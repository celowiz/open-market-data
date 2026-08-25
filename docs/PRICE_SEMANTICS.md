# Price Semantics

Financial values in this project are typed. A number without a `price_type` is
incomplete. Different semantics must never be silently converted into each other.

Persisted values use exact decimals. JSON responses should serialize them as
strings (or an equivalent decimal-safe encoding), not IEEE floats.

---

## Observation kinds

| Kind | Typical price types | Examples |
|---|---|---|
| Instrument quote | `LAST`, `FUND_NAV`, `OFFICIAL_SETTLEMENT`, `PU_BASE` | PETR4, fund cota, DI1, Tesouro LTN |
| Market series observation | `REFERENCE` | CDI, Selic, PTAX |
| Curve point | deferred | ETTJ vertices |

`VL_PATRIM_LIQ` is fund net assets, not a unit price. It may be stored in
metadata or a non-price field, never as `FUND_NAV`.

---

## Price type enum (initial)

| Value | Meaning |
|---|---|
| `CLOSE` | Official or vendor-defined closing price when that concept exists as a distinct field |
| `LAST` | Last trade of the session |
| `LAST_TRADE` | Alias reserved only if a source truly distinguishes last trade from `LAST`. Prefer `LAST` for new mappings |
| `OFFICIAL_SETTLEMENT` | Exchange official settlement / ajuste |
| `ADJUSTMENT` | Corporate-action or contract adjustment factor (out of MVP scope) |
| `PU_BASE` | Tesouro Direto official base PU for the day |
| `FUND_NAV` | Fund unit value / cota (`VL_QUOTA`) |
| `INDICATIVE` | Indicative quote that is not an official close or settlement |
| `BID_PU` | Tesouro Direto morning buy-side PU |
| `ASK_PU` | Tesouro Direto morning sell-side PU |
| `YIELD` | Annualized rate associated with a bond quote, not a price |
| `REFERENCE` | Official reference series value (Selic, CDI, PTAX) |

Do not invent a silent `canonical_quote` heuristic in the MVP. If B3 and Yahoo
both have a PETR4-like observation, the API can return both, filtered by
`source` and `price_type`.

---

## Source mappings

These mappings were validated against current official files and APIs in
August 2026. Older open-source clients often get them wrong.

### CVM Informe Diário

- `VL_QUOTA` → `FUND_NAV` (primary valuation field)
- `VL_PATRIM_LIQ` → not a unit price
- `VL_TOTAL` → portfolio total, not NAV
- Currency: BRL
- Precision: CVM documents `VL_QUOTA` as numeric(27,12). Persist enough
  decimal places; do not round to cents.

### B3 equities (BVBG.186 / BVBG.086)

- `FrstPric` → open
- `MaxPric` / `MinPric` → high / low
- `LastPric` → `LAST`
- `ClsgPric` is **not** present in BVBG.186/086. It appears in BVBG.087 for
  indices / BDR IOPV-style reports.

B3 communications sometimes call `LastPric` "preço de fechamento". The message
catalog defines it as último negócio (last trade). This project stores it as
`LAST`, not as a fabricated auction close, and never as split-adjusted close.

Corporate actions are out of MVP scope. Do not produce Adjusted Close.

### B3 derivatives (BVBG.187 / BVBG.086)

- `AdjstdQt` → `OFFICIAL_SETTLEMENT` (PU)
- `AdjstdQtTax` → `OFFICIAL_SETTLEMENT` with unit documenting that the value is
  an annualized rate (DI1)
- `LastPric` → `LAST` only
- `PrvsAdjstdQt` → previous settlement metadata, not today's settlement

Never substitute last trade for official settlement.

WDO settlement follows DOL; WIN settlement follows IND. Store the official
published settlement; do not recompute it unless a later phase adds a validated
derived series with its own semantics.

### B3 credit (OTC consolidated)

Official public prints are Boletim Diário `ConsolidatedRecords` (Negociação
consolidada / Balcão), not BVBG.186 and not Pesquisa por Pregão Renda Fixa
Privada.

- `Closing` (Último Preço / Last Price) → `LAST`
- `Average` (Preço Médio) → metadata only
- `ReferencePrice` (Preço de Referência) → **not ingested as a quote** (B3 MtM
  if available, else VWAP of the day’s trades)
- RF bulletin `PU_MERCADO` → **not ingested** (reference / model price)

The JSON field is named Closing; it is last observed price, not
`PriceType.CLOSE`. Persist a quote only when Último Preço is present and there
was at least one trade. Absence is a `quality_events` row
(`NO_PUBLIC_PRICE`), never a zero or a carried-forward last.

### Tesouro Direto (CKAN CSV)

These are Tesouro Direto retail morning quotes, not ANBIMA indicative rates.

- `PU Base Manha` → `PU_BASE`
- `PU Compra Manha` → `BID_PU`
- `PU Venda Manha` → `ASK_PU`
- `Taxa Compra Manha` / `Taxa Venda Manha` → `YIELD`

PUs are absolute BRL amounts (an LFT PU can be ~19,700). They are not factors
on base 100.

PYield `tpf.taxas()` fetches ANBIMA, not this CSV. Do not mix those series.

### Banco Central do Brasil

- SGS 11 Selic over → `REFERENCE`, unit `% per day`
- SGS 12 CDI → `REFERENCE`, unit `% per day`
- SGS 432 Selic target → `REFERENCE`, unit `% per year`
- SGS 1 / 10813 PTAX USD → `REFERENCE`, unit BRL per USD
- PTAX OData closing bulletin → `REFERENCE` with buy/sell side in metadata

Never annualize daily Selic/CDI silently.

### Yahoo Finance

- History `Close` → `CLOSE`
- Do not use `Adj Close` for daily valuation
- `is_official = false`

---

## Rules

1. Never silently convert between price types.
2. Never treat missing data as zero.
3. Never carry the last known price forward and present it as today.
4. Absence on a weekend or holiday is not necessarily an error.
5. `NO_PUBLIC_PRICE` / coverage `NO_TRADE` is used when there was no public print,
   not as a fake last trade. Coverage never copies a prior-day quote into today's
   `price`; that case is `STALE`.
6. Multiple quotes per instrument and date are allowed when they have different
   `price_type` or `source_id`.

---

## Units

Store unit explicitly when the value is not a currency amount.

Examples:

- Tesouro yield: percent per year
- Selic/CDI daily: percent per day
- PTAX: BRL per 1 USD
- Fund NAV: BRL per quota
- DI settlement tax: percent per year, 252-business-day convention (document in
  metadata; do not convert)

---

## Related documents

- [`DATA_MODEL.md`](DATA_MODEL.md)
- [`DATA_SOURCES.md`](DATA_SOURCES.md)
- [`adr/0010-observation-types.md`](adr/0010-observation-types.md)
