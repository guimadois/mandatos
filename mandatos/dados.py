"""Transforma os CSVs oficiais em dados do site. Regras: nada é inventado nem deduzido;
campo ausente fica None; todo registro guarda a URL oficial e quando foi coletado."""
import json
import re
import unicodedata
from pathlib import Path

from . import config

PASTA_DADOS = Path(__file__).resolve().parent.parent / "dados"


class DadosInvalidos(Exception):
    """A coleta veio incompleta ou estranha: o site fica com a última versão boa."""


def _limpa(v):
    v = (v or "").strip()
    return v or None


def chave_alfabetica(nome):
    """Ordem alfabética do português: ignora acentos e maiúsculas (Érico fica no E, não depois do Z)."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", nome or "") if not unicodedata.combining(c))
    return sem_acento.casefold()


def id_da_url(url):
    m = re.search(r"-(\d+)/?$", url or "")
    return m.group(1) if m else None


def slug_da_url(url):
    m = re.search(r"/vereador/([^/?#]+)$", (url or "").strip())
    return m.group(1) if m else None


def montar_vereadores(linhas):
    """Titulares da legislatura acompanhada, exatamente como o CSV oficial informa."""
    out = []
    for l in linhas:
        if config.LEGISLATURA not in (l.get("Legislaturas") or ""):
            continue
        url = _limpa(l.get("Link no site"))
        out.append({
            "id_oficial": id_da_url(url),
            "slug": slug_da_url(url),
            "nome": _limpa(l.get("Nome")),
            "nome_civil": _limpa(l.get("Nome Civil")),
            "partidos_registrados": _limpa(l.get("Partidos")),  # histórico, como no CSV; não é "partido atual"
            "legislaturas": _limpa(l.get("Legislaturas")),
            "url_origem": url,
        })
    out.sort(key=lambda v: chave_alfabetica(v["nome"]))
    return out


def mapa_nome_para_id(vereadores):
    """Nome exato -> id oficial. Nome repetido entre vereadores não entra no mapa (ambíguo)."""
    contagem = {}
    for v in vereadores:
        contagem[v["nome"]] = contagem.get(v["nome"], 0) + 1
    return {v["nome"]: v["id_oficial"] for v in vereadores if contagem[v["nome"]] == 1}


def _autores(linha, nome_para_id=None):
    if "Autores" not in linha and "Autoria" in linha:
        # Formato sem IDs (CSV de 2025): só nome exato; sem aproximação.
        nomes = [n.strip() for n in (linha.get("Autoria") or "").split(",") if n.strip()]
        out = []
        for n in nomes:
            vid = (nome_para_id or {}).get(n)
            out.append({"nome": n, "id": vid, "id_por_nome": True} if vid else {"nome": n, "id": None})
        return out
    nomes = [n.strip() for n in (linha.get("Autores") or "").split(",") if n.strip()]
    ids = [i.strip() for i in (linha.get("Ids dos Autores") or "").split(",") if i.strip()]
    if len(nomes) == len(ids):
        return [{"nome": n, "id": i} for n, i in zip(nomes, ids)]
    # Quantidades diferentes: não pareamos nomes e ids para não atribuir autoria errada.
    return [{"nome": n, "id": None} for n in nomes]


def montar_proposicoes(linhas, ids_vereadores, url_csv, coletado_em, nome_para_id=None):
    """Proposições (tipos de CATEGORIAS) com ao menos um autor vereador da legislatura."""
    out = {}
    for l in linhas:
        subtipo = _limpa(l.get("Subtipo"))
        if subtipo not in config.SUBTIPO_PARA_CATEGORIA:
            continue
        autores = _autores(l, nome_para_id)
        if not any(a["id"] in ids_vereadores for a in autores):
            continue
        url = _limpa(l.get("Link no site"))
        rid = id_da_url(url)
        if not rid:
            continue
        out[rid] = {
            "id_oficial": rid,
            "tipo": subtipo,
            "categoria": config.SUBTIPO_PARA_CATEGORIA[subtipo],
            "numero": _limpa(l.get("Número")),
            "ano": _limpa(l.get("Ano")),
            "data": _limpa(l.get("Data")),
            "situacao": _limpa(l.get("Situação")),
            "protocolo": _limpa(l.get("Protocolo")),
            "titulo": _limpa(l.get("Título")),
            "autores": autores,
            "ementa": None,  # não existe no CSV oficial; ver documento em url_origem
            "url_origem": url,
            "fonte": url_csv,
            "coletado_em": coletado_em,
        }
    return out


def preservar_coletado_em(novos, anteriores):
    """Registro que não mudou mantém a data da coleta anterior (histórico do git fica limpo)."""
    for rid, r in novos.items():
        a = anteriores.get(rid)
        if a and {k: v for k, v in a.items() if k != "coletado_em"} == {k: v for k, v in r.items() if k != "coletado_em"}:
            r["coletado_em"] = a["coletado_em"]
    return novos


def validar(vereadores, proposicoes, anteriores):
    erros = []
    if not (config.MIN_VEREADORES <= len(vereadores) <= config.MAX_VEREADORES):
        erros.append(f"{len(vereadores)} vereadores na legislatura {config.LEGISLATURA} (esperado "
                     f"{config.MIN_VEREADORES}-{config.MAX_VEREADORES})")
    if any(not v["id_oficial"] or not v["slug"] or not v["nome"] for v in vereadores):
        erros.append("vereador sem id, slug ou nome")
    if not proposicoes:
        erros.append("nenhuma proposição")
    for r in proposicoes.values():
        if not r["url_origem"].startswith(config.BASE + "/documento/"):
            erros.append(f"{r['id_oficial']}: URL fora da Câmara ({r['url_origem']})")
        if not r["data"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["data"]):
            erros.append(f"{r['id_oficial']}: data inválida ({r['data']})")
        if not r["autores"]:
            erros.append(f"{r['id_oficial']}: sem autores")
    # Queda brusca por ano em relação à última versão publicada
    por_ano_ant, por_ano = {}, {}
    for r in anteriores.values():
        por_ano_ant[r["ano"]] = por_ano_ant.get(r["ano"], 0) + 1
    for r in proposicoes.values():
        por_ano[r["ano"]] = por_ano.get(r["ano"], 0) + 1
    for ano, n_ant in por_ano_ant.items():
        n = por_ano.get(ano, 0)
        if n_ant and n < n_ant * (1 - config.QUEDA_MAXIMA):
            erros.append(f"ano {ano}: {n} proposições, eram {n_ant} (queda acima de "
                         f"{int(config.QUEDA_MAXIMA * 100)}%)")
    if erros:
        raise DadosInvalidos("; ".join(erros[:20]) + (f" (+{len(erros) - 20})" if len(erros) > 20 else ""))


# ---------------------------------------------------------------- persistência
def _escreve_linhas(caminho, registros):
    """Um registro por linha: arquivo pequeno de ler e diff legível no git."""
    tmp = caminho.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write("[\n")
        f.write(",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in registros))
        f.write("\n]\n")
    tmp.replace(caminho)


def salvar(pasta, vereadores, proposicoes, meta):
    pasta.mkdir(parents=True, exist_ok=True)
    lista = sorted(proposicoes.values(), key=lambda r: (r["data"], int(r["numero"] or 0), int(r["id_oficial"])), reverse=True)
    _escreve_linhas(pasta / "vereadores.json", vereadores)
    _escreve_linhas(pasta / "proposicoes.json", lista)
    (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carregar(pasta):
    def ler(nome, padrao):
        p = pasta / nome
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao
    vereadores = ler("vereadores.json", [])
    proposicoes = {r["id_oficial"]: r for r in ler("proposicoes.json", [])}
    return vereadores, proposicoes, ler("meta.json", {})
