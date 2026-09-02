# SEC EDGAR 13F (filtered)

Latest-quarter 13F-HR holdings **only where the CUSIP maps to a scratch
equity** (`config/scratch_cusip.csv`). Brazilian names without a CUSIP row
are skipped. Empty intersection is OK. Do not pull decades of 13F or the
full EDGAR tape.

## Map

Scratch ticker → US-listed ADR CUSIP. Holdings whose CUSIP is absent from
the CSV are dropped (including AAPL and the rest of a filer’s book).

## Download

```text
https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&count=20&output=atom
```

Live path is best-effort (recent filings only). HTTP / parse failure
**skips success**. Tests parse a fixture information table; CI does not
call EDGAR.

## Commands

```bash
uv run marketdata ingest 13f --date 2026-08-21
```

Honor `EDGAR_PROVIDER_ENABLED`. Persisted table: `thirteen_f_holdings`.
