# Project Context & AI Guidelines

This document provides a concise, single-source-of-truth reference for AI assistants working on **`internship-engine-india`**.

---

## 1. Project Purpose & Scope

- **Primary Goal**: Automatically aggregate, filter, enrich, and publish tech internship listings for **India** (plus Remote) for target hiring cycles (e.g. Summer 2027, Fall 2026).
- **Core Strategy**: Read public ATS job feeds directly (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Internshala, Naukri, Wellfound, etc.), normalize jobs to a unified `Job` schema, deduplicate, enrich posting text, and generate outputs via GitHub Actions on a schedule.
- **De-Americanized Scope**: All legacy US visa/H-1B/F-1 sponsorship tracking files (`h1b.py`, `sponsorship.py`, `build_h1b.py`, `data/h1b.json`) have been removed. Do **not** re-introduce US-specific visa/sponsorship logic.
- **Live Deployment**: The production web app is deployed on **Vercel** (`https://internship-engine-india.vercel.app`) powered by `web/app.py`.

---

## 2. Codebase Structure

```
internship-engine-india/
├── data/
│   ├── config.json          # Active cycles, regions (["India", "Remote"]), scope rules
│   ├── companies.json       # Validated company ATS slugs (~5,803+ companies)
│   ├── jobs.json            # Persistent job store (deduped, open/closed tracking)
│   ├── health.json          # Circuit breaker quarantine state
│   └── history.jsonl        # Per-run stats time-series
├── src/intern_engine/
│   ├── pipeline.py          # Core orchestrator: fetch → filter → enrich → store
│   ├── connectors/          # One module per ATS feed (greenhouse, lever, ashby, etc.)
│   ├── filters.py           # Scope classification: internship?, tech?, season?, region?
│   ├── models.py            # Normalized `Job` dataclass
│   ├── store.py             # Persistent JSON store operations (atomic writes)
│   ├── enrich.py            # Text enrichment for new matched postings
│   ├── readme.py            # Generates README.md
│   ├── publish.py           # Generates RSS feed (`docs/feed.xml`) & iCal (`docs/radar.ics`)
│   ├── health.py            # Quarantines repeatedly failing endpoints
│   ├── harvester.py         # Probes ATS slugs for candidate companies
│   ├── utils.py             # Shared cross-platform atomic file write utilities
│   └── observe.py / radar.py# Drop Radar & cycle tracking
├── web/                     # Production web app (FastAPI) deployed to Vercel
│   ├── app.py               # Routes: /, /api/jobs, /companies, /unsubscribe
│   └── templates/           # Jinja2 templates (index, companies, unsubscribe)
├── docs/                    # Machine-readable public feeds (feed.xml, radar.ics, trends SVGs)
├── tests/                   # Pytest test suite (189+ passing unit tests)
├── run.py                   # CLI entrypoint (update, discover, harvest, all)
└── ARCHITECTURE.md          # Technical architectural design document
```

---

## 3. Key Operational Rules & Constraints

1. **Connector Isolation & Unstable Feed Disabling**:
   - Connector fetch functions are registered in `CONNECTORS` inside `src/intern_engine/pipeline.py`.
   - Direct ATS: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Workday, Breezy, Recruitee, Rippling, Eightfold, Oracle.
   - Direct Tech Portals: Amazon (India jobs), Custom Playwright Scrapers for Indian unicorns (Flipkart, Swiggy, Razorpay, CRED, etc.).
   - India Portals: Internshala, Naukri, Wellfound. Unstable or unwanted aggregators (Unstop, Instahyre, LinkedIn, Indeed) are disabled from `pipeline.py`'s `CONNECTORS` map.
   - Never add blocking network calls to main loops. One failing company feed must never crash the run (wrap in isolated error handlers).

2. **Deduplication & ID Structure**:
   - Job IDs use `<ats_source>:<company_slug>:<external_id>`.
   - Primary deduplication is handled by `_dedup()` in `pipeline.py` using `(company, normalized_title)`.

3. **Regional & Cycle Filtering**:
   - Configured via `data/config.json`. Region matching uses `filters.region_ok()` with strict Option A logic: accepts physical India locations, verified India/Global remote roles, and Indian platform postings, while strictly rejecting foreign remote roles.
   - Explicit seasons in job titles or descriptions (e.g. "Summer 2027") override inferred seasons. Inferred seasons from posting dates are sticky once recorded.

4. **Testing Before Committing**:
   - Always run `python -m pytest` and `python tools/verify_accuracy.py` before completing changes.

---

## 4. Instructions for Future AI Sessions

- **Context Awareness**: Assume the scope is strictly **India & Remote tech internships**.
- **No Hallucinated Execution**: Distinguish clearly between local background command execution and GitHub Actions remote CI workflows.
- **Maintain Test Hygiene**: Ensure changes do not break existing test coverage in `tests/`.
- **Execution Location**: Always run CI or full scraper processes on GitHub's servers (e.g., via `gh workflow run`), never locally on the user's machine, to protect their IP. Only run it locally if the user explicitly asks you to do so.
