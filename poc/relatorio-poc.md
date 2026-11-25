# Relatório da PoC — Radar Legislativo Joinville
*Coleta em 25/11/2026 · UA `RadarJoinville-PoC/0.1` · 1 requisição a cada 3 s, sem paralelismo · ~98 requisições no total*

> ## ⚠️ ALERTA URGENTE — conformidade
> O `robots.txt` de `camara.joinville.br` diz **`User-agent: *` / `Disallow: /`**: só Google, Bing, Twitter e Facebook podem rastrear, e mesmo eles ficam fora de `/documento(s)`. A coleta das páginas de detalhe desta PoC foi feita **contra o robots.txt**, por decisão consciente do responsável, e deve ser resolvida **antes de qualquer coleta recorrente**. Há um contraponto: a página oficial `/DadosAbertos` oferece CSVs e um índice JSON "para consulta livre e automatizada" (LAI 12.527/2011). Esse canal é legítimo. **Ação:** pedir à Ouvidoria/SIC (ouvidoria@cvj.sc.gov.br) autorização expressa para o UA e a inclusão da *ementa* no CSV.

## Veredito: **GO COM RESTRIÇÕES**
| Critério de GO | Resultado | |
|---|---|---|
| ~100 proposições coletadas automaticamente | **91** (parou no CAPTCHA) | ⚠️ |
| >95% com campos essenciais | **98,9%** (90/91; o 1 que falta deu 404) | ✅ |
| 5/5 conferidas com o site | **Não executada pelo script** (ver Etapa 3) | ❌ pendente |
| Nenhum bloqueio que exija contornar | **CAPTCHA após ~98 requisições** em ~6 min | ❌ |

**Leitura:** coletar é viável e confiável **pelo CSV de Dados Abertos**. Ele é sancionado, vem num arquivo só por ano, com ID, tipo, número, ano, autores com ID, data, situação, protocolo e link oficial. Só **não tem ementa**. A ementa e a tramitação só existem no HTML de cada proposição (1 requisição por item), e esse caminho **ativou um CAPTCHA** e é proibido pelo robots.txt. Por isso não é GO pleno.

## Etapa 3 — números
- **Total:** 91 registros · **duplicatas:** 0 (chave `id_oficial` = sufixo numérico da URL, confirmado pelo campo `Documento.id` do GPS Legislativo).
- **Variedade:** 9 tipos (PL Ordinária 17, PL Complementar 17, Requerimento 16, Pedido de Informação 14, Moção 9, PDL 9, Indicação 5, PR 2, PELO 2) e 21 autores distintos.
- **Falhas de requisição:** 1 HTTP 404 (Requerimento 222/2026: está no CSV, mas a página não existe; ementa ficou `null`) e 1 CAPTCHA (`/documento/projeto-de-lei-ordinaria-no-297-2026-4696144` → `/pages/validar_captcha`). A coleta parou ali.
- **Conferência cruzada offline (CSV oficial × HTML oficial, 90 registros):** título e autores batem em 100%. A **situação diverge em 3** (ex.: Req. 236/2026 aparece como "Aguardando providências" no CSV e "Arquivado" no HTML). A causa provável é o CSV ser um retrato gerado às 03:01, mas **não confirmei** isso.
- **Conferência 5/5 contra a página atual:** não rodei `coleta.py --conferir 5` para não insistir após o CAPTCHA. Os 5 registros abaixo devem ser **conferidos manualmente no navegador**:

| id | proposição | autores | data | situação (CSV / HTML) | link |
|---|---|---|---|---|---|
| 4698118 | Indicação 8778/2026 | Instrutor Lucas | 2026-11-24 | Expediente / Expediente | [link](https://camara.joinville.br/documento/indicacao-no-8778-2026-4698118) |
| 4688546 | PL Ordinária 271/2026 | Instrutor Lucas | 2026-10-21 | Aguard. parecer do relator (iguais) | [link](https://camara.joinville.br/documento/projeto-de-lei-ordinaria-no-271-2026-4688546) |
| 4675605 | PL Complementar 47/2026 | Instrutor Lucas, Tânia Larson | 2026-09-02 | Aguard. parecer do relator (iguais) | [link](https://camara.joinville.br/documento/projeto-de-lei-complementar-no-47-2026-4675605) |
| 4687887 | Requerimento 210/2026 | Dr. Cassiano Ucker, Instrutor Lucas | 2026-10-19 | Arquivado / Arquivado | [link](https://camara.joinville.br/documento/requerimento-no-210-2026-4687887) |
| 4697560 | Requerimento 236/2026 | Mateus Batista | 2026-11-23 | Aguard. providências / **Arquivado** | [link](https://camara.joinville.br/documento/requerimento-no-236-2026-4697560) |

## Disponibilidade
| Dado | Status | Formato / evidência |
|---|---|---|
| Vereadores | **COLETÁVEL** | `DadosAbertos/download/vereadores.csv` (nome, partido, legislaturas, link) |
| Proposições | **COLETÁVEL** (ementa só no HTML) | `documentos-AAAA.csv` + `/documento/<slug>-<id>` |
| Sessões | **COLETÁVEL** | `sessoes-AAAA.csv` + `/sessao/<slug>-<id>` |
| Presença em sessões | **COLETÁVEL** | página da sessão lista Presente/Ausente por vereador ([120ª SO](https://camara.joinville.br/sessao/120a-sessao-ordinaria-2a-sessao-legislativa-20a-legislatura-em-24-de-novembro-de-2026-4273)). O formato do "Relatório de Presença" não foi confirmado |
| Votações (votos individuais) | **COLETÁVEL** | fragmento HTML via AJAX [`/sessao/documento/votacao/133523`](https://camara.joinville.br/sessao/documento/votacao/133523) → "Adilson Girardi favorável … Érico Vinicius Ausente" |
| Localização | **Parcial** | Lat/long estruturados no "GPS Legislativo" (`/documentos/localizacoes/ano:2026`, 2.021 docs em 2026, quase só indicações). **Bairro/rua não têm campo próprio**, aparecem só no texto (na amostra: bairro mencionado em 18 e rua em 15 registros; coordenadas em 5) |
| PDFs (original, texto, atas) | **SÓ ATRÁS DE CAPTCHA** | links passam por `/pages/validar_captcha` e não foram tocados. O texto da proposição está inline no HTML |

## Riscos de manutenção do coletor
1. **Política/acesso:** o robots.txt proíbe o UA, e o CAPTCHA aparece com volume moderado (~100 req em ~6 min). Uma coleta recorrente do HTML pode ser bloqueada a qualquer momento.
2. **Dependência do HTML** para ementa e tramitação: seletores como `.block-text`, `input[name="data[conteudo]"]` e `.item-movimentation` quebram se o Legisoft mudar o layout.
3. **Defasagem do CSV:** o índice diz "semanal", mas os arquivos mostram atualização diária às 03:01, e a situação diverge do HTML em ~3% dos casos.
4. **Votos nominais por proposição:** 51 registros têm sessão com votação, mas o parser **não extraiu** as URLs de votos da página de detalhe (0/51). O formato ali difere do da página da sessão e não foi investigado.

## Próximos passos
1. **Resolver o alerta** com um pedido formal à Ouvidoria/SIC: autorização para o UA e inclusão de ementa e votos no Dados Abertos. Até lá, coletar **só pelos CSVs**.
2. **Desenho incremental:** CSV diário como espinha dorsal; detalhe HTML só para documentos novos ou alterados, poucos por dia; votos e presença a partir da página da sessão (1 requisição por sessão em vez de 1 por proposição).
3. **Fechar as pendências da PoC:** conferir manualmente os 5 registros acima, corrigir a extração de votos na página de detalhe e confirmar o formato do "Relatório de Presença".

**Não confirmado:** conteúdo da Política de Privacidade e se existem termos de uso específicos (não encontrei); o gatilho exato do CAPTCHA (volume? intervalo?); a causa das 3 divergências de situação.
