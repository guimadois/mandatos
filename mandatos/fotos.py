"""Fotos dos vereadores a partir dos Dados Abertos do TSE (Eleições 2024, licença CC BY).

Passo manual, feito uma vez por eleição (as fotos não mudam no dia a dia):

    python -m mandatos.fotos --consulta cache_local/tse/consulta_cand_2024.zip \\
                             --fotos cache_local/tse/foto_cand2024_SC_div.zip

Associa vereador -> candidato só por nome IDÊNTICO (sem acento e sem diferença de maiúsculas),
entre os candidatos a vereador em Joinville: o nome civil da Câmara com o nome do TSE; senão o nome
parlamentar com o nome de urna; senão o nome parlamentar com o nome civil do TSE.
Exceção: os vínculos em config.TSE_VINCULOS_CONFERIDOS, conferidos manualmente pelo autor. Se não houver exatamente um candidato, o vereador
fica sem foto (o site mostra as iniciais). Nada é aproximado.
"""
import argparse
import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import config, dados

LARGURA = 240  # px; exibida a no máximo 120 px (2x para telas de alta densidade)


def norm(s):
    return " ".join(dados.chave_alfabetica(s).split())


def candidatos(consulta_zip, uf, municipio, cargo):
    """Linhas do CSV oficial de candidatos filtradas por UF, município e cargo."""
    with zipfile.ZipFile(consulta_zip) as z:
        nome = f"consulta_cand_{config.TSE_ANO}_{uf}.csv"
        with z.open(nome) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
            return [l for l in leitor
                    if l["NM_UE"] == municipio and l["DS_CARGO"] == cargo]


def associar(vereadores, cands):
    """id_oficial -> (candidato, regra). Só associação única por nome idêntico."""
    por_civil, por_urna = {}, {}
    for c in cands:
        por_civil.setdefault(norm(c["NM_CANDIDATO"]), {})[c["SQ_CANDIDATO"]] = c
        por_urna.setdefault(norm(c["NM_URNA_CANDIDATO"]), {})[c["SQ_CANDIDATO"]] = c
    por_sq = {c["SQ_CANDIDATO"]: c for c in cands}
    out = {}
    for v in vereadores:
        sq = config.TSE_VINCULOS_CONFERIDOS.get(v["id_oficial"])
        if sq:  # decisão do autor, registrada na config; só vale se o candidato for de Joinville
            if sq in por_sq:
                out[v["id_oficial"]] = (por_sq[sq], "conferido manualmente")
            continue
        for regra, mapa, nome in (("nome civil", por_civil, v.get("nome_civil")),
                                  ("nome de urna", por_urna, v.get("nome")),
                                  ("nome parlamentar igual ao nome civil", por_civil, v.get("nome"))):
            achados = list(mapa.get(norm(nome), {}).values()) if nome else []
            if len(achados) == 1:
                out[v["id_oficial"]] = (achados[0], regra)
                break
    return out


def main(consulta_zip, fotos_zip, pasta=dados.PASTA_DADOS):
    vereadores, _, _ = dados.carregar(pasta)
    if not vereadores:
        raise SystemExit("dados/vereadores.json vazio: rode antes  python -m mandatos.coletar")
    cands = candidatos(consulta_zip, config.TSE_UF, config.TSE_MUNICIPIO, "VEREADOR")
    if not cands:
        raise SystemExit("nenhum candidato a vereador de Joinville no arquivo do TSE")
    assoc = associar(vereadores, cands)
    destino = pasta / "fotos"
    destino.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(config.TZ).isoformat(timespec="seconds")
    registros = []
    with zipfile.ZipFile(fotos_zip) as z:
        nomes = {Path(n).name.upper(): n for n in z.namelist()}
        for v in vereadores:
            if v["id_oficial"] not in assoc:
                print(f"sem foto: {v['nome']} (nenhum candidato com nome idêntico)")
                continue
            c, regra = assoc[v["id_oficial"]]
            base = f"F{config.TSE_UF}{c['SQ_CANDIDATO']}_DIV"
            arq = nomes.get(base + ".JPG") or nomes.get(base + ".JPEG")  # o TSE usa as duas extensões
            if not arq:
                print(f"sem foto: {v['nome']} (candidato {c['SQ_CANDIDATO']} sem foto no arquivo do TSE)")
                continue
            img = Image.open(io.BytesIO(z.read(arq))).convert("RGB")
            img.thumbnail((LARGURA, LARGURA * 2))
            img.save(destino / f"{v['id_oficial']}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
            registros.append({
                "id_oficial": v["id_oficial"],
                "arquivo": f"fotos/{v['id_oficial']}.jpg",
                "sq_candidato": c["SQ_CANDIDATO"],
                "nome_tse": c["NM_CANDIDATO"],
                "nome_urna_tse": c["NM_URNA_CANDIDATO"],
                "regra": regra,
                "url_origem": config.TSE_FOTOS_URL,
                "fonte_dados": config.TSE_CONSULTA_URL,
                "coletado_em": agora,
            })
            print(f"ok: {v['nome']} -> {c['NM_URNA_CANDIDATO']} ({regra})")
    ids = {r["id_oficial"] for r in registros}
    for f in destino.glob("*.jpg"):  # foto de quem saiu da lista não fica para trás
        if f.stem not in ids:
            f.unlink()
    (pasta / "fotos.json").write_text(json.dumps(sorted(registros, key=lambda r: r["id_oficial"]),
                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(registros)} de {len(vereadores)} vereadores com foto")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--consulta", required=True, help="consulta_cand_2024.zip do TSE")
    ap.add_argument("--fotos", required=True, help="foto_cand2024_SC_div.zip do TSE")
    a = ap.parse_args()
    sys.exit(main(Path(a.consulta), Path(a.fotos)))
