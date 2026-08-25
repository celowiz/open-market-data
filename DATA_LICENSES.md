# Data Licenses

This file tracks **data** terms. Source-code terms are in [`LICENSE`](LICENSE)
(Apache-2.0; added in Phase 1) and [`docs/LICENSING.md`](docs/LICENSING.md).

Last reviewed: **2026-08-24**. Status values are operational, not legal advice.
If a field is uncertain, set it to `UNKNOWN` and keep public redistribution off.

| Source | Data owner | Official? | Terms URL | Data license | Automated access allowed? | Redistribution allowed? | Commercial reuse allowed? | Attribution required? | Public API allowed? | Bulk dataset redistribution allowed? | Status | Last reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CVM Informe Diário | CVM | yes | https://dados.cvm.gov.br/about | ODbL-1.0 | yes, respectful / may throttle | yes, ODbL conditions | yes, ODbL conditions | yes | yes | yes | `PUBLIC_WITH_ATTRIBUTION` | 2026-08-24 |
| Tesouro Direto prices (CKAN) | Tesouro Nacional / STN | yes | CKAN dataset + ODbL | ODbL-1.0 | yes | yes, ODbL conditions | yes, ODbL conditions | yes | yes | yes | `PUBLIC_WITH_ATTRIBUTION` | 2026-08-24 |
| BCB SGS / PTAX / dados abertos | Banco Central do Brasil | yes | https://dadosabertos.bcb.gov.br | ODbL-1.0 | yes, throttle conservatively | yes, ODbL conditions | yes, ODbL conditions | yes | yes | yes | `PUBLIC_WITH_ATTRIBUTION` | 2026-08-24 |
| B3 EOD files (BVBG, COTAHIST, arquivos.b3) | B3 S.A. | yes | B3 Market Data Consumption Policy; OC 104/2025-PRE | UNKNOWN (proprietary market data policy) | website downloads exist; legally gray for products | UNKNOWN; default no bulk | UNKNOWN; default no | n/a until licensed | yes, `API_ONLY` (temporary operational choice) | no | `API_ONLY` / no Parquet | 2026-08-24 |
| Yahoo Finance (via yfinance) | Yahoo / exchanges | no | Yahoo terms; yfinance is not a data license | UNKNOWN | unofficial client | UNKNOWN; default no | UNKNOWN; default no | n/a | no | no | `UNKNOWN` / POC only | 2026-08-24 |
| ANBIMA | ANBIMA | yes | not reviewed — provider disabled | UNKNOWN | do not scrape | no | no | n/a | no | no | disabled | 2026-08-24 |

## Attribution snippets (ODbL sources)

Use these (or equivalent) on dataset manifests and API documentation when
publishing derived databases:

- CVM: data from Portal de Dados Abertos CVM, https://dados.cvm.gov.br/
- Tesouro: data from Tesouro Transparente / Tesouro Nacional
- BCB: data from Banco Central do Brasil open data / SGS / PTAX

Derivative databases published from these sources must remain under ODbL
share-alike as required by that license.

The committed `config/instruments.example.csv` lists tickers for a coverage
experiment. It is not an official index product and must not be treated as
redistribution of S&P, Nasdaq, Dow, or B3 index membership data.

## Review cadence

Re-check this table when:

- enabling a source for public API or Parquet
- a source announces new terms
- adding fixtures copied from real files
