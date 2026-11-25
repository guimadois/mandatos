# mandatos: regras do projeto

`mandatos` é o nome de código (repositório e pacote Python). A marca pública ainda não foi decidida e fica só em `mandatos/config.py` (`MARCA`, `LOCAL`). Visão: começar por Joinville, depois outras cidades de SC (com roteiro de viabilidade), depois deputados estaduais, federais e senadores. Manter o núcleo separado da fonte de cada casa legislativa.

Visão e decisões: doc "Radar Joinville — a ideia do portal" (Claude Docs), seção "Decisões e limites".

## Regras de dados (não negociáveis)
- Só dados oficiais da Câmara, sempre com `url_origem` e `coletado_em`. Nunca inventar, completar ou deduzir campos: o que falta fica `None`.
- Coletar **apenas** os Dados Abertos (`/DadosAbertos/download/...`). As páginas HTML (`/documento`, `/sessao`) são proibidas pelo robots.txt. Não coletar HTML sem decisão explícita do autor, que depende da resposta da Ouvidoria.
- No máximo 1 requisição a cada 3 s, User-Agent identificado. Em 403, 429, CAPTCHA ou login: parar e avisar, nunca contornar.
- Validar antes de publicar. Se falhar, o site fica com a última versão boa.

## Regras editoriais
- Mesma regra para todos os vereadores; vereadores em ordem alfabética; sem nota, ranking ou opinião.
- Não confundir etapas: pedido não é obra, projeto não é lei, "Arquivado" não é rejeitado.
- O que for estimativa ou classificação automática aparece marcado como tal.

## Escopo atual (fase 1)
- Só a legislatura 2025–2028. Proposições pelo CSV, sem ementa.
- Presença e votos só depois da Ouvidoria. Uso de IA para classificar: em aberto.
- Nunca escrever o nome da marca direto em templates ou textos: usar `nome_site`, `marca` e `local` da config.

## Comandos
- `python -m mandatos.coletar` (ou `--local cache_local --anos 2026` sem rede)
- `python -m mandatos.site` gera `_site/`
- `python -m pytest -q`
