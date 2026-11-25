"""Gera o site estático:  python -m mandatos.site  (lê dados/, escreve _site/)"""
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont

from . import config, dados

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "_site"
RECENTES_POR_CATEGORIA = 10
POR_PAGINA = 100  # listas longas viram páginas estáticas de até 100 itens (#6)
RECENTES_HOME = 10      # feed da home (#2)
RECENTES_MAX = 500      # página "Mais recentes": as 500 últimas; as mais antigas ficam nas páginas de grupo

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def milhar(n):
    """Número no padrão brasileiro: 4007 -> "4.007". Um só lugar para todo número exibido."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return n


def reais(v):
    """Valor em reais no padrão brasileiro: 19500 -> "R$ 19.500,00"."""
    if v is None:
        return ""
    inteiro, cent = f"{float(v):,.2f}".split(".")
    return f"R$\u00a0{inteiro.replace(',', '.')},{cent}"  # espaço inseparável: "R$" não fica sozinho na linha


def subsidio(cfg):
    """Valor da lei corrigido pelas revisões anuais (cada uma sobre o valor anterior, em centavos).
    Sem valor, lei e link oficial, não mostra nada."""
    if not all((cfg or {}).get(k) for k in ("valor_lei", "lei", "lei_url")):
        return None
    atual = round(float(cfg["valor_lei"]), 2)
    for r in cfg.get("revisoes", []):
        atual = round(atual * (1 + r["pct"] / 100), 2)
    return {**cfg, "revisoes": cfg.get("revisoes", []), "atual": atual}


def data_br(iso):
    if not iso:
        return ""
    a, m, d = iso[:10].split("-")
    return f"{d}/{m}/{a}"


def data_extenso(iso):
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso)
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}, {dt:%H:%M}"


CORES = {"melhorias": "#2f7d4f", "perguntas": "#a35d00", "leis": "#0a5a8c", "mocoes": "#8a4fa8",
         "requerimentos": "#5a6874"}


def imagem_og(destino, composicao_cidade):
    """Imagem genérica de pré-visualização (1200x630). Usa a fonte Noto Sans que vai
    junto com o projeto (não depende das fontes do servidor) e o nome da marca da config."""
    W, H, M = 1200, 630, 80
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    pasta = Path(__file__).parent / "fontes"  # Noto Sans (SIL OFL 1.1), cobre os acentos do português
    fonte = lambda t, negrito=False: ImageFont.truetype(
        str(pasta / ("NotoSans-Bold.ttf" if negrito else "NotoSans-Regular.ttf")), t)
    d.text((M, 110), config.MARCA, font=fonte(84, True), fill="#17222c")
    larg = d.textlength(config.MARCA + " ", font=fonte(84, True))
    d.text((M + larg, 110), config.LOCAL, font=fonte(84, True), fill="#0a5a8c")
    d.text((M, 240), "O que cada vereador apresentou na Câmara", font=fonte(44), fill="#17222c")
    d.text((M, 300), "Só dados oficiais, com link para cada documento", font=fonte(34), fill="#5a6874")
    x, y, total_w, h, vao = M, 400, W - 2 * M, 28, 4
    segs = [c for c in composicao_cidade if c["total"]]
    util = total_w - vao * (len(segs) - 1)  # desconta os vãos para nenhum segmento ser cortado
    for i, c in enumerate(segs):
        w = max(3, round(util * c["pct"] / 100))
        if i == len(segs) - 1:
            w = M + total_w - x  # o último fecha exatamente na margem
        d.rectangle([x, y, x + w - 1, y + h], fill=CORES.get(c["chave"], "#5a6874"))
        x += w + vao
    d.text((M, 500), "Dados Abertos da Câmara de Vereadores de Joinville", font=fonte(30), fill="#5a6874")
    img.save(destino, "PNG", optimize=True)


def descricao_vereador(f, periodo):
    """Descrição neutra, só com números, para buscadores e pré-visualização."""
    partes = [f'{milhar(c["total"])} {c["nome"].lower()}' for c in f["categorias"] if c["total"]]
    return (f'{f["nome"]}: {milhar(f["total"])} proposições em {periodo}, como autor ou coautor'
            + (": " + ", ".join(partes) if partes else "") + ". Dados oficiais da Câmara de Joinville.")


def composicao(categorias):
    """Proporção de cada grupo (para a barra). Percentuais exatos para a largura; arredondados só para exibir."""
    total = sum(c["total"] for c in categorias)
    out = []
    for c in categorias:
        pct = 100 * c["total"] / total if total else 0
        out.append({"chave": c["chave"], "nome": c["nome"], "total": c["total"], "pct": pct,
                    "pct_txt": f"{pct:.0f}%" if pct >= 1 or pct == 0 else "<1%"})
    return out


def nome_pagina(chave, n):
    return f"{chave}.html" if n == 1 else f"{chave}-p{n}.html"


def iniciais(nome):
    """Avatar neutro de quem não tem foto: primeira e última inicial do nome parlamentar."""
    partes = [p for p in (nome or "").split() if p[:1].isalpha()]
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


def montar_contexto(vereadores, proposicoes, meta, fotos=None):
    fotos = fotos or {}
    por_vereador = {v["id_oficial"]: [] for v in vereadores}
    for p in sorted(proposicoes.values(), key=lambda r: (r["data"], int(r["numero"] or 0), int(r["id_oficial"])), reverse=True):
        for a in p["autores"]:
            if a["id"] in por_vereador:
                por_vereador[a["id"]].append(p)
    fichas = []
    for v in sorted(vereadores, key=lambda x: dados.chave_alfabetica(x["nome"])):
        props = por_vereador[v["id_oficial"]]
        cont = Counter(p["categoria"] for p in props)
        cats = []
        for c in config.CATEGORIAS:
            itens = [p for p in props if p["categoria"] == c["chave"]]
            cats.append({**c, "total": cont.get(c["chave"], 0), "itens": itens,
                         "recentes": itens[:RECENTES_POR_CATEGORIA]})
        fichas.append({**v, "total": len(props), "categorias": cats, "composicao": composicao(cats),
                       "coautoria": sum(1 for p in props if len(p["autores"]) > 1),
                       "foto": fotos.get(v["id_oficial"]), "iniciais": iniciais(v["nome"])})
    anos = sorted({p["ano"] for p in proposicoes.values() if p["ano"]})
    cronologica = sorted(proposicoes.values(), key=lambda r: (r["data"], int(r["numero"] or 0), int(r["id_oficial"])),
                         reverse=True)
    slug_por_id = {v["id_oficial"]: v["slug"] for v in vereadores}
    partidos = sorted({p.strip() for v in vereadores for p in (v["partidos_registrados"] or "").split(",") if p.strip()},
                      key=dados.chave_alfabetica)
    # Cidade: cada proposição conta uma vez, mesmo com vários autores (#1)
    cont_cidade = Counter(p["categoria"] for p in proposicoes.values())
    cats_cidade = [{**c, "total": cont_cidade.get(c["chave"], 0)} for c in config.CATEGORIAS]
    por_ano = Counter(p["ano"] for p in proposicoes.values())
    return {
        "fichas": fichas,
        "cronologica": cronologica,
        "recentes_home": cronologica[:RECENTES_HOME],
        "slug_por_id": slug_por_id,
        "partidos": partidos,
        "cidade": {"total": len(proposicoes), "categorias": cats_cidade, "composicao": composicao(cats_cidade),
                   "por_ano": [(a, por_ano[a]) for a in sorted(por_ano)]},
        "categorias": config.CATEGORIAS,
        "meta": meta,
        "anos": anos,
        "periodo": " e ".join(anos) if len(anos) <= 2 else f"{anos[0]} a {anos[-1]}",
        "legislatura": config.LEGISLATURA.replace(" - ", "–"),
        "contato_correcao": config.CONTATO_CORRECAO,
        "marca": config.MARCA,
        "local": config.LOCAL,
        "nome_site": config.NOME_SITE,
        "autor": config.AUTOR,
        "autor_linkedin": config.AUTOR_LINKEDIN,
        "repositorio": config.REPOSITORIO,
        "total_proposicoes": len(proposicoes),
        "csv_vereadores": next((f for f in meta.get("fontes", []) if f.endswith("vereadores.csv")), None),
        "csvs_documentos": [f for f in meta.get("fontes", []) if "/documentos-" in f],
        "dados_abertos": config.BASE + "/DadosAbertos",
        "site_url": config.SITE_URL,
        "subsidio": subsidio(config.SUBSIDIO),
        "tse": {"dataset": config.TSE_DATASET, "licenca": config.TSE_LICENCA, "licenca_url": config.TSE_LICENCA_URL,
                "ano": config.TSE_ANO, "com_foto": sum(1 for f in fichas if f["foto"]),
                "manuais": [f["nome"] for f in fichas if f["foto"] and f["foto"]["regra"] == "conferido manualmente"]},
    }


def gerar(saida=SAIDA, pasta_dados=dados.PASTA_DADOS):
    vereadores, proposicoes, meta = dados.carregar(pasta_dados)
    if not vereadores or not proposicoes:
        raise SystemExit("dados/ vazio: rode antes  python -m mandatos.coletar")
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["data_br"] = data_br
    env.filters["milhar"] = milhar
    env.filters["reais"] = reais
    env.filters["data_extenso"] = data_extenso
    fotos = dados.carregar_fotos(pasta_dados)
    ctx = montar_contexto(vereadores, proposicoes, meta, fotos)

    if saida.exists():
        shutil.rmtree(saida)
    (saida / "vereador").mkdir(parents=True)
    if fotos:
        (saida / "fotos").mkdir()
        for r in fotos.values():
            shutil.copy(pasta_dados / r["arquivo"], saida / r["arquivo"])

    def escreve(rel, template, raiz, **extra):
        destino = saida / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(env.get_template(template).render(**ctx, **extra, raiz=raiz, caminho=rel), encoding="utf-8")

    def paginado(pasta, chave, itens, template, raiz, **extra):
        """Grava itens em páginas de POR_PAGINA: <chave>.html, <chave>-p2.html… (#6)"""
        paginas = [itens[i:i + POR_PAGINA] for i in range(0, len(itens), POR_PAGINA)] or [[]]
        for n, pag in enumerate(paginas, 1):
            escreve(f"{pasta}/{nome_pagina(chave, n)}" if pasta else nome_pagina(chave, n), template, raiz,
                    itens=pag, pagina=n, total_paginas=len(paginas), total_itens=len(itens),
                    anterior=nome_pagina(chave, n - 1) if n > 1 else None,
                    proxima=nome_pagina(chave, n + 1) if n < len(paginas) else None,
                    primeiro=(n - 1) * POR_PAGINA + 1, ultimo=(n - 1) * POR_PAGINA + len(pag), **extra)

    escreve("index.html", "index.html", "")
    # #3: grupos da cidade, com filtro por ano (páginas estáticas)
    for c in ctx["cidade"]["categorias"]:
        do_grupo = [p for p in ctx["cronologica"] if p["categoria"] == c["chave"]]
        abas = [{"rotulo": "Todos", "ano": None, "arquivo": f"{c['chave']}.html", "total": len(do_grupo)}]
        abas += [{"rotulo": a, "ano": a, "arquivo": f"{c['chave']}-{a}.html",
                  "total": sum(1 for p in do_grupo if p["ano"] == a)} for a in ctx["anos"]]
        for aba in abas:
            itens = do_grupo if aba["ano"] is None else [p for p in do_grupo if p["ano"] == aba["ano"]]
            paginado("grupo", aba["arquivo"][:-5], itens, "grupo.html", "../", c=c, abas=abas, aba=aba)
    # #2: mais recentes da cidade
    paginado("", "recentes", ctx["cronologica"][:RECENTES_MAX], "recentes.html", "")
    escreve("como-funciona.html", "como_funciona.html", "")
    escreve("sobre.html", "sobre.html", "")
    for f in ctx["fichas"]:
        escreve(f"vereador/{f['slug']}.html", "vereador.html", "../", v=f,
                descricao_meta=descricao_vereador(f, ctx["periodo"]))
        for c in f["categorias"]:
            if c["itens"]:
                paginado(f"vereador/{f['slug']}", c["chave"], c["itens"], "lista.html", "../../", v=f, c=c)
    imagem_og(saida / "og.png", ctx["cidade"]["composicao"])
    (saida / ".nojekyll").write_text("")
    n = sum(1 for _ in saida.rglob("*.html"))
    print(f"site gerado em {saida} ({n} páginas)")
    return saida


if __name__ == "__main__":
    gerar()
    sys.exit(0)
