"""Coleta diária:  python -m mandatos.coletar

Baixa só os Dados Abertos da Câmara (índice JSON + CSVs), valida e grava em dados/.
Se algo vier estranho, sai com erro e NÃO altera dados/: o site fica com a última versão boa.
"""
import sys
from datetime import datetime

from . import config, dados
from .fonte import Bloqueio, Cliente, ClienteLocal, FalhaColeta


def main(pasta=dados.PASTA_DADOS, cliente=None, anos=None):
    cli = cliente or Cliente()
    if hasattr(cli, "momento_coleta"):  # download manual: vale a hora em que os arquivos foram baixados
        agora = cli.momento_coleta(config.TZ)
    else:
        agora = datetime.now(config.TZ).isoformat(timespec="seconds")
    try:
        indice = cli.indice()
        arquivos = indice.get("arquivos") or []
        url_ver = next(a["url"] for a in arquivos if a.get("tipo") == "vereadores")
        ano_atual = datetime.now(config.TZ).year
        anos = list(anos or range(config.LEGISLATURA_ANO_INICIO, ano_atual + 1))
        docs = {a["ano"]: a["url"] for a in arquivos if a.get("tipo") == "documentos" and a.get("ano") in anos}
        faltando = [a for a in anos if a not in docs]
        if faltando:
            raise FalhaColeta(f"índice sem documentos de {faltando}")

        vereadores = dados.montar_vereadores(cli.csv(url_ver, config.COLUNAS_VEREADORES))
        ids = {v["id_oficial"] for v in vereadores}
        nome_para_id = dados.mapa_nome_para_id(vereadores)
        proposicoes = {}
        for ano in sorted(docs):
            linhas = cli.csv(docs[ano], config.COLUNAS_DOCUMENTOS)
            proposicoes.update(dados.montar_proposicoes(linhas, ids, docs[ano], agora, nome_para_id))

        _, anteriores, _ = dados.carregar(pasta)
        dados.preservar_coletado_em(proposicoes, anteriores)
        dados.validar(vereadores, proposicoes, anteriores)
    except (Bloqueio, FalhaColeta, dados.DadosInvalidos, StopIteration, KeyError, ValueError) as e:
        print(f"COLETA NÃO PUBLICADA ({type(e).__name__}): {e}", file=sys.stderr)
        return 1

    meta = {
        "coletado_em": agora,
        "dados_abertos_atualizados_em": indice.get("ultima_atualizacao"),
        "fontes": [config.INDICE_DADOS_ABERTOS, url_ver, *[docs[a] for a in sorted(docs)]],
        "legislatura": config.LEGISLATURA,
        "total_vereadores": len(vereadores),
        "total_proposicoes": len(proposicoes),
        "requisicoes": cli.requisicoes,
        "modo": "manual" if hasattr(cli, "momento_coleta") else "automatico",
    }
    dados.salvar(pasta, vereadores, proposicoes, meta)
    print(f"ok: {len(vereadores)} vereadores, {len(proposicoes)} proposições, {cli.requisicoes} requisições")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local", help="pasta com os arquivos oficiais já baixados (não faz requisições)")
    ap.add_argument("--anos", type=int, nargs="+", help="anos de documentos (padrão: legislatura até hoje)")
    a = ap.parse_args()
    sys.exit(main(cliente=ClienteLocal(a.local) if a.local else None, anos=a.anos))
