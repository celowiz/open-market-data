# Licensing

Code licensing and data licensing are separate concerns.

The Apache License 2.0 covers this repository's source code. It does **not**
grant rights to redistribute third-party market data consumed by the software.

When redistribution rights are unclear, the default is no public redistribution.

Per-source legal tracking lives in [`DATA_LICENSES.md`](../DATA_LICENSES.md).
That file must be updated when a source is enabled for public API or datasets.

---

## Source code

Initial decision: **Apache License 2.0**. See
[`adr/0008-source-code-license.md`](adr/0008-source-code-license.md).

Dependency constraints that affect this choice:

- `mercados` is LGPL-3.0. Using it as a dynamically linked/installable library
  behind adapters is acceptable if we ship license notices and do not statically
  embed or copy substantial portions. See
  [`adr/0009-mercados-adapter.md`](adr/0009-mercados-adapter.md).
- `securo` and `OpenBB` are AGPL-3.0. They must not be dependencies and their
  code must not be copied.
- `amgsnt/cvm` is GPL-3.0 and stale. Do not depend on it.

---

## Redistribution policy enum

Each `sources` row has `redistribution_policy`:

| Value | Meaning |
|---|---|
| `PUBLIC` | Redistribution allowed without special attribution beyond ordinary citation |
| `PUBLIC_WITH_ATTRIBUTION` | Public API and datasets allowed if attribution (and share-alike, if any) is honored |
| `API_ONLY` | May appear in the API but not as bulk datasets |
| `INTERNAL_ONLY` | Ingestion allowed; not for public API or datasets |
| `NO_REDISTRIBUTION` | Must not be published |
| `UNKNOWN` | Treated as deny until reviewed |

Publication code must refuse to emit public API payloads or Parquet files unless
the policy is an allowed public value. Do not rely on developers remembering.

Capability flags are independent:

```text
ingestion_enabled
public_api_enabled
public_dataset_enabled
```

---

## Initial source classification

Validated August 2026 against official portals. This is not legal advice.

### CVM Dados Abertos (Informe Diário)

- Owner: CVM
- Official: yes
- Data license: Open Data Commons ODbL 1.0
- Terms: https://dados.cvm.gov.br/about
- Dataset: https://dados.cvm.gov.br/dataset/fi-doc-inf_diario
- Automated access: allowed with respectful use; CVM may throttle robots
- Redistribution: **`PUBLIC_WITH_ATTRIBUTION`**
- Obligations: attribution to Portal de Dados Abertos CVM; ODbL share-alike on
  derivative databases
- Public API: allowed with attribution
- Bulk datasets: allowed with attribution and ODbL compliance

### Tesouro Transparente (Tesouro Direto prices)

- Owner: Tesouro Nacional / STN / CODIP
- Official: yes
- Data license: ODbL 1.0 (`odc-odbl` on CKAN)
- Dataset: https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto
- Redistribution: **`PUBLIC_WITH_ATTRIBUTION`**
- Obligations: attribution to Tesouro Nacional/STN; ODbL share-alike on
  derivative databases

### Banco Central do Brasil (SGS / PTAX / dados abertos)

- Owner: Banco Central do Brasil
- Official: yes
- Data license: ODbL 1.0 on dadosabertos.bcb.gov.br
- Portal: https://dadosabertos.bcb.gov.br
- Redistribution: **`PUBLIC_WITH_ATTRIBUTION`**
- Obligations: attribution to BCB; ODbL share-alike on derivative databases

### B3

- Owner: B3 S.A.
- Official: yes
- Access: public website files exist (Pesquisa por Pregão, arquivos.b3.com.br,
  COTAHIST). FTP is dead.
- Market Data B3 Consumption Policy effective 2026-01-01 treats EOD files as
  Market Data. Distribution, product development, and storage for commercial
  datasets/APIs generally require B3 licenses.
- Redistribution: **`UNKNOWN`** for bulk datasets; operational public API is
  **`API_ONLY`** (temporary). `public_dataset_enabled` stays false.
- Ingestion sets `public_api_enabled=true`, `redistribution_policy=API_ONLY`,
  `public_dataset_enabled=false`. Re-run `marketdata ingest b3` to update an
  existing `sources` row.
- See [`adr/0014-b3-redistribution.md`](adr/0014-b3-redistribution.md). Bulk
  Parquet remains blocked until a license is confirmed. Lending snapshots follow
  the same `API_ONLY` source flags as B3 quotes. NEGOCIOSBTB parquet is not
  published unless object storage is `s3`.

### FRED / IBGE / CFTC / SEC 13F

- FRED: official public API; attribution required; allowlist only.
- IBGE SIDRA: CC-BY; IPCA only in this milestone.
- CFTC public reporting: public domain / attribution; allowlisted contracts.
- SEC 13F: public EDGAR; persist only CUSIP-mapped scratch holdings.

### Yahoo Finance via yfinance

- Code license of `yfinance`: Apache-2.0
- Data owner: Yahoo / underlying exchanges
- Official: no
- Redistribution: **`UNKNOWN`**
- Flags: `ingestion_enabled` may be true for POC; `public_api_enabled=true`
  (temporary operational choice); `public_dataset_enabled=false`
  `public_dataset_enabled=false`
- Enforce in code, not only in docs. See
  [`adr/0013-yahoo-gating.md`](adr/0013-yahoo-gating.md).

`config/instruments.example.csv` US ticker lists are a **coverage experiment
snapshot**, not redistribution of S&P / Nasdaq / Dow index constituent products.
B3 IBOV/SMLL rows snapshot B3 theoretical-portfolio tickers; they are not a
licensed index feed. See [`COVERAGE.md`](COVERAGE.md).

### ANBIMA

- Provider stub exists conceptually with `enabled=false`
- No scraping, no access bypass
- Redistribution: **`UNKNOWN`** / disabled

---

## ODbL practical notes

For CVM, Tesouro, and BCB public products:

- Cite the source on API docs, dataset manifests, and README examples.
- Treat published Parquet collections derived from those databases as ODbL
  databases: share-alike applies to the database, not automatically to our
  Apache-2.0 code.
- Do not mix ODbL series and non-redistributable series in the same published
  dataset file.

Phase 9 publishes CVM, Tesouro, and BCB as Parquet. Attribution snippets live
in each dataset manifest (`public/manifests/{name}-latest.json`) and in
[`DATASETS.md`](DATASETS.md). B3 and Yahoo are not published.

---

## Fixtures

Test fixtures must respect the same redistribution rules.

Prefer synthetic files that match official schemas. Small CVM/Tesouro/BCB
samples may be included with attribution when ODbL allows. Do not commit B3 or
Yahoo bulk extracts into the public repo until redistribution is cleared.
