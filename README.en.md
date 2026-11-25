# mandatos

[Português](README.md) · **English**

> `mandatos` ("mandates") is the project's code name. The public brand hasn't been chosen yet and lives in a single place, `mandatos/config.py` (`MARCA` + `LOCAL`).

A free civic-tech platform that shows citizens what each city councillor did in office, using official data only. It starts with **Joinville, Brazil**: improvement requests, questions to the mayor's office, bills and motions. Every item links to the original document on the City Council website. The site itself is in Portuguese.

Personal project by [Guilherme Alberto Moreira dos Santos](https://www.linkedin.com/in/guilherme-alberto-moreira-dos-santos-784185145/), with no ties to the City Council, political parties or councillors.

---

## Case study

### The problem
Municipal legislative data in Brazil is public, but it sits in back-office systems written in legal jargon. In 2026 several Joinville councillors ran for state and federal office, and voters had no simple place to check their record. Journalists use "how each legislator voted" portals for federal congress members, but almost nothing like that exists at city level.

### The proof-of-concept question
Before writing any product code, a time-boxed PoC (≈4 hours) answered one question: **can councillors' bills be collected automatically, reliably, and with a link back to the official source?**

What it found:
- **An official Open Data portal** with yearly CSVs and a JSON index explicitly offered "for free and automated use". This changed the strategy from scraping pages to using the sanctioned source.
- **The CSV lacks the bill summary** (*ementa*), which only exists on each document's HTML page.
- **`robots.txt` disallows every crawler except major search engines.** Fetching ~98 detail pages at 1 request every 3 s triggered a **CAPTCHA**. The collector stopped by design, and there was no attempt to bypass it.

| PoC metric | Result |
|---|---|
| Records collected | 91 (stopped at the CAPTCHA) |
| With all essential fields | 98.9% |
| Duplicates | 0 |
| CSV vs. HTML: title and authors | 100% match across 90 records |
| CSV vs. HTML: status | 3 mismatches (likely CSV lag, not confirmed) |

Verdict: **GO WITH RESTRICTIONS**. The full report (in Portuguese) is in [`poc/relatorio-poc.md`](poc/relatorio-poc.md).

### Key decisions
| Decision | Why |
|---|---|
| **Single source: the Open Data files** (4 requests/day) | It is the authorized channel. Scraping HTML goes against `robots.txt` and had already been blocked. |
| **Ship without bill summaries** | Better to publish less data with certainty than more data in an unsustainable way. The summaries will be requested from the Council. |
| **Validate before publishing** | If the source format changes or a file arrives incomplete (columns, counts, dates, URLs, a drop above 10%), nothing is published and the site keeps the last good version. |
| **Static site + JSON versioned in git** | Zero hosting cost and minimal maintenance. Git history doubles as a data audit trail. |
| **Never infer fields** | The CSV lists a party *history* ("PL, PROS"), not the current party, and lists elected members without saying who is on leave. The site shows exactly that, with honest labels. |
| **Explain "Arquivado" (archived)** | 94% of 2026 records are "archived", which only means the procedure ended at the Council. Without context, residents would read it as "rejected". |
| **No rankings** | Alphabetical order and the same rule for everyone. The data informs; the reader judges. |

### Architecture
```
Council Open Data ──► mandatos.coletar ──► validation ──► dados/*.json ──► mandatos.site ──► GitHub Pages
(JSON index + CSVs)   polite client:       fails?          (git)           Jinja2 → HTML
                      3 s, named UA,       don't publish
                      stops on 403/429/CAPTCHA
```
GitHub Actions runs the whole pipeline daily at 04:30 local time, after the Council regenerates its files at 03:01.

### Numbers (2026 data)
22 elected councillors and 10,340 bills: 8,789 improvement requests, 1,029 motions, 276 bills of law, 163 procedural requests and 83 information requests.

### Known limitations
- No bill summaries yet, so categories rely on the official document type only, and motions still mix tributes with protests.
- Attendance and roll-call votes exist on the Council website, but only as HTML. They wait for authorization or for inclusion in the Open Data files.
- **Automated collection is currently blocked.** Since the PoC, the Council requires a CAPTCHA even to download the Open Data files, including from GitHub Actions. The bot tries once a day, stops at the CAPTCHA without bypassing it, and keeps the site on the last good data (2026 CSV, from Nov 25, 2026). The issue will be raised with the Council's ombudsman.

### Roadmap
1. Formal request to the Council's ombudsman: authorization for the bot, plus bill summaries, attendance and votes in the Open Data files.
2. Phase 1 complete: 30 days stable in production and, once authorized, attendance and votes.
3. Expansion: a reusable feasibility playbook for other cities in Santa Catarina, then state and federal legislators, whose official APIs already publish roll-call votes.

## Stack
Python 3.12 · requests · Jinja2 · pytest · GitHub Actions · GitHub Pages. No database, no server, no tracking, no third-party fonts.

## Run locally
See [README.md](README.md#rodar-localmente); the commands are the same.

## Credits and license
Inspired by the guide *Como criar o Radar da sua cidade* by Gabriel Damasceno (Hortolândia, Brazil). Code under the [MIT](LICENSE) license. Data © Câmara de Vereadores de Joinville.
