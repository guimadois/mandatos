"""Gera o site estático:  python -m mandatos.site  (lê dados/, escreve _site/)"""
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, dados

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "_site"
RECENTES_POR_CATEGORIA = 10
POR_PAGINA = 100  # listas longas viram páginas estáticas de até 100 itens (#6)

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


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


def nome_pagina(chave, n):
    return f"{chave}.html" if n == 1 else f"{chave}-p{n}.html"


def montar_contexto(vereadores, proposicoes, meta):
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
        fichas.append({**v, "total": len(props), "categorias": cats,
                       "coautoria": sum(1 for p in props if len(p["autores"]) > 1)})
    anos = sorted({p["ano"] for p in proposicoes.values() if p["ano"]})
    return {
        "fichas": fichas,
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
    }


def gerar(saida=SAIDA, pasta_dados=dados.PASTA_DADOS):
    vereadores, proposicoes, meta = dados.carregar(pasta_dados)
    if not vereadores or not proposicoes:
        raise SystemExit("dados/ vazio: rode antes  python -m mandatos.coletar")
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["data_br"] = data_br
    env.filters["data_extenso"] = data_extenso
    ctx = montar_contexto(vereadores, proposicoes, meta)

    if saida.exists():
        shutil.rmtree(saida)
    (saida / "vereador").mkdir(parents=True)

    def escreve(rel, template, raiz, **extra):
        destino = saida / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(env.get_template(template).render(**ctx, **extra, raiz=raiz), encoding="utf-8")

    escreve("index.html", "index.html", "")
    escreve("como-funciona.html", "como_funciona.html", "")
    escreve("sobre.html", "sobre.html", "")
    for f in ctx["fichas"]:
        escreve(f"vereador/{f['slug']}.html", "vereador.html", "../", v=f)
        for c in f["categorias"]:
            paginas = [c["itens"][i:i + POR_PAGINA] for i in range(0, len(c["itens"]), POR_PAGINA)]
            for n, itens in enumerate(paginas, 1):
                escreve(f"vereador/{f['slug']}/{nome_pagina(c['chave'], n)}", "lista.html", "../../", v=f, c=c,
                        itens=itens, pagina=n, total_paginas=len(paginas),
                        anterior=nome_pagina(c["chave"], n - 1) if n > 1 else None,
                        proxima=nome_pagina(c["chave"], n + 1) if n < len(paginas) else None,
                        primeiro=(n - 1) * POR_PAGINA + 1, ultimo=(n - 1) * POR_PAGINA + len(itens))
    (saida / ".nojekyll").write_text("")
    n = sum(1 for _ in saida.rglob("*.html"))
    print(f"site gerado em {saida} ({n} páginas)")
    return saida


if __name__ == "__main__":
    gerar()
    sys.exit(0)
