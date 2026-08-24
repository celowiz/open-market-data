# Open-Source Review

Review date: **2026-08-24**.

This project may use libraries **only behind provider adapters**. Domain, API,
and storage code must not import them.

Do not copy code without evaluating license. AGPL projects are reference-only.

| Project | Purpose | Language | License | Active? | Useful components | Use as dependency? | Use as reference? | Risks |
|---|---|---|---|---|---|---|---|---|
| [PythonicCafe/mercados](https://github.com/PythonicCafe/mercados) | BR official fetch/parse (CVM, BCB, STN, B3, IBGE, FundosNet) | Python ≥3.11 | LGPL-3.0 | Yes (pushed 2026-08; PyPI 0.2.0, pre-1.0) | Source modules, CLI, endpoint catalog | **Yes**, adapter backend | Yes | Pre-1.0 API; LGPL notices; B3 BVBG not fully implemented; Portuguese API surface |
| [crdcj/PYield](https://github.com/crdcj/PYield) | Brazilian fixed income: calendar, DI, TPF math, Selic/IPCA/PTAX helpers | Python ≥3.12 | MIT | Yes (PyPI 0.56.x) | `du` calendar, bond PU engines, DI helpers | **Yes**, optional RF helpers | Yes | API churn; `tpf.taxas` is **ANBIMA**, not Tesouro Direto CSV |
| [wilsonfreitas/python-bcb](https://github.com/wilsonfreitas/python-bcb) | BCB SGS, PTAX, Expectativas, OData | Python ≥3.10 | MIT | Yes (PyPI 0.4.0) | `bcb.sgs`, `bcb.PTAX` | **Yes**, preferred BCB client | Yes | pandas DataFrames; overlap with `mercados.bcb` |
| [eduresser/cvm-sqlite](https://github.com/eduresser/cvm-sqlite) | CVM datasets → SQLite | Python | MIT | Moderate (2026-03) | META-driven download ideas | **No** | Yes | SQLite serving model conflicts with PostgreSQL architecture |
| [securo-finance/securo](https://github.com/securo-finance/securo) | Personal finance app with Tesouro CSV provider | Python + TS | AGPL-3.0 | Yes | Tesouro CSV URL, Decimal parsing, title+maturity identity | **No** | Yes — patterns only, **do not copy code** | AGPL network copyleft |
| [hugorteixeira/brfutures](https://github.com/hugorteixeira/brfutures) | B3 futures bulletins / BVBG XML | R | Unspecified | Niche (2026-07) | BVBG.028/187, AdjstdQt | **No** | Yes for derivatives ingestion design | Wrong language; unclear license |
| [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | Unofficial Yahoo EOD | Python | Apache-2.0 (code) | Yes | `Ticker.history` | **Yes**, Yahoo adapter only | Yes | Yahoo **data** redistribution unknown; scraping fragility |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | Large multi-provider platform | Python | AGPL-3.0 | Yes | Provider registry patterns | **No** | Limited | AGPL; over-scoped |
| [rafa-rod/pyettj](https://github.com/rafa-rod/pyettj) | Brazilian ETTJ curves | Python | MIT | Moderate | ANBIMA/B3 curve fetch | Later / optional | Yes | ANBIMA licensing; beyond quote MVP |
| [joaopm33/fundspy](https://github.com/joaopm33/fundspy) | CVM quotas → SQLite + analytics | Python | MIT | Stale (2022) | Legacy CVM URLs | **No** | Legacy schema only | Bare CSV URLs broken; `CNPJ_FUNDO` only |
| [thobiast/fundosbr](https://github.com/thobiast/fundosbr) | CVM fund info script | Python | MIT | Stale (2021) | Minimal | **No** | Minimal | CSV not ZIP; http:// URLs |
| [amgsnt/cvm](https://github.com/amgsnt/cvm) | CVM quota downloader | Python + shell | GPL-3.0 | Stale (2020) | Historical URL notes | **No** | Minimal | GPL; CSV 403; obsolete reprocess policy |

---

## Primary reference: mercados

Useful for CVM, STN, B3 COTAHIST, and some BCB/IBGE paths.

Required usage:

```text
marketdata/providers/cvm.py  → may call mercados
marketdata/domain/*          → never imports mercados
```

Do not copy SSL `verify=False` patterns if present.

LGPL-3.0: ship license text, NOTICE, and keep mercados replaceable as a
separate package. Do not vendor/fork substantial LGPL code into Apache files
without compliance.

BVBG.186/187 downloads are still largely an open gap in community libraries.
Phase 5 cannot assume mercados already solved B3 official settlement files.

---

## PYield

Use for Brazilian business calendar, PU validation, and DI conventions.

Do **not** use as Tesouro Direto or BCB primary fetcher:

- Tesouro prices: CKAN CSV
- BCB series: python-bcb

ANBIMA-sourced PYield outputs follow the ANBIMA disablement policy.

---

## python-bcb

Preferred HTTP client for SGS and PTAX OData. Adapter must:

- chunk history into ≤10-year windows
- convert to Decimal + explicit unit
- preserve raw JSON when useful for artifacts

---

## AGPL exclusion

Do not `pip install` or copy:

- securo-finance/securo
- OpenBB-finance/OpenBB

Reading public code for ideas is allowed. Reimplement independently.

---

## Recommended adapter mapping

```text
CvmProvider      → httpx and/or mercados.cvm (verify ZIP support first)
B3Provider       → custom BVBG + optional mercados COTAHIST backfill
TesouroProvider  → httpx CKAN CSV; PYield optional validation only
BcbProvider      → python-bcb
YahooProvider    → yfinance (public flags off)
AnbimaProvider   → disabled stub
```

---

## Related ADRs

- [`adr/0008-source-code-license.md`](adr/0008-source-code-license.md)
- [`adr/0009-mercados-adapter.md`](adr/0009-mercados-adapter.md)
- [`adr/0013-yahoo-gating.md`](adr/0013-yahoo-gating.md)
