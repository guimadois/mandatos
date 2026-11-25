#!/usr/bin/env python3
"""PoC Radar Legislativo Joinville — coleta de amostra de proposições.

Fontes (todas públicas, camara.joinville.br):
  - Dados Abertos (CSV oficial): /DadosAbertos/download/documentos-AAAA.csv e vereadores.csv
  - Página de detalhe da proposição: /documento/<slug>-<id>  (ementa, texto, movimentações)
  - GPS Legislativo: /documentos/localizacoes/ano:AAAA  (lat/long por documento)

Regras: 1 requisição a cada 3 s, sem paralelismo, timeout, no máx. 2 retentativas,
UA identificável. Aborta em 403/429, CAPTCHA/login ou redirecionamento para fora do domínio.
Não inventa campos: ausente => null. Não baixa PDFs (protegidos por CAPTCHA).

Uso:
  python coleta.py --fase 1          # 25 proposições de 1 vereador
  python coleta.py --fase 2          # amplia até ~100, variando vereadores e tipos
  python coleta.py --conferir 5      # Etapa 3: reconfere 5 registros com a página oficial
  python coleta.py --metricas        # Etapa 3: métricas da amostra
"""
import argparse
import csv
import io
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://camara.joinville.br"
UA = "RadarJoinville-PoC/0.1 (projeto pessoal de transparência)"
INTERVALO_S = 3.0
TIMEOUT_S = 20
MAX_RETENTATIVAS = 2
ANO = 2026
TZ = ZoneInfo("America/Sao_Paulo")
SAIDA = Path(__file__).with_name("amostra.json")

# Subtipos considerados "proposições" de vereadores (nomes exatos do CSV oficial).
SUBTIPOS_PROPOSICAO = [
    "Indicação", "Moção", "Requerimento", "Pedido de Informação",
    "Projeto de Lei Ordinária", "Projeto de Lei Complementar",
    "Projeto de Decreto Legislativo", "Projeto de Resolução",
    "Proposta de Emenda à Lei Orgânica",
]
VEREADOR_FASE1 = "213714"  # Instrutor Lucas (id oficial no site)
CAMPOS_ESSENCIAIS = ["id_oficial", "tipo", "numero", "ano", "autores", "data",
                     "ementa", "situacao", "url_origem", "coletado_em"]


class Bloqueio(Exception):
    """Condição em que a coleta deve PARAR (não contornar)."""


class Cliente:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR"})
        self._ultima = 0.0
        self.requisicoes = 0
        self.falhas = []

    def get(self, url):
        for tentativa in range(MAX_RETENTATIVAS + 1):
            espera = INTERVALO_S - (time.monotonic() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            self._ultima = time.monotonic()
            self.requisicoes += 1
            try:
                r = self.s.get(url, timeout=TIMEOUT_S, allow_redirects=True)
            except requests.RequestException as e:
                self.falhas.append({"url": url, "tentativa": tentativa, "erro": repr(e)})
                continue
            final = r.url
            if urlparse(final).netloc != "camara.joinville.br":
                raise Bloqueio(f"redirecionamento para fora do domínio: {url} -> {final}")
            if any(k in final.lower() for k in ("validar_captcha", "captcha", "login")):
                raise Bloqueio(f"CAPTCHA/login encontrado: {url} -> {final}")
            if r.status_code in (403, 429):
                raise Bloqueio(f"HTTP {r.status_code} em {url}")
            if r.status_code >= 500:
                self.falhas.append({"url": url, "tentativa": tentativa, "erro": f"HTTP {r.status_code}"})
                continue
            if r.status_code != 200:
                self.falhas.append({"url": url, "tentativa": tentativa, "erro": f"HTTP {r.status_code}"})
                return None
            r.encoding = "utf-8"
            return r
        return None


def agora():
    return datetime.now(TZ).isoformat(timespec="seconds")


def limpa(t):
    if t is None:
        return None
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def id_da_url(url):
    m = re.search(r"-(\d+)/?$", url or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- fontes
def baixa_csv(cli, nome):
    r = cli.get(f"{BASE}/DadosAbertos/download/{nome}")
    if r is None:
        raise SystemExit(f"falha ao baixar {nome}")
    texto = r.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto), delimiter=";")), r.url


def baixa_gps(cli, ano):
    url = f"{BASE}/documentos/localizacoes/ano:{ano}"
    r = cli.get(url)
    if r is None:
        return {}, url
    m = re.search(r"var documentos = (\[.*?\]);\s*\n", r.text, re.S)
    if not m:
        return {}, url
    out = {}
    for d in json.loads(m.group(1)):
        doc, end = d.get("Documento") or {}, d.get("DocumentoEndereco") or {}
        if doc.get("id"):
            out[str(doc["id"])] = {
                "latitude": end.get("latitude") or None,
                "longitude": end.get("longitude") or None,
                "resumo_gps": doc.get("resumo") or None,
            }
    return out, url


def campo_bloco(soup, titulo):
    for sp in soup.select(".block-text > span.title"):
        if limpa(sp.get_text()) == titulo:
            p = sp.find_next_sibling("p")
            return limpa(p.get_text(" ")) if p else None
    return None


def parse_detalhe(html):
    soup = BeautifulSoup(html, "html.parser")
    h1 = next((h for h in soup.find_all("h1") if "Nº" in h.get_text()), None)
    autores = []
    for sp in soup.select(".block-text > span.title"):
        if limpa(sp.get_text()) == "Autoria":
            for a in sp.parent.select(".author a[href]"):
                autores.append({"nome": limpa(a.get_text()), "id": id_da_url(a["href"])})
    texto = None
    inp = soup.find("input", attrs={"name": "data[conteudo]"})
    if inp and inp.get("value"):
        texto = limpa(BeautifulSoup(inp["value"], "html.parser").get_text(" "))
    movs = []
    for it in soup.select(".item-movimentation"):
        movs.append({
            "data_hora": limpa(it.select_one(".date").get_text()) if it.select_one(".date") else None,
            "descricao": limpa(it.select_one(".title").get_text(" ")) if it.select_one(".title") else None,
            "detalhe": limpa(it.select_one("p").get_text(" ")) if it.select_one("p") else None,
        })
    votos = soup.select_one("#como-votou-cada-vereador")
    votacao_urls = sorted({m for m in re.findall(r"/sessao/documento/votacao/\d+", str(votos))}) if votos else []
    sem_votacao = bool(votos and "Nenhuma sessão com votação" in votos.get_text())
    return {
        "titulo_pagina": limpa(h1.get_text()) if h1 else None,
        "ementa": campo_bloco(soup, "Ementa"),
        "situacao": campo_bloco(soup, "Situação"),
        "data_documento_texto": campo_bloco(soup, "Data do Documento"),
        "autores": autores,
        "texto_principal": texto,
        "movimentacoes": movs,
        "votacao": {
            "secao_existe": votos is not None,
            "sem_votacao_registrada": sem_votacao if votos is not None else None,
            "urls_votos_nominais": [BASE + u for u in votacao_urls],
        },
        "pdf_original_atras_de_captcha": "validar_captcha" in html,
    }


# ---------------------------------------------------------------- montagem
def monta_registro(linha, det, gps, url_csv, url_gps, coletado_em):
    url = linha["Link no site"].strip()
    ids = [i.strip() for i in (linha.get("Ids dos Autores") or "").split(",") if i.strip()]
    nomes = [n.strip() for n in (linha.get("Autores") or "").split(",") if n.strip()]
    autores_csv = [{"nome": n, "id": i} for n, i in zip(nomes, ids)] if len(nomes) == len(ids) else \
        [{"nome": n, "id": None} for n in nomes]
    g = gps.get(id_da_url(url))
    ementa = det.get("ementa") if det else None
    loc_campo = bool(g and g["latitude"] and g["longitude"])
    texto_loc = " ".join(filter(None, [ementa]))
    return {
        "id_oficial": id_da_url(url),
        "tipo": linha.get("Subtipo") or None,
        "tipo_geral": linha.get("Tipo") or None,
        "titulo": linha.get("Título") or None,
        "numero": linha.get("Número") or None,
        "ano": linha.get("Ano") or None,
        "autores": autores_csv or None,
        "data": linha.get("Data") or None,
        "ementa": ementa,
        "situacao": linha.get("Situação") or None,
        "protocolo": linha.get("Protocolo") or None,
        "url_origem": url,
        "coletado_em": coletado_em,
        "detalhe_html": det,  # valores como aparecem na página oficial (para conferência)
        "localizacao": {
            "latitude": g["latitude"], "longitude": g["longitude"], "fonte": url_gps,
        } if loc_campo else None,
        "local_em_campo_proprio": loc_campo,  # coordenadas estruturadas no GPS Legislativo
        "bairro_mencionado_no_texto": bool(re.search(r"\bbairro\b", texto_loc, re.I)) if ementa else None,
        "rua_mencionada_no_texto": bool(re.search(r"\b(rua|avenida|av\.|estrada|travessa|servid[aã]o)\b", texto_loc, re.I)) if ementa else None,
        "fontes": {
            "id_oficial,tipo,titulo,numero,ano,autores,data,situacao,protocolo,url_origem": url_csv,
            "ementa,detalhe_html": url,
            "localizacao": url_gps if loc_campo else None,
        },
    }


def seleciona(linhas, ids_vereadores, fase, ja):
    prop = [l for l in linhas if l["Subtipo"].strip() in SUBTIPOS_PROPOSICAO
            and any(i.strip() in ids_vereadores for i in l["Ids dos Autores"].split(","))]
    prop.sort(key=lambda l: (l["Data"], l["Link no site"]), reverse=True)
    if fase == 1:
        alvo = 25
        dele = [l for l in prop if VEREADOR_FASE1 in [i.strip() for i in l["Ids dos Autores"].split(",")]]
        # variar tipos: round-robin por subtipo
        return round_robin(dele, key=lambda l: l["Subtipo"], n=alvo, excluir=ja)
    alvo = 100 - len(ja)
    return round_robin(prop, key=lambda l: (l["Ids dos Autores"].split(",")[0].strip(), l["Subtipo"]),
                       n=alvo, excluir=ja, chave2=lambda l: l["Subtipo"])


def round_robin(linhas, key, n, excluir, chave2=None):
    """Seleção determinística: alterna entre grupos (vereador/tipo), mais recentes primeiro."""
    grupos = {}
    for l in linhas:
        if id_da_url(l["Link no site"]) in excluir:
            continue
        grupos.setdefault(key(l), []).append(l)
    ordem = sorted(grupos)
    if chave2:  # priorizar tipos raros primeiro para garantir variedade
        rnd = random.Random(42)
        rnd.shuffle(ordem)
        ordem.sort(key=lambda k: len(grupos[k]))
    out, vistos = [], set()
    while len(out) < n and any(grupos.values()):
        for k in ordem:
            if grupos[k] and len(out) < n:
                l = grupos[k].pop(0)
                i = id_da_url(l["Link no site"])
                if i not in vistos:
                    vistos.add(i)
                    out.append(l)
    return out


def carrega():
    if SAIDA.exists():
        return {r["id_oficial"]: r for r in json.loads(SAIDA.read_text(encoding="utf-8"))["registros"]}
    return {}


def salva(regs, meta):
    SAIDA.write_text(json.dumps({"meta": meta, "registros": list(regs.values())},
                                ensure_ascii=False, indent=2), encoding="utf-8")


def coletar(fase):
    cli = Cliente()
    regs = carrega()
    try:
        vers, _ = baixa_csv(cli, "vereadores.csv")
        ids_ver = {id_da_url(v["Link no site"]) for v in vers}
        linhas, url_csv = baixa_csv(cli, f"documentos-{ANO}.csv")
        gps, url_gps = baixa_gps(cli, ANO)
        alvo = seleciona(linhas, ids_ver, fase, set(regs))
        print(f"fase {fase}: {len(alvo)} proposições a coletar (já na amostra: {len(regs)})")
        for n, l in enumerate(alvo, 1):
            url = l["Link no site"].strip()
            r = cli.get(url)
            det = parse_detalhe(r.text) if r is not None else None
            reg = monta_registro(l, det, gps, url_csv, url_gps, agora())
            if reg["id_oficial"] in regs:
                continue
            regs[reg["id_oficial"]] = reg
            print(f"  [{n:3}/{len(alvo)}] {reg['id_oficial']} {reg['tipo']} {reg['numero']}/{reg['ano']} "
                  f"ementa={'ok' if reg['ementa'] else 'NULL'}")
    except Bloqueio as b:
        print(f"\n⛔ PARADA: {b}")
        cli.falhas.append({"bloqueio": str(b)})
    meta = {
        "ultima_execucao": agora(), "fase": fase, "user_agent": UA,
        "intervalo_s": INTERVALO_S, "requisicoes_ultima_execucao": cli.requisicoes,
        "falhas_ultima_execucao": cli.falhas,
    }
    salva(regs, meta)
    print(f"\nsalvo {len(regs)} registros em {SAIDA.name}; requisições={cli.requisicoes}; falhas={len(cli.falhas)}")


# ---------------------------------------------------------------- Etapa 3
def conferir(n):
    """Refaz GET de n registros e compara campo a campo: CSV oficial x página oficial atual."""
    regs = list(carrega().values())
    rnd = random.Random(7)
    # garantir tipos variados na conferência
    por_tipo = {}
    for r in regs:
        por_tipo.setdefault(r["tipo"], []).append(r)
    escolha = []
    for t in sorted(por_tipo, key=lambda t: -len(por_tipo[t])):
        if len(escolha) < n:
            escolha.append(rnd.choice(por_tipo[t]))
    cli = Cliente()
    meses = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                                          "agosto", "setembro", "outubro", "novembro", "dezembro"], 1)}
    resultado = []
    for r in escolha:
        resp = cli.get(r["url_origem"])
        d = parse_detalhe(resp.text) if resp is not None else {}
        titulo = d.get("titulo_pagina") or ""
        m = re.match(r"(.+?) Nº (\d+)/(\d{4})", titulo)
        dt = None
        if d.get("data_documento_texto"):
            mm = re.match(r"(\d+) de (\w+) de (\d{4})", d["data_documento_texto"])
            if mm and mm.group(2).lower() in meses:
                dt = f"{mm.group(3)}-{meses[mm.group(2).lower()]:02d}-{int(mm.group(1)):02d}"
        pagina = {
            "id_oficial": id_da_url(resp.url) if resp is not None else None,
            "tipo": m.group(1) if m else None,
            "numero": m.group(2) if m else None,
            "ano": m.group(3) if m else None,
            "autores": sorted(a["nome"] for a in d.get("autores", [])),
            "data": dt,
            "ementa": d.get("ementa"),
            "situacao": d.get("situacao"),
        }
        amostra = {
            "id_oficial": r["id_oficial"], "tipo": r["tipo"], "numero": r["numero"], "ano": r["ano"],
            "autores": sorted(a["nome"] for a in (r["autores"] or [])), "data": r["data"],
            "ementa": r["ementa"], "situacao": r["situacao"],
        }
        campos = {k: {"amostra": amostra[k], "pagina": pagina[k], "bate": amostra[k] == pagina[k]}
                  for k in amostra}
        resultado.append({"url": r["url_origem"], "conferido_em": agora(), "campos": campos})
    Path(__file__).with_name("conferencia.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    for res in resultado:
        print(f"\n{res['url']}")
        for k, v in res["campos"].items():
            flag = "OK " if v["bate"] else "DIF"
            print(f"  {flag} {k:11} amostra={str(v['amostra'])[:70]!r}  pagina={str(v['pagina'])[:70]!r}")
    print(f"\nrequisições={cli.requisicoes} falhas={cli.falhas}")


def metricas():
    data = json.loads(SAIDA.read_text(encoding="utf-8"))
    regs = data["registros"]
    ids = [r["id_oficial"] for r in regs]
    completos = [r for r in regs if all(r.get(c) not in (None, "", []) for c in CAMPOS_ESSENCIAIS)]
    faltando = {}
    for r in regs:
        for c in CAMPOS_ESSENCIAIS:
            if r.get(c) in (None, "", []):
                faltando[c] = faltando.get(c, 0) + 1
    tipos, autores = {}, set()
    for r in regs:
        tipos[r["tipo"]] = tipos.get(r["tipo"], 0) + 1
        for a in r["autores"] or []:
            autores.add(a["nome"])
    print(json.dumps({
        "total": len(regs),
        "completos_campos_essenciais": len(completos),
        "pct_completos": round(100 * len(completos) / len(regs), 1) if regs else 0,
        "faltando_por_campo": faltando,
        "duplicatas_id_oficial": len(ids) - len(set(ids)),
        "falhas_requisicao_ultima_execucao": data["meta"]["falhas_ultima_execucao"],
        "por_tipo": tipos,
        "autores_distintos": len(autores),
        "com_coordenadas_gps": sum(1 for r in regs if r["local_em_campo_proprio"]),
        "bairro_mencionado_no_texto": sum(1 for r in regs if r["bairro_mencionado_no_texto"]),
        "rua_mencionada_no_texto": sum(1 for r in regs if r["rua_mencionada_no_texto"]),
        "com_votos_nominais": sum(1 for r in regs if (r["detalhe_html"] or {}).get("votacao", {}).get("urls_votos_nominais")),
        "divergencia_situacao_csv_vs_html": sum(1 for r in regs if r["detalhe_html"] and r["detalhe_html"]["situacao"] != r["situacao"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", type=int, choices=[1, 2])
    ap.add_argument("--conferir", type=int)
    ap.add_argument("--metricas", action="store_true")
    a = ap.parse_args()
    if a.fase:
        coletar(a.fase)
    elif a.conferir:
        conferir(a.conferir)
    elif a.metricas:
        metricas()
    else:
        ap.print_help()
        sys.exit(1)
