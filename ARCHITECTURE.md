# Architecture

[![CI](https://github.com/Rohan-droid7341/internship-engine-india/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohan-droid7341/internship-engine-india/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![async](https://img.shields.io/badge/I%2FO-async%20httpx-success)

A dependency-light Python engine that reads public ATS job feeds directly,
keeps only the internships in scope (configurable cycle / region / role scope),
tracks every role's lifecycle over time, and regenerates the public `README.md`,
an Atom feed, an iCalendar feed, and a live web application on Vercel.
GitHub Actions runs it on a schedule and commits the refreshed output.

## Data flow

```
public datasets + README mines          data/candidates.json (curated slugs)
        │  python run.py discover               │  python run.py harvest
        ▼                                       ▼
   discover.py ──ATS tokens──►  data/companies.json  ◄──probe & merge── harvester.py
                                        │
                                        │  python run.py update
                                        ▼
    health.py ──skips quarantined──►  pipeline.py ──concurrent fetch──►  connectors/*.py
    (circuit breaker,                   │                                (16 sources, one
     data/health.json)                  │  keep: internship? scope?       normalized Job[])
                                        │        target cycle? region?
                                        ▼
                                    enrich.py ──posting text──►
                                        │       (detail fetch only
                                        │        for NEW matched roles)
                                        ▼
                                     store.py ──► data/jobs.json
                                        │         (dedup · first-seen · open/closed
                                        │          · closed_at · retention purge)
        ┌───────────────┬───────────────┴────────────────┬──────────────┐
        ▼               ▼                                ▼              ▼
    readme.py       publish.py                       notify.py       db.py
    README.md       docs/feed.xml + docs/radar.ics   Discord /       Postgres
                    (RSS & iCal alerts)              WhatsApp        (optional)
```

## Files

| File | Responsibility |
|---|---|
| `run.py` | CLI entrypoint: `harvest` \| `discover` \| `update` \| `all`. Puts `src/` on the path. |
| `src/intern_engine/models.py` | The `Job` dataclass — the one shape every connector returns. |
| `src/intern_engine/paths.py` | All file paths, computed from the repo root (CI-safe). |
| `src/intern_engine/config.py` | Loads `data/config.json`; derives repo and live web app URLs. |
| `src/intern_engine/net.py` | Async HTTP with retry/backoff + per-host concurrency limits. |
| `src/intern_engine/connectors/` | Connectors for ATS feeds & job platforms: Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Oracle, Amazon, Rippling, Workable, Breezy, Recruitee, Eightfold, Internshala, Naukri, Wellfound, Custom Careers. |
| `src/intern_engine/filters.py` | Classification: internship? tech? season/year? India/Remote? category. |
| `src/intern_engine/enrich.py` | Fetches posting text for new matched roles; extracts pay, stipend, skills. |
| `src/intern_engine/trends.py` | Weekly posting-volume chart + median posting-lifetime metric. |
| `src/intern_engine/radar.py` | Drop Radar: last cycle's first-post dates projected onto this cycle. |
| `src/intern_engine/mailer.py` | Daily email digests to our subscriber list (Brevo, opt-in). |
| `src/intern_engine/health.py` | Circuit breaker: quarantines repeatedly-failing boards, self-heals. |
| `src/intern_engine/harvester.py` | Probes candidate slugs across ATS, merges hits into the registry. |
| `src/intern_engine/discover.py` | Mines public datasets/READMEs for ATS tokens at scale. |
| `src/intern_engine/quality.py` | Company quality gate: blocklist + optional allowlist-only mode. |
| `src/intern_engine/priority.py` | Company prestige ranking for capped sections. |
| `src/intern_engine/store.py` | Persistent JSON store: dedup, first-seen, open/closed, retention. |
| `src/intern_engine/pipeline.py` | Orchestrates fetch → filter → enrich → store; writes stats + history. |
| `src/intern_engine/readme.py` | Renders `README.md`. |
| `src/intern_engine/publish.py` | Renders the Atom feed (`docs/feed.xml`) and Drop Radar calendar (`docs/radar.ics`). |
| `src/intern_engine/notify.py` | Optional Discord webhook and Twilio WhatsApp alerts for newly spotted roles. |
| `src/intern_engine/db.py` | Optional Postgres (Supabase) mirror of jobs/companies/runs. |
| `web/app.py` | Dynamic web app (FastAPI) deployed to Vercel with search, filters, companies, and unsubscribe. |
| `.github/workflows/update.yml` | Scheduled CI (every 3h): run update, commit changes. |
| `.github/workflows/discover.yml` | Daily CI: discover and harvest new companies automatically. |
| `data/config.json` | Tunable settings (see below). |
| `data/companies.json` | Validated companies the pipeline reads. |
| `data/jobs.json` | The persistent job state (source of truth for the README). |
| `data/health.json` | Circuit-breaker state (auditable in git like everything else). |
| `data/history.jsonl` | One line of run metrics per run. |

## Configuration (`data/config.json`)

```json
{
  "cycles": ["Summer 2027", "Fall 2026"],
  "regions": ["India", "Remote"],
  "role_scope": "tech",
  "max_age_days": 30,
  "max_per_company": 5,
  "allowlist_only": false,
  "infer_undated": true,
  "infer_max_age_days": 30,
  "section_limits": { "Summer 2027": 300, "Fall 2026": 150 }
}
```

Sources: Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Oracle Recruiting
Cloud, Amazon (India Jobs), Rippling, Workable, Breezy, Recruitee, Eightfold,
Internshala, Naukri, Wellfound, and Custom Career Scrapers.
A company-level quality gate (`data/blocklist.json` plus the optional `allowlist_only` mode)
keeps the list free of spam.

- `cycles` — the exact cycles to show; these become the section headings, in order.
  A year stated in the title always wins (e.g. "2027", "Fall 2026", "Summer '27"
  — but a graduation year like "Class of 2027" never counts). Titles with no
  year are bucketed from their posting date when posted within
  `infer_max_age_days` (marked `~` everywhere they render), then checked against
  the posting text at enrichment.
- `regions` — `["India", "Remote"]` (India and verified global remote).
- `role_scope` — `"tech"` keeps only tech roles; `"all"` keeps every internship.
- `max_age_days` — drop postings published longer ago than this (kills stale/evergreen reqs).
- `max_per_company` — cap roles shown per company per section, for variety.
- `section_limits` — max rows per section; over the cap, the most sought-after companies win.

Run `python run.py discover` to mine public datasets for company tokens and grow
`data/companies.json` — we then poll those feeds directly. A daily workflow does
this automatically.

## Design choices

- **One normalized `Job`** decouples the whole system from any specific ATS —
  adding a source is a single new connector module + one line in
  `pipeline.CONNECTORS`.
- **JSON store, not a DB** — the state file is committed by CI each run, so a
  human-diffable text file beats a binary database here.
- **Fault isolation** — each company is fetched in its own task with its own
  `try/except`; one dead endpoint never breaks a run, and jobs are only marked
  "closed" for companies that fetched successfully.
- **Circuit breaker** — boards that fail 3+ runs in a row are quarantined with
  an exponential backoff window (6h → 72h cap) and retried automatically, so
  dead slugs from public datasets cost nothing and recoveries need no human.
- **Enrichment is O(new roles), not O(all jobs)** — posting text is fetched once
  per matched role, the verdict is stored, and it is never re-fetched.
- **Stable ids** (`<source>:<slug>:<external_id>`) make dedup automatic.
- **Frozen posted dates** — a role's published date is recorded once; blanks may
  be backfilled later (better data), but a real date never shifts.

## Workday (enterprise tier) & the optional proxy

Workday is per-tenant (each company has its own host + `site`) and bot-protected.
Discovery extracts tenant/site pairs from public data — both URL shapes
(`{tenant}.wdN.myworkdayjobs.com` and `wdN.myworkdaysite.com/recruiting/…`) —
and the connector paginates past the API's 20-per-page cap. Failures are
isolated per company and repeated failures are quarantined by the breaker.

Workday blocks **datacenter/cloud IPs** more aggressively than home IPs, so the
GitHub Actions runner may be refused for some tenants. To recover them, set a repo
secret named **`WORKDAY_PROXY`** to a proxy URL. The workflow passes it through, and only the
Workday/Oracle connectors use it. Unset = they run direct (default).

## Data layer (optional Postgres / Supabase)

The JSON store is the always-available default. When `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY` are set, each run also mirrors the data into Postgres via
`db.py` (best-effort - missing creds simply skip it): a normalized schema of
`companies`, `jobs` (with first/last-seen history + open/closed state), and a
`scrape_runs` metrics table. The README, RSS feed, and web app serve users seamlessly.

## Alerts

- **RSS/Atom** (`docs/feed.xml`): ordered by when the engine first spotted each
  role — point any RSS reader, or a Slack/Discord RSS integration, at it and new
  roles arrive as notifications. Zero infrastructure.
- **Discord & WhatsApp webhook** (optional): set `DISCORD_WEBHOOK_URL` and Twilio
  secrets to get real-time role alerts.
- **Email digests** (our own list): the web app's signup form inserts into Supabase
  under row-level security. `mailer.py` sends at most one digest a day, only when
  something new appeared, via Brevo's transactional API (`BREVO_API_KEY` + `MAIL_FROM` secrets).
  Every email carries a one-click unsubscribe link handled by `/unsubscribe` on the web app.

## Drop Radar

Every list shows what's open; the radar shows **what's coming**. At render time
`radar.py` checks expected opening dates against the live store and renders a
countdown table: README shows marquee dates, and `docs/radar.ics` provides an
iCalendar subscription.

## Trends

`trends.py` answers timing questions from data the store already keeps:
weekly posting volume (from real published dates) and median posting lifetime.

## Running locally

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py all               # discover + harvest + update
python -m pytest                # 189+ tests, no network
```
