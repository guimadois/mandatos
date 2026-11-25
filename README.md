# mandatos

**Português** · [English](README.en.md)

> `mandatos` é o nome de código do projeto. A marca pública ainda não foi escolhida e fica em um só lugar, `mandatos/config.py` (`MARCA` + `LOCAL`).

Plataforma gratuita que mostra ao cidadão o que cada vereador fez no mandato, usando só dados oficiais. Começa por **Joinville-SC**: pedidos de melhoria, perguntas à Prefeitura, projetos de lei e moções, e cada proposição leva ao documento original na Câmara.

Projeto pessoal de [Guilherme Alberto Moreira dos Santos](https://www.linkedin.com/in/guilherme-alberto-moreira-dos-santos-784185145/). Sem vínculo com a Câmara, partidos ou vereadores.

---

## Estudo de caso

### O problema
Os dados do Legislativo municipal são públicos, mas ficam espalhados num sistema feito para servidores, em linguagem técnica. Em 2026, vários vereadores de Joinville se candidataram a deputado, e o eleitor não tinha um lugar simples para consultar o histórico de cada um. Jornalistas usam portais de "como votou cada parlamentar" para deputados e senadores, mas isso quase não existe no nível municipal.

### A pergunta da prova de conceito
Antes de escrever o produto, uma PoC de poucas horas respondeu uma única pergunta: **dá para coletar automaticamente, de forma confiável e com link para a fonte oficial, as proposições dos vereadores?**

O que ela encontrou:
- **Um portal oficial de Dados Abertos,** com CSVs por ano e um índice JSON oferecidos "para consulta livre e automatizada". Isso mudou a estratégia: passamos a usar a fonte sancionada em vez de raspar páginas.
- **O CSV não tem a ementa** (o resumo da proposição). Ela só existe na página HTML de cada documento.
- **O `robots.txt` proíbe qualquer robô** que não seja dos grandes buscadores. A coleta de ~98 páginas de detalhe, a 1 requisição a cada 3 s, disparou um **CAPTCHA**. A coleta parou automaticamente, sem tentativa de contorno.

| Métrica da PoC | Resultado |
|---|---|
| Proposições coletadas | 91 (a coleta parou no CAPTCHA) |
| Com todos os campos essenciais | 98,9% |
| Duplicatas | 0 |
| CSV × HTML: título e autores | 100% iguais em 90 registros |
| CSV × HTML: situação | 3 divergências (provável defasagem do CSV, não confirmada) |

Veredito: **GO COM RESTRIÇÕES**. O relatório completo está em [`poc/relatorio-poc.md`](poc/relatorio-poc.md).

### Decisões
| Decisão | Por quê |
|---|---|
| **Fonte única: Dados Abertos** (4 requisições/dia) | É o canal autorizado. Coletar HTML fere o `robots.txt` e já foi bloqueado. |
| **Lançar sem ementa** | Melhor publicar menos dado com certeza do que mais dado de forma insustentável. A ementa será pedida à Câmara. |
| **Validar antes de publicar** | Se a Câmara mudar o formato ou o arquivo vier incompleto (colunas, contagem, datas, URLs, queda >10%), nada é publicado e o site fica com a última versão boa. |
| **Site estático + JSON versionado no git** | Custo zero e quase nenhuma manutenção. O histórico do git vira auditoria dos dados. |
| **Nunca deduzir campos** | O CSV lista partidos como histórico ("PL, PROS"), não como partido atual, e lista titulares sem indicar licença. O site mostra exatamente isso, com o rótulo certo. |
| **Explicar "Arquivado"** | 94% das proposições de 2026 estão "Arquivadas", que para a Câmara é só o fim da tramitação. Sem explicação, o morador leria "rejeitado". |
| **Sem ranking** | Ordem alfabética e a mesma regra para todos. Os dados informam; quem julga é o leitor. |

### Arquitetura
```
Dados Abertos da Câmara ──► mandatos.coletar ──► validação ──► dados/*.json ──► mandatos.site ──► GitHub Pages
  (índice JSON + CSVs)      cliente educado:      falhou?        (git)          Jinja2 → HTML
                            3 s, UA próprio,      não publica
                            para em 403/429/CAPTCHA
```
O GitHub Actions roda tudo diariamente às 04:30, depois que a Câmara regera os arquivos às 03:01.

### Números (dados de 2026)
22 vereadores titulares e 10.340 proposições: 8.789 indicações, 1.029 moções, 276 projetos, 163 requerimentos e 83 pedidos de informação.

### Limitações conhecidas
- Sem ementa: os grupos são definidos só pelo tipo do documento, e as moções ainda não separam homenagem de repúdio.
- Presença e votos nominais existem no site da Câmara, mas só em HTML. Aguardam autorização ou inclusão nos Dados Abertos.
- Depois da PoC, a máquina de desenvolvimento passou a receber CAPTCHA até nos Dados Abertos. A coleta em produção (GitHub Actions) ainda precisa ser validada.

### Próximos passos
1. Pedido à Ouvidoria/SIC da Câmara: autorização para o robô e inclusão de ementa, presença e votos nos Dados Abertos.
2. Fase 1 completa: 30 dias estável em produção e, quando autorizado, presença e votos.
3. Expansão: roteiro de viabilidade reaproveitável para outras cidades de SC, depois deputados estaduais, federais e senadores, cujas APIs oficiais já publicam votações nominais.

---

## Rodar localmente

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m mandatos.coletar                                  # baixa os Dados Abertos
.venv/bin/python -m mandatos.coletar --local cache_local --anos 2026  # ou usa arquivos já baixados, sem rede
.venv/bin/python -m mandatos.site                                     # gera _site/
.venv/bin/python -m http.server -d _site 8000 --bind 127.0.0.1        # http://localhost:8000
.venv/bin/python -m pytest -q                                         # testes, sem rede
```

## Publicar
1. Repositório público no GitHub → **Settings → Pages → Source: GitHub Actions**.
2. O workflow [`atualizar.yml`](.github/workflows/atualizar.yml) testa, coleta, valida, grava `dados/` e publica. Se falhar, o GitHub avisa por e-mail.
3. Preencha `REPOSITORIO` e `CONTATO_CORRECAO` em `mandatos/config.py`.

## Estrutura
| Caminho | O que é |
|---|---|
| `mandatos/config.py` | Identidade (marca, autor) e regras editoriais (categorias, legislatura, limites da validação) |
| `mandatos/fonte.py` | Cliente HTTP educado; modo local sem rede |
| `mandatos/dados.py` | CSV → registros, validação, gravação |
| `mandatos/coletar.py` | Coleta diária (CLI) |
| `mandatos/site.py`, `mandatos/templates/` | Gerador do site estático |
| `dados/` | Dados publicados (JSON, um registro por linha) |
| `tests/` | Testes com linhas reais dos CSVs oficiais |
| `poc/` | Prova de conceito: relatório, amostra e coletor |

## Créditos e licença
Inspirado no manual *Como criar o Radar da sua cidade*, de Gabriel Damasceno (Hortolândia-SP). Código sob licença [MIT](LICENSE). Os dados são da Câmara de Vereadores de Joinville.
