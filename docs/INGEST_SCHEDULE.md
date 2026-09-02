# Ingest schedule (America/Sao_Paulo)

GitHub Actions `cron` is always **UTC**. Official Brazilian reference times
below are **America/Sao_Paulo (BRT, UTC−3)**. Brazil has not used DST since
2019, so this offset is treated as stable. If that ever changes, update the
UTC expressions here and in `.github/workflows/`.

Workflows invoke the project CLI (ADR-0006). They do not reimplement downloads
in YAML. Neon-writing workflows share one GitHub Actions concurrency group,
`neon-writes`, with `cancel-in-progress: false`: `backfill.yml`,
`ingest-all.yml`, `ingest-b3.yml`, `ingest-bcb.yml`, `ingest-cvm.yml`,
`ingest-tesouro.yml`, and `ingest-yahoo.yml`. The group is repository-scoped,
so a nightly B3 ingest waits behind an in-progress backfill instead of writing
in parallel. An in-progress run is not cancelled. `ci.yml`, `explorer.yml`,
and `publish-datasets.yml` are not in that group; they do not write to
Postgres. HTTP retries stay in the CLI (`httpx` / tenacity). YAML does not
tight-loop the source.

If `DATABASE_URL` is not configured as a GitHub Actions **secret**, the job
exits before any provider HTTP. The secret must be set in the repository
Settings → Secrets and variables → Actions. Do **not** put the connection
string in git, workflow YAML, or these docs. This repository currently has no
Actions secrets; scheduled jobs will keep failing at "Require DATABASE_URL"
until an operator adds that secret.

Scheduled workflows run only on the repository **default branch**. Use
`workflow_dispatch` on any branch for manual reruns.

Daily scheduled ingest is the **per-provider** crons (BCB, B3, Tesouro).
`ingest-all.yml` is `workflow_dispatch` only so it does not run on the same
calendar as those crons (overlapping jobs duplicate work and raise source
load). `ingest-cvm.yml` is also `workflow_dispatch` only. Persist is filtered by
`CVM_CLASSES` (scratch default `Multimercado,Ações`; see below). Do not add
its cron back unless operators explicitly want daily CVM on Neon.

---

## Conversion

`UTC hour = BRT hour + 3`. When that sum is ≥ 24, the UTC **calendar date**
is the next day.

| BRT clock | UTC clock | UTC date vs BRT date |
|---|---|---|
| 09:30 | 12:30 | same calendar day |
| 10:30 | 13:30 | same calendar day |
| 16:30 | 19:30 | same calendar day |
| 21:00 | 00:00 | UTC date = BRT date + 1 |
| 21:30 | 00:30 | UTC date = BRT date + 1 |
| 22:30 | 01:30 | UTC date = BRT date + 1 |

GitHub `cron` weekday field: `0`/`7` Sunday … `6` Saturday. A job that should
run Monday–Friday **evening BRT** must therefore list **Tuesday–Saturday UTC**
(`2-6`).

---

## Workflows

| Workflow | Safe local clock BRT | Cron UTC | Command |
|---|---|---|---|
| `ingest-cvm.yml` | none (dispatch only; class-filtered persist) | **no schedule** | `marketdata ingest cvm --date` |
| `ingest-tesouro.yml` | 10:30 weekdays | `30 13 * * 1-5` | `marketdata ingest tesouro --date` |
| `ingest-bcb.yml` | 16:30 weekdays | `30 19 * * 1-5` | `marketdata ingest bcb --date` |
| `ingest-b3.yml` | 21:00 weekdays | `0 0 * * 2-6` | `marketdata ingest b3 --date` (BRT trading date; see below) |
| `ingest-yahoo.yml` | 00:00 nightly | `0 3 * * *` | `marketdata ingest yahoo --date` |
| `ingest-all.yml` | none (dispatch only) | **no schedule** | `marketdata ingest all --date` |
| `publish-datasets.yml` | 22:30 weekdays | `30 1 * * 2-6` | `marketdata publish datasets --date` |
| `backfill.yml` | never daily | **no schedule** | `marketdata backfill <provider> --start --end` |

All ingest/publish workflows also have `workflow_dispatch` with optional
`date` (`YYYY-MM-DD`). When `date` is omitted:

- CVM / Tesouro / BCB: **today UTC** (Tesouro and BCB crons still fall
  on the same BRT calendar day; CVM is dispatch-only and class-filtered).
- Yahoo: **yesterday in America/Sao_Paulo**, walking back across Saturday/Sunday
  (completed session after 00:00 BRT; Monday 00:00 ingests Friday).
- B3: America/Sao_Paulo trading-date helper (below).
- ingest-all / publish: **today in America/Sao_Paulo**. Publish still runs
  after 00:00 UTC (BRT evening of the previous UTC date). ingest-all is
  dispatch-only; the Sao_Paulo default remains so a weekday evening rerun
  does not pick the next UTC calendar date.

`ingest-cvm.yml` stays dispatch-only. Informe persist is filtered by
`CVM_CLASSES` after joining CVM cadastro (`registro_classe.csv`) on
`CNPJ_FUNDO_CLASSE`. Empty application setting = persist all classes.
Scratch / Neon Free uses `CVM_CLASSES=Multimercado,Ações` (exact cad_fi
`CLASSE` labels). FII, FIDC, Renda Fixa, and unclassified rows are skipped.
The workflow job defaults that allowlist unless repository variable
`CVM_CLASSES` is set. Do not add the CVM cron unless operators explicitly
want daily CVM on Neon.

`DATABASE_URL` is still an Actions **secret**. There is no connection string
in git, workflow YAML, or these docs. Scheduled (and dispatch) jobs fail at
"Require DATABASE_URL" until an operator sets that secret.

`ingest-all.yml` stays dispatch-only. Do not add its cron while per-provider
BCB / B3 / Tesouro schedules are enabled.

Official ingest/backfill jobs that can run provider `all` or Yahoo
(`ingest-all.yml`, `backfill.yml`) set `YAHOO_PROVIDER_ENABLED=false` in job
`env:`. The same flag is set on the official per-provider workflows (CVM, B3,
Tesouro, BCB) as a shared env baseline. Python defaults `yahoo_provider_enabled`
to false.

`ingest-yahoo.yml` is the exception: it sets `YAHOO_PROVIDER_ENABLED=true` and
runs nightly at `0 3 * * *` (00:00 America/Sao_Paulo, UTC−3). Default `--date`
is yesterday in America/Sao_Paulo so the job persists the session that just
finished, not an in-progress bar. The helper walks back across Saturday/Sunday
(Monday 00:00 BRT → Friday). `workflow_dispatch` may still pass an explicit
date. Symbols come from `config/instruments.scratch.csv`: 150 B3 equities as
`{TICKER}.SA` (PETR4 → PETR4.SA). `ingest-yahoo.yml` forwards
`INGEST_UNIVERSE` and `B3_EQUITY_UNIVERSE_PATH` like the B3 jobs; Yahoo still
reads the scratch CSV when those vars are empty. Futures (`WIN*` / `IND*` /
`WDO*` / `DOL*` / `DI1*`) are skipped with a count in the run log. One missing
Yahoo symbol is logged and skipped; it does not fail the job. Mapping equities
and persisting zero quotes on a weekday fails the run. Yahoo remains unofficial
POC (ADR-0013): `public_dataset_enabled` stays false. Official B3 quotes stay
the Explorer default for PETR4 (`PETR4.SA` is a distinct Yahoo identifier).

`publish-datasets.yml` requires the Actions variable
`PUBLIC_DATASET_PUBLICATION_ENABLED=true`. Leave that variable unset or
`false` unless publication is an explicit operator choice. Parquet publication
still honors source flags: B3 is `API_ONLY` (no public dataset), Yahoo is not
redistributable. If `OBJECT_STORAGE_BACKEND` is local, unset, or not `s3`, the
workflow **succeeds with skip** (R2 is not configured) instead of failing. Local
S3-compatible backends (`OBJECT_STORAGE_BACKEND=s3`) still publish.

`backfill.yml` must **never** gain a `schedule:` block. Range loads are
operator-triggered. GitHub-hosted jobs cap at 6 hours; a full CVM HIST span
should run locally or on a self-hosted runner. After a 6-hour kill, re-dispatch
the same provider and start/end — B3 resumes from the restored checkpoint or
Neon `max(instrument_quotes.reference_date)` in that range, not a new `--start`.

Tesouro daily ingest (`ingest-tesouro.yml`) and Tesouro backfill both honor
`TESOURO_CURRENT_TITLES_ONLY` (default `true`): only titles present on the
latest `Data Base` date in the CKAN CSV are persisted, with their full
history. Set `false` to persist the entire CSV, including matured titles.
See [`DEPLOYMENT.md`](DEPLOYMENT.md#tesouro-currently-traded-titles).

Secrets and durable object storage: [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## B3 `--date` (UTC cron vs BRT trading day)

B3 EOD files (BVBG.186 last trades, BVBG.187 settlement, credit prints) are
expected after about **20:30 BRT**. The job is scheduled at **21:00 BRT**
weekdays.

GitHub fires that as `0 0 * * 2-6` (Tuesday–Saturday 00:00 UTC):

- Tuesday 00:00 UTC = Monday 21:00 BRT → ingest **Monday**
- Saturday 00:00 UTC = Friday 21:00 BRT → ingest **Friday**

Default `--date` when `workflow_dispatch` does not pass `date`:

1. Take **now** in `America/Sao_Paulo`.
2. If local time ≥ 21:00, use **today**; otherwise use **yesterday**.
3. While the result is Saturday or Sunday, step back one day (land on Friday).

`ingest-b3.yml` computes that default with
`uv run python -m marketdata.ingestion.schedule` (prints an ISO date). Prefer
an explicit `workflow_dispatch` date for reruns (for example a holiday Friday,
or a missed Monday). There is no `ingest b3 --date auto`.

Holidays are **not** skipped here. An empty B3 ZIP for a holiday should be
handled by the ingest/backfill code (empty-ZIP skip), not by YAML retries.

---

## CLI names (must match Typer)

```text
uv run marketdata ingest cvm --date YYYY-MM-DD
uv run marketdata ingest tesouro --date YYYY-MM-DD
uv run marketdata ingest bcb --date YYYY-MM-DD
uv run marketdata ingest b3 --date YYYY-MM-DD
uv run marketdata ingest yahoo --date YYYY-MM-DD
uv run marketdata ingest all --date YYYY-MM-DD
uv run marketdata publish datasets --date YYYY-MM-DD
uv run marketdata backfill <cvm|tesouro|bcb|b3|yahoo|all> --start YYYY-MM-DD --end YYYY-MM-DD
```

`ingest all` and `backfill` are live CLI commands. The YAML calls those exact
names. `backfill.yml` must never gain a `schedule:` block.

---

## Scratch universe (opt-in, BVBG.186 LAST only)

Default B3 ingest is **unchanged**: the full BVBG.186 LAST file is persisted.
BVBG.187 futures keep the existing MVP ticker regex.

To persist only B3 equities listed in the scratch coverage CSV (IBOV+SMLL):

```text
INGEST_UNIVERSE=scratch
```

`scratch` reads `config/instruments.csv` if present, else
`config/instruments.scratch.csv`. Or set an explicit file
(`B3_EQUITY_UNIVERSE_PATH`); that wins over `INGEST_UNIVERSE`. Tickers not in
the B3 equity rows are skipped (not persisted), not errored. Empty
`INGEST_UNIVERSE` still persists the full BVBG.186.

Scratch also skips the live BDI OTC credit download (trades + ~9k-row cadastro).
That path is not in the IBOV/SMLL coverage list and was the bulk of a 2-hour
single-day GitHub Actions run. Explicit `credit_*_payload` arguments still
ingest. BVBG.028 is still fetched so ISINs/maturities can be attached, but only
for tickers persisted from 186/187 — ingest does not issue one Neon lookup per
master instrument. Stage timing logs go to stderr; B3 workflows set
`PYTHONUNBUFFERED=1`.

`ingest-b3.yml`, `ingest-all.yml`, `backfill.yml`, and `ingest-yahoo.yml` pass
both variables from repository Actions variables (`vars.INGEST_UNIVERSE`,
`vars.B3_EQUITY_UNIVERSE_PATH`). Unset/empty keeps B3 full-file persist. Yahoo
still reads `config/instruments.scratch.csv` when the vars are empty. The Python
default for B3 is unchanged: empty `INGEST_UNIVERSE` still persists the full
BVBG.186. Do not enable COTAHIST. `ingest-cvm.yml` stays dispatch-only.

For a $0-scratch / Neon Free run:

- CVM persist honors `CVM_CLASSES=Multimercado,Ações`. `ingest-cvm.yml` stays
  dispatch-only. Do not re-enable its cron.
- Tesouro persist honors `TESOURO_CURRENT_TITLES_ONLY` (default true).
- `CVM_PROVIDER_ENABLED`, `B3_PROVIDER_ENABLED`, `TESOURO_PROVIDER_ENABLED`,
  and `BCB_PROVIDER_ENABLED` are honored by `ingest` / `backfill` (including
  `all` and individual commands). Set a flag false to skip that provider.
  `YAHOO_PROVIDER_ENABLED` defaults false (ADR-0013). ANBIMA stays disabled.
- Do **not** enable COTAHIST (`--cotahist`).
- Keep `marketdata ingest b3` (186 filtered + 187 as-is). Prefer BCB if you
  still want a cheap official series.

See [`.env.example`](../.env.example) and [`DEPLOYMENT.md`](DEPLOYMENT.md).
