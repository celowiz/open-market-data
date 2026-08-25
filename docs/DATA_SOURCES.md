# Data Sources

Official access patterns, formats, schedules, and ingestion notes.

Research date: **2026-08-24**. Prefer current official documentation over
historical GitHub READMEs. Outdated assumptions found during planning are
called out explicitly.

Timezone for publication and "safe ingest" clocks is **America/Sao_Paulo**.
GitHub Actions cron uses UTC; document conversions when schedules are added.

HTTP clients must send a clear User-Agent, timeouts, retries, and conditional
GET headers when the source provides ETag / Last-Modified.

---

## Priority

1. Government / official open data
2. Exchange / market infrastructure
3. Official regulatory datasets
4. Other public sources
5. Open-source adapters
6. Non-official aggregators

Initial providers: **CVM, B3, Tesouro Nacional, BCB, Yahoo**.
ANBIMA is a disabled stub.

Custodian prices are out of scope.

---

## CVM — Informe Diário de Fundos

First functional vertical after Foundation.

| Resource | URL |
|---|---|
| Dataset page | https://dados.cvm.gov.br/dataset/fi-doc-inf_diario |
| Rolling 12-month files | https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/ |
| Historical archive | https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/ |
| META dictionary | https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/META/meta_inf_diario_fi.txt |
| Change log | https://dados.cvm.gov.br/pages/novidades |
| Terms | https://dados.cvm.gov.br/about |
| Cadastral data | https://dados.cvm.gov.br/dataset/fi-cad |

### Download URLs

Current monthly ZIP (May 2022+):

```text
https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{YYYY}{MM}.zip
```

Historical yearly ZIP:

```text
https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{YYYY}.zip
```

**Outdated assumption:** many OSS clients still download
`inf_diario_fi_YYYYMM.csv`. Bare CSV URLs return **403**. Always fetch ZIP.

HTTP (non-TLS) URLs are deprecated.

### File format

- Outer: ZIP
- Inner: single CSV `inf_diario_fi_YYYYMM.csv`
- Delimiter: semicolon
- Encoding: ISO-8859-1 / Latin-1
- Dates: `YYYY-MM-DD` in `DT_COMPTC`
- CNPJ: often punctuated

### Schema eras (header is ground truth)

| Era | Period | Identity columns |
|---|---|---|
| A | through 2020 HIST | `CNPJ_FUNDO` |
| B | 2021-01 to 2023-11 | `TP_FUNDO`, `CNPJ_FUNDO` |
| C | 2023-12 to present | `TP_FUNDO_CLASSE`, `CNPJ_FUNDO_CLASSE`, `ID_SUBCLASSE` |

CVM announced the CNPJ_FUNDO_CLASSE rename in October 2024; files already
changed in December 2023. Detect era from the header, not from announcement
dates. META describes the current era only.

Primary field: `VL_QUOTA` → `FUND_NAV`.

Natural key: `(CNPJ_FUNDO_CLASSE, ID_SUBCLASSE, DT_COMPTC)` with
`CNPJ_FUNDO` as backward-compatible alias. Blank subclass → NULL.

### Revisions

Official policy (dataset page):

- Current month and previous month: daily Mon–Sat ~08:00 BRT
- M-2 through M-11: weekly reapresentações
- Rolling window is 12 months; older files live under HIST and are frozen.
  Phase 2 daily ingest uses monthly `DADOS/` ZIPs only. Yearly
  `HIST/inf_diario_fi_{YYYY}.zip` is **Phase 12** backfill.

Administrators have about one business day to file (ICVM 555 Art. 59).
Missing D-1 is not always an error.

**Recommended defaults:**

- Daily job: `recent_reprocess_days = 90` (covers M + M-1 plus lag)
- Weekly reconciliation: 365 days
- `.env.example` currently defaults to `7`; Phase 1/2 should change the
  application default for CVM to 90 while keeping the variable configurable

Re-fetch whole monthly ZIPs and upsert. Do not assume append-only history.

**Outdated OSS policy:** `amgsnt/cvm` still documents M-4..M-11 as monthly.

### Cadastral companion

Legacy `cad_fi.csv` still exists. RCVM 175 structure is
`registro_fundo_classe.zip` (fund / class / subclass). Post-175,
`CNPJ_FUNDO_CLASSE` is class-level. Phase 2 may ingest quotes first and
enrich cadastral data later.

### License

ODbL 1.0. See [`LICENSING.md`](LICENSING.md).

---

## B3

### Current access (2026)

| Channel | Status |
|---|---|
| Pesquisa por Pregão | Primary public BVBG download portal |
| `arquivos.b3.com.br` | Public JSON/token downloads for some files |
| COTAHIST on `bvmf.bmfbovespa.com.br` | Legacy equities EOD, still live |
| FTP `ftp.bmf.com.br` | **Dead — do not use** |
| BVBG.028.01 | **Deprecated — use 028.02** |
| UP2DATA / DataWise+ / UMDF | Paid / participant — not default OSS path |

Pesquisa por Pregão:

```text
https://www.b3.com.br/pesquisapregao/download?filelist={PREFIX}{YYMMDD}.zip
```

Verified prefixes (from Pesquisa por Pregão checkbox `value` attributes,
2026-08-24):

- `PR` → BVBG.086.01 (`PR{YYMMDD}.zip`)
- `IN` → BVBG.028.02 (`IN{YYMMDD}.zip`)
- `IR` → BVBG.087.01 (`IR{YYMMDD}.zip`)
- `SPRE` → BVBG.186.01 (`SPRE{YYMMDD}.zip`)
- `SPRD` → BVBG.187.01 (`SPRD{YYMMDD}.zip`)

Prefixes are not always two letters. Empty or missing files often return HTTP
200 with a 22-byte empty ZIP (`PK\x05\x06`). Reject those; require a local-file
ZIP header (`PK\x03\x04`) and a usable size. A later retry of the same SPRD URL
can still return the empty ZIP even after a successful download.

BVBG.187 inner ZIPs may contain two XML files with the same tickers and
settlement values (near-duplicate payloads). Deduplicate by ticker and
reference date when parsing.

`arquivos.b3.com.br` uses a two-step token download for some listed files.
After EC 007/2025-VTEC (Public Data page deactivated 2026-01-19), OTC taxonomy
names `OTCTradeInformationConsolidated` / `OTCInstrumentsConsolidated` return
HTTP 400. Credit prints are fetched from Boletim Diário table export:

```text
POST https://arquivos.b3.com.br/bdi/table/export
{"Name":"<table>","Date":"YYYY-MM-DD","FinalDate":"YYYY-MM-DD","ClientId":"","Filters":null}
```

Verified table names (2026-08-24): `ConsolidatedRecords` (Negociação
consolidada) and `InstrumentRegistration` (Cadastro de instrumentos). Captcha
was not required for this POST.

Pesquisa por Pregão also lists **Renda Fixa Privada** (`RF{DDMMYY}`). That
bulletin’s `PU_MERCADO` is a reference / model price, not a public print. Do
not ingest it as `LAST`.

### Files to use

| File | Role |
|---|---|
| BVBG.186.01 | Simplified equities EOD (active, not a replacement of 086) |
| BVBG.187.01 | Simplified derivatives EOD |
| BVBG.028.02 | Instrument master at session start |
| BVBG.086.01 | Full price report, three intraday snapshots; use snapshot 03 |
| BVBG.087.01 | Index / BDR / IOPV |
| BDI `ConsolidatedRecords` | OTC credit prints (DEB / CRI / CRA Último Preço) |
| BDI `InstrumentRegistration` | OTC cadastro for the CREDIT universe |
| COTAHIST | Equities **Phase 12** backfill; price-correction flag; no derivative settlement |

Format: XML inside nested ZIP (ISO 20022-style BVMF messages), except COTAHIST
(fixed-width text in ZIP) and BDI OTC tables (JSON from the table export POST).

Publication (trading days, BRT, approximate, OC 040/2025-PRE):

- BVBG.087 ~17:30
- BVBG.186 ~19:00–20:00
- BVBG.086 snapshots ~18:40 / 19:20 / 20:00
- BVBG.187 ~20:00–20:30 (portal listing can appear earlier, around 19:15)
- Option-expiry days can delay last publish ~20:15
- Safe operator clock for 186+187 together: after 20:30 America/Sao_Paulo

186/187 are independently generated and can diverge from 086. Never silently
dedupe them as if they were the same file.

### Semantics

See [`PRICE_SEMANTICS.md`](PRICE_SEMANTICS.md). Equities: `LastPric` → `LAST`.
Derivatives: `AdjstdQt` → `OFFICIAL_SETTLEMENT` (PU). `AdjstdQtTax` is official
rate metadata on the same quote (`unit` documents PU vs percent per year); do
not convert and do not map `LastPric` to settlement.

Phase 8 OTC credit: BDI `ConsolidatedRecords` `Closing` (Último Preço) →
`LAST`. Do not map `ReferencePrice` or RF bulletin `PU_MERCADO` to `LAST`.
BVBG.186 is not the credit file.

Phase 6 persists settlement only for DI1, DOL, WDO, WIN, and IND futures
matching `^(DI1|DOL|WDO|WIN|IND)[FGHJKMNQUVXZ]\d{2}$`. Other 187 products
(options, agricultural futures, FRC/FRO) are deferred. BVBG.028.02 futures
identity lives in `FutrCtrctsInf` (ISIN, `XprtnDt`), not `EqtyInf`.

### License

Treat bulk/public dataset redistribution as denied until B3 license review.
Public API currently serves B3 quotes as `API_ONLY` (no Parquet).

`mercados` currently uses COTAHIST, not full BVBG.186/187. Do not assume that
library already solved B3 EOD.

---

## Tesouro Nacional — Tesouro Direto prices

| Resource | URL |
|---|---|
| Dataset | https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto |
| CKAN API | https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id=taxas-dos-titulos-ofertados-pelo-tesouro-direto |
| CSV (verified live) | CKAN resource download `precotaxatesourodireto.csv` |
| Data Lake REST | `apidatalake.tesouro.gov.br` TD endpoints returned **404** in August 2026 — do not depend on them |

### CSV format

Header:

```text
Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha
```

- Separator `;`, Brazilian decimal comma, dates `DD/MM/YYYY`
- Daily morning snapshot since January 2002
- Identity: map `Tipo Titulo` to `title_type`, plus `Data Vencimento`
- Phase 3 `ingest tesouro --date` keeps only that `Data Base`. Loading the
  full CSV (or a `--start`/`--end` slice) is **Phase 12** `backfill tesouro`.

| Marketing name | title_type |
|---|---|
| Tesouro Selic | LFT |
| Tesouro Prefixado | LTN |
| Tesouro Prefixado com Juros Semestrais | NTN-F |
| Tesouro IPCA+ | NTN-B Principal |
| Tesouro IPCA+ com Juros Semestrais | NTN-B |
| Tesouro IGPM+ com Juros Semestrais | NTN-C (historical) |
| Tesouro Renda+ / Educa+ | NTN-B1 (may need conversion year) |

PYield is **not** the price fetcher for this source (`tpf.taxas` is ANBIMA).

License: ODbL 1.0.

---

## Banco Central do Brasil

| Resource | URL |
|---|---|
| Open data portal | https://dadosabertos.bcb.gov.br |
| SGS JSON | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{CODE}/dados?formato=json` |
| Last N | `.../dados/ultimos/{N}?formato=json` |
| Range | `&dataInicial=DD/MM/YYYY&dataFinal=DD/MM/YYYY` |
| PTAX OData | `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/` |

**Constraint since 2026-03-26:** historical JSON/CSV queries are limited to
**10-year windows**. Backfills must be chunked. Phase 4 ingest still fetches a
single `--date`; multi-year SGS load is **Phase 12** `backfill bcb`.

Avoid legacy SOAP SGS for new code.

### Initial series

| Series | SGS code | Domain |
|---|---|---|
| Selic over | 11 | market series, % per day |
| CDI | 12 | market series, % per day |
| Selic target | 432 | market series, % per year |
| PTAX USD sell | 1 | market series, BRL/USD |
| PTAX USD buy | 10813 | market series, BRL/USD |

Prefer `python-bcb` behind `BcbProvider`. Convert pandas output to Polars /
Decimal at the adapter boundary.

License: ODbL 1.0.

---

## Yahoo Finance

Unofficial. Used only for POC / local coverage of global equities and ETFs
(AAPL, MSFT, SPY, ASML.AS, ...).

Adapter: `yfinance` behind `YahooProvider`.

- EOD field: Close, not Adj Close
- `is_official = false`
- Public API and public datasets disabled until redistribution is reviewed

---

## ANBIMA

Create `AnbimaProvider` as a registered, **disabled** stub.

Do not scrape. Do not bypass access controls. A future
`ManualAnbimaImportProvider` may ingest files obtained legitimately.

PYield and pyettj ANBIMA modules are discovery references only.

---

## Provider schedule notes (later)

Each enabled provider should document:

- expected publication time
- safe ingestion time
- retry strategy

Do not invent a single universal cron hour.

---

## Related documents

- [`OPEN_SOURCE_REVIEW.md`](OPEN_SOURCE_REVIEW.md)
- [`LICENSING.md`](LICENSING.md)
- [`PRICE_SEMANTICS.md`](PRICE_SEMANTICS.md)
