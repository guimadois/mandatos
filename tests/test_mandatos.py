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


def test_formato_2025_associa_autor_por_nome_exato(local, tmp_path):
    base = config.BASE + "/DadosAbertos/download/"
    idx = json.loads((local / "dados-abertos.json").read_text(encoding="utf-8"))
    idx["arquivos"].append({"tipo": "documentos", "url": base + "documentos-2025.csv", "ano": 2025})
    (local / "dados-abertos.json").write_text(json.dumps(idx), encoding="utf-8")
    destino = tmp_path / "dados"
    assert coletar.main(pasta=destino, cliente=ClienteLocal(local), anos=[2025, 2026]) == 0
    _, props, _ = dados.carregar(destino)
    de2025 = [p for p in props.values() if p["ano"] == "2025"]
    assert de2025
    tipos = {p["tipo"] for p in de2025}
    assert "Termo de Posse" not in tipos
    for p in de2025:
        assert all(a.get("id_por_nome") for a in p["autores"] if a["id"])
        assert "Poder Executivo (SEI)" not in [a["nome"] for a in p["autores"]] or any(a["id"] for a in p["autores"])
    dupla = [p for p in de2025 if [a["nome"] for a in p["autores"]] == ["Instrutor Lucas", "Wilian Tonezi"]]
    assert dupla and [a["id"] for a in dupla[0]["autores"]] == ["213714", "202230"]
    # comissão (nome com vírgulas) não vira vereador
    assert not any(a["nome"].startswith("Comissão") and a["id"] for p in de2025 for a in p["autores"])


def test_nome_repetido_nao_e_associado():
    m = dados.mapa_nome_para_id([{"nome": "X", "id_oficial": "1"}, {"nome": "X", "id_oficial": "2"},
                                 {"nome": "Y", "id_oficial": "3"}])
    assert m == {"Y": "3"}


def test_vereadores_em_ordem_alfabetica_ignorando_acentos(local, tmp_path):
    """#23: sem ranking, só ordem alfabética. Acentos não empurram nomes para o fim."""
    import re
    destino = tmp_path / "dados"
    _coleta(local, destino)
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    nomes = re.findall(r'<h3><a href="vereador/[^"]+">([^<]+)</a>', (saida / "index.html").read_text(encoding="utf-8"))
    assert len(nomes) == 22
    assert nomes == sorted(nomes, key=dados.chave_alfabetica)
    assert nomes.index("Érico Vinicius") < nomes.index("Franciel Iurko")
    assert nomes.index("Tânia Larson") < nomes.index("Tiago Ronchi")


def test_listas_longas_paginadas(local, tmp_path, monkeypatch):
    """#6: listas viram páginas estáticas com navegação."""
    destino = tmp_path / "dados"
    _coleta(local, destino)
    monkeypatch.setattr(site, "POR_PAGINA", 1)
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    pasta = saida / "vereador" / "instrutor-lucas-213714"
    paginas = {p.name for p in pasta.glob("melhorias*.html")}
    assert "melhorias.html" in paginas and "melhorias-p2.html" in paginas
    p1 = (pasta / "melhorias.html").read_text(encoding="utf-8")
    assert 'rel="next"' in p1 and "melhorias-p2.html" in p1


def test_resumo_da_cidade_conta_cada_proposicao_uma_vez(local, tmp_path):
    """#1: totais da cidade = proposições únicas; #4: proporções somam 100%."""
    destino = tmp_path / "dados"
    _coleta(local, destino)
    vereadores, props, meta = dados.carregar(destino)
    ctx = site.montar_contexto(vereadores, props, meta)
    assert ctx["cidade"]["total"] == len(props)
    assert sum(c["total"] for c in ctx["cidade"]["categorias"]) == len(props)
    assert abs(sum(c["pct"] for c in ctx["cidade"]["composicao"]) - 100) < 1e-6
    for f in ctx["fichas"]:
        if f["total"]:
            assert abs(sum(c["pct"] for c in f["composicao"]) - 100) < 1e-6
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    index = (saida / "index.html").read_text(encoding="utf-8")
    assert "A Câmara em números" in index and "Como ler estes números" in index  # #1 e #9
    assert 'role="img"' in index and "como-funciona.html#situacao" in index


def test_paginas_de_grupo_da_cidade_e_recentes(local, tmp_path):
    """#3: grupos da cidade com filtro por ano; #2: feed de recentes; #5: dados para busca e filtro."""
    import re
    destino = tmp_path / "dados"
    _coleta(local, destino)
    vereadores, props, _ = dados.carregar(destino)
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    for c in config.CATEGORIAS:
        html = (saida / "grupo" / f"{c['chave']}.html").read_text(encoding="utf-8")
        total = sum(1 for p in props.values() if p["categoria"] == c["chave"])
        assert html.count('class="tit"') == min(total, site.POR_PAGINA)
        assert (saida / "grupo" / f"{c['chave']}-2026.html").exists()
    index = (saida / "index.html").read_text(encoding="utf-8")
    assert 'href="grupo/melhorias.html"' in index and 'href="recentes.html"' in index
    assert 'id="busca-nome"' in index and 'data-partidos="|' in index
    recentes = (saida / "recentes.html").read_text(encoding="utf-8")
    assert recentes.count('class="tit"') == min(len(props), site.POR_PAGINA)
    # autoria com link para o perfil do vereador nas páginas da cidade
    assert re.search(r'Autoria: <a href="vereador/[a-z0-9-]+\.html">', recentes)


def test_open_graph_em_todas_as_paginas(local, tmp_path):
    """#7: tags de pré-visualização com URL absoluta e imagem gerada."""
    import re
    destino = tmp_path / "dados"
    _coleta(local, destino)
    saida = site.gerar(saida=tmp_path / "_site", pasta_dados=destino)
    for html in saida.rglob("*.html"):
        s = html.read_text(encoding="utf-8")
        rel = html.relative_to(saida).as_posix()
        assert '<meta property="og:title" content="' in s, rel
        url = re.search(r'<meta property="og:url" content="([^"]+)"', s).group(1)
        esperado = config.SITE_URL + ("" if rel == "index.html" else rel)
        assert url == esperado, rel
    perfil = (saida / "vereador" / "instrutor-lucas-213714.html").read_text(encoding="utf-8")
    desc = re.search(r'<meta property="og:description" content="([^"]+)"', perfil).group(1)
    assert desc.startswith("Instrutor Lucas: ") and "proposições" in desc
    from PIL import Image
    assert Image.open(saida / "og.png").size == (1200, 630)


def test_numeros_com_separador_de_milhar():
    assert site.milhar(4007) == "4.007"
    assert site.milhar(23274) == "23.274"
    assert site.milhar(999) == "999"
    assert site.milhar("1000") == "1.000"
