"""Configuração do projeto. Tudo que é regra editorial ou identidade fica aqui, em um lugar só."""
from zoneinfo import ZoneInfo

# Identidade pública. O nome da marca ainda não foi decidido: troque só aqui.
# Padrão planejado: MARCA + LOCAL ("<Marca> Joinville", "<Marca> SC", "<Marca> Senado").
MARCA = "Mandatos"          # provisório
LOCAL = "Joinville"
NOME_SITE = f"{MARCA} {LOCAL}"
AUTOR = "Guilherme Alberto Moreira dos Santos"
AUTOR_LINKEDIN = "https://www.linkedin.com/in/guilherme-alberto-moreira-dos-santos-784185145/"
REPOSITORIO = "https://github.com/guimadois/mandatos"
SITE_URL = "https://guimadois.github.io/mandatos/"  # endereço público (links absolutos do Open Graph)

BASE = "https://camara.joinville.br"
INDICE_DADOS_ABERTOS = f"{BASE}/DadosAbertos/download/dados-abertos.json"
DOMINIO_PERMITIDO = "camara.joinville.br"

USER_AGENT = "mandatos-bot/0.2 (projeto pessoal de transparência legislativa; coleta só dos Dados Abertos)"
INTERVALO_S = 3.0        # no máximo 1 requisição a cada 3 s
TIMEOUT_S = 60           # os CSVs anuais têm até ~8 MB
MAX_RETENTATIVAS = 2

TZ = ZoneInfo("America/Sao_Paulo")

# Legislatura acompanhada. O site mostra os titulares desta legislatura, como o CSV oficial informa.
LEGISLATURA = "2025 - 2028"
LEGISLATURA_ANO_INICIO = 2025

# Subsídio dos vereadores (#21). Só aparece no site quando valor, lei e link oficial estiverem preenchidos.
# Preencher a partir do texto oficial da lei (e da última lei de revisão anual, se houver). Nunca de notícia.
SUBSIDIO = {
    "valor_mensal": None,       # ex.: 19500.00 (R$, bruto, por vereador)
    "lei": None,                # ex.: "Lei nº 0.000, de 00 de novembro de 2023"
    "lei_url": None,            # link para o texto oficial
    "revisao": None,            # ex.: "Lei nº 0.000/2026 (revisão anual de 3,81%)", se o valor vier de revisão
    "revisao_url": None,
    "valor_presidente": None,   # subsídio de quem preside a Mesa Diretora, se a lei fixar valor próprio
}

# Fotos (#22): Dados Abertos do TSE, Eleições 2024, licença Creative Commons Atribuição (CC BY).
# O site da Câmara não serve: o robots.txt proíbe e não há licença de reuso explícita.
TSE_ANO = 2024
TSE_UF = "SC"
TSE_MUNICIPIO = "JOINVILLE"
TSE_DATASET = "https://dadosabertos.tse.jus.br/dataset/candidatos-2024"
TSE_CONSULTA_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip"
TSE_FOTOS_URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2024/fotos/foto_cand2024_SC_div.zip"
# Vínculos conferidos manualmente pelo autor (id_oficial da Câmara -> SQ_CANDIDATO do TSE), para quem
# o nome não é idêntico nas duas fontes. Cada um foi conferido por nome, partido e candidatura em Joinville.
TSE_VINCULOS_CONFERIDOS = {
    "202219": "240002114189",  # Dr. Cassiano Ucker = DR CASSIANO (Cassiano Gonçalves Ucker, PL)
    "202226": "240001901933",  # Neto Petters = NETO PETTERS DO NOVO (Italmar José Petters Neto, NOVO)
    "213717": "240001901934",  # Vanessa Venzke Falk = VANESSA FALK (Vanessa Cristina Venzke Falk, NOVO)
}
TSE_LICENCA = "Creative Commons Atribuição"  # como o portal do TSE informa, sem versão
TSE_LICENCA_URL = "http://www.opendefinition.org/licenses/cc-by"  # link usado pelo próprio portal

# Colunas que o CSV oficial precisa ter. Se a Câmara mudar o formato, a coleta para e o site não é republicado.
COLUNAS_DOCUMENTOS = ["Título", "Tipo", "Subtipo", "Número", "Ano", "Data", "Situação",
                      "Protocolo", "Link no site"]
# A autoria vem em um de dois formatos, conforme o ano do arquivo:
#  - 2026 em diante: "Autores" + "Ids dos Autores" (nomes e IDs oficiais)
#  - 2025: só "Autoria" (nomes). Associamos ao vereador pelo nome EXATO da lista oficial e marcamos id_por_nome.
FORMATOS_AUTORIA = [["Autores", "Ids dos Autores"], ["Autoria"]]
COLUNAS_VEREADORES = ["Nome", "Nome Civil", "Partidos", "Legislaturas", "Link no site"]

# Categorias cidadãs PROVISÓRIAS: definidas só pelo tipo oficial do documento, porque o CSV não traz a ementa.
# A mesma regra vale para todos os vereadores e é publicada na página "Como funciona".
CATEGORIAS = [
    {
        "chave": "melhorias",
        "nome": "Pedidos de melhoria",
        "explicacao": "Indicações: o vereador sugere à Prefeitura uma obra ou serviço, como asfalto, "
                      "iluminação ou poda. É um pedido, não uma obra feita.",
        "subtipos": ["Indicação"],
    },
    {
        "chave": "perguntas",
        "nome": "Perguntas e cobranças",
        "explicacao": "Pedidos de informação: o vereador pergunta oficialmente algo à Prefeitura, "
                      "que deve responder.",
        "subtipos": ["Pedido de Informação"],
    },
    {
        "chave": "leis",
        "nome": "Propostas de lei",
        "explicacao": "Projetos de lei, de decreto legislativo, de resolução e propostas de emenda à "
                      "Lei Orgânica. Projeto apresentado não é lei aprovada.",
        "subtipos": ["Projeto de Lei Ordinária", "Projeto de Lei Complementar",
                     "Projeto de Decreto Legislativo", "Projeto de Resolução",
                     "Proposta de Emenda à Lei Orgânica"],
    },
    {
        "chave": "mocoes",
        "nome": "Moções",
        "explicacao": "Manifestações da Câmara: na maioria homenagens e parabéns, mas também apoio, "
                      "pesar ou repúdio. Sem a ementa no dado aberto, ainda não dá para separar.",
        "subtipos": ["Moção"],
    },
    {
        "chave": "requerimentos",
        "nome": "Requerimentos",
        "explicacao": "Pedidos feitos à própria Câmara, como urgência, retirada de projeto ou "
                      "sessão especial.",
        "subtipos": ["Requerimento"],
    },
]
SUBTIPO_PARA_CATEGORIA = {s: c["chave"] for c in CATEGORIAS for s in c["subtipos"]}

# Validação antes de publicar
MIN_VEREADORES = 15
MAX_VEREADORES = 40
QUEDA_MAXIMA = 0.10      # se um ano perder mais de 10% das proposições de um dia para o outro, não publica

# Canal de correção (preencher antes de publicar o site)
CONTATO_CORRECAO = "https://github.com/guimadois/mandatos/issues"
