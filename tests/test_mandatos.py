"""Testes com linhas reais dos CSVs oficiais (tests/fixtures). Nenhum teste faz requisição."""
import json
import shutil
from pathlib import Path

import pytest

from mandatos import coletar, config, dados, site
from mandatos.fonte import ClienteLocal, FalhaColeta, ler_csv

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def local(tmp_path):
    """Pasta com índice + CSVs de fixture, nos nomes oficiais."""
    pasta = tmp_path / "oficial"
    pasta.mkdir()
    for f in FIX.glob("*.csv"):
        shutil.copy(f, pasta / f.name)
    base = config.BASE + "/DadosAbertos/download/"
    (pasta / "dados-abertos.json").write_text(json.dumps({
        "ultima_atualizacao": "2026-11-25T00:01:46-03:00",
        "arquivos": [
            {"tipo": "vereadores", "url": base + "vereadores.csv", "ano": None},
            {"tipo": "documentos", "url": base + "documentos-2026.csv", "ano": 2026},
        ]}), encoding="utf-8")
    return pasta


def _coleta(local, destino, **kw):
    return coletar.main(pasta=destino, cliente=ClienteLocal(local), anos=[2026], **kw)


def test_coleta_filtra_proposicoes_de_vereadores(local, tmp_path):
    destino = tmp_path / "dados"
    assert _coleta(local, destino) == 0
    vereadores, props, meta = dados.carregar(destino)
    assert len(vereadores) == 22
    tipos = {p["tipo"] for p in props.values()}
    assert "Resposta" not in tipos and "Designação de relatoria" not in tipos
    # PL do Executivo não entra: nenhum autor é vereador
    assert all(any(a["id"] in {v["id_oficial"] for v in vereadores} for a in p["autores"]) for p in props.values())
    assert meta["total_proposicoes"] == len(props)


def test_registro_fiel_ao_csv(local, tmp_path):
    destino = tmp_path / "dados"
    _coleta(local, destino)
    _, props, _ = dados.carregar(destino)
    r = props["4698118"]
    assert r == {**r, "tipo": "Indicação", "categoria": "melhorias", "numero": "8778", "ano": "2026",
                 "data": "2026-11-24", "situacao": "Expediente", "protocolo": "61339",
                 "autores": [{"nome": "Instrutor Lucas", "id": "213714"}], "ementa": None,
                 "url_origem": "https://camara.joinville.br/documento/indicacao-no-8778-2026-4698118"}
    assert r["coletado_em"]


def test_sem_duplicatas_e_reexecucao_estavel(local, tmp_path):
    destino = tmp_path / "dados"
    _coleta(local, destino)
    antes = (destino / "proposicoes.json").read_text(encoding="utf-8")
    _coleta(local, destino)
    depois = (destino / "proposicoes.json").read_text(encoding="utf-8")
    assert antes == depois  # coletado_em preservado quando nada muda
    ids = [r["id_oficial"] for r in json.loads(depois)]
    assert len(ids) == len(set(ids))


def test_queda_brusca_nao_publica(local, tmp_path):
    destino = tmp_path / "dados"
    _coleta(local, destino)
    original = (destino / "proposicoes.json").read_text(encoding="utf-8")
    # CSV novo com só o cabeçalho e uma linha: deve recusar e manter os dados anteriores
    csvf = local / "documentos-2026.csv"
    linhas = csvf.read_text(encoding="utf-8-sig").splitlines()
    csvf.write_text("\n".join(linhas[:2]) + "\n", encoding="utf-8-sig")
    assert _coleta(local, destino) == 1
    assert (destino / "proposicoes.json").read_text(encoding="utf-8") == original


def test_coluna_ausente_para_a_coleta():
    with pytest.raises(FalhaColeta):
        ler_csv("Título;Tipo\nx;y\n", config.COLUNAS_DOCUMENTOS)


def test_autores_desalinhados_nao_sao_pareados():
    linha = {"Autores": "A, B", "Ids dos Autores": "1"}
    assert dados._autores(linha) == [{"nome": "A", "id": None}, {"nome": "B", "id": None}]


def test_site_gera_paginas_com_links_oficiais(local, tmp_path):
    destino = tmp_path / "dados"
    _coleta(local, destino)
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    index = (saida / "index.html").read_text(encoding="utf-8")
    assert "Instrutor Lucas" in index and "ranking" in index
    pagina = (saida / "vereador" / "instrutor-lucas-213714.html").read_text(encoding="utf-8")
    assert "https://camara.joinville.br/documento/indicacao-no-8778-2026-4698118" in pagina
    assert "Arquivado" in pagina  # aviso sobre o significado da situação
    assert (saida / "como-funciona.html").exists()
