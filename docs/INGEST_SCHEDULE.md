# Ingest schedule (America/Sao_Paulo)

GitHub Actions `cron` is always **UTC**. Official Brazilian reference times
below are **America/Sao_Paulo (BRT, UTC−3)**. Brazil has not used DST since
2019, so this offset is treated as stable. If that ever changes, update the
UTC expressions here and in `.github/workflows/`.

Workflows invoke the project CLI (ADR-0006). They do not reimplement downloads
in YAML. Each ingest job uses `concurrency.group` per provider with
`cancel-in-progress: false` (a second B3 job waits; it does not kill the first
and hammer Pesquisa por Pregão). HTTP retries stay in the CLI (`httpx` /
tenacity). YAML does not tight-loop the source.

If `DATABASE_URL` is not configured as a GitHub Actions **secret**, the job
exits before any provider HTTP.

Scheduled workflows run only on the repository **default branch**. Use
`workflow_dispatch` on any branch for manual reruns.

Prefer **either** the per-provider ingest workflows **or** `ingest-all.yml`,
not both. Overlapping crons duplicate work (usually idempotent) and raise
source load.

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
| `ingest-cvm.yml` | 09:30 Mon–Sat | `30 12 * * 1-6` | `marketdata ingest cvm --date` |
| `ingest-tesouro.yml` | 10:30 weekdays | `30 13 * * 1-5` | `marketdata ingest tesouro --date` |
| `ingest-bcb.yml` | 16:30 weekdays | `30 19 * * 1-5` | `marketdata ingest bcb --date` |
| `ingest-b3.yml` | 21:00 weekdays | `0 0 * * 2-6` | `marketdata ingest b3 --date` (BRT trading date; see below) |
| `ingest-yahoo.yml` | none (POC) | **no schedule** | `marketdata ingest yahoo --date` |
| `ingest-all.yml` | 21:30 weekdays | `30 0 * * 2-6` | `marketdata ingest all --date` |
| `publish-datasets.yml` | 22:30 weekdays | `30 1 * * 2-6` | `marketdata publish datasets --date` |
| `backfill.yml` | never daily | **no schedule** | `marketdata backfill <provider> --start --end` |

All ingest/publish workflows also have `workflow_dispatch` with optional
`date` (`YYYY-MM-DD`). When `date` is omitted:

- CVM / Tesouro / BCB / Yahoo: **today UTC** (those crons still fall on the
  same BRT calendar day).
- B3: America/Sao_Paulo trading-date helper (below).
- ingest-all / publish: **today in America/Sao_Paulo**, because their crons
  run after 00:00 UTC (BRT evening of the previous UTC date).

`ingest-yahoo.yml` stays dispatch-only (ADR-0013). Do not add a cron unless
operators explicitly want Yahoo on a schedule **and** `YAHOO_PROVIDER_ENABLED`
is intentional. Yahoo is currently visible on the public API; it is still not
published as Parquet.

`publish-datasets.yml` requires the Actions variable
`PUBLIC_DATASET_PUBLICATION_ENABLED=true`. Parquet publication still honors
source flags: B3 is `API_ONLY` (no public dataset), Yahoo is not redistributable.

`backfill.yml` must **never** gain a `schedule:` block. Range loads are
operator-triggered. GitHub-hosted jobs cap at 6 hours; a full CVM HIST span
should run locally or on a self-hosted runner.

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

To persist only B3 equities listed in the coverage CSV (IBOV+SMLL in the
example seed):

```text
INGEST_UNIVERSE=scratch
```

`scratch` reads `config/instruments.csv` if present, else
`config/instruments.example.csv`. Or set an explicit file
(`B3_EQUITY_UNIVERSE_PATH`); that wins over `INGEST_UNIVERSE`. Tickers not in
the B3 equity rows are skipped (not persisted), not errored.

For a $0-scratch / Neon Free run:

- Do **not** run CVM or Tesouro jobs. `CVM_PROVIDER_ENABLED` and
  `TESOURO_PROVIDER_ENABLED` exist in Settings but are currently ignored by
  ingest/backfill (only `yahoo_provider_enabled` is wired). Omit those
  commands instead of expecting the flags to skip them.
- Do **not** enable COTAHIST (`--cotahist`).
- Keep `marketdata ingest b3` (186 filtered + 187 as-is). Prefer BCB if you
  still want a cheap official series.

See [`.env.example`](../.env.example) and [`DEPLOYMENT.md`](DEPLOYMENT.md).
