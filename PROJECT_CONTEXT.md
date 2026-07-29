# Project Context & AI Guidelines

This document provides a concise, single-source-of-truth reference for AI assistants working on **`internship-engine-india`**.

---

## 1. Project Purpose & Scope

- **Primary Goal**: Automatically aggregate, filter, enrich, and publish tech internship listings for **India** (plus Remote) for target hiring cycles (e.g. Summer 2027, Fall 2026).
- **Core Strategy**: Read public ATS job feeds directly (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Unstop, Internshala, Instahyre, Naukri, etc.), normalize jobs to a unified `Job` schema, deduplicate, enrich posting text, and generate output formats via GitHub Actions on a schedule.
- **De-Americanized Scope**: All legacy US visa/H-1B/F-1 sponsorship tracking files (`h1b.py`, `sponsorship.py`, `build_h1b.py`, `data/h1b.json`) have been removed. Do **not** re-introduce US-specific visa/sponsorship logic.

---

## 2. Codebase Structure

```
internship-engine-india/
├── data/
│   ├── config.json          # Active cycles, regions (["India", "Remote"]), scope rules
│   ├── companies.json       # Validated company ATS slugs (~4,400+ companies)
│   ├── jobs.json            # Persistent job store (deduped, open/closed tracking)
│   ├── health.json          # Circuit breaker quarantine state
│   └── history.jsonl        # Per-run stats time-series for dashboard
├── src/intern_engine/
│   ├── pipeline.py          # Core orchestrator: fetch → filter → enrich → store
│   ├── connectors/          # One module per ATS feed (greenhouse, lever, ashby, etc.)
│   ├── filters.py           # Scope classification: internship?, tech?, season?, region?
│   ├── models.py            # Normalized `Job` dataclass
│   ├── store.py             # Persistent JSON store operations
│   ├── enrich.py            # Text enrichment for new matched postings
│   ├── readme.py            # Generates README.md & data/internships.csv
│   ├── dashboard.py         # Renders docs/index.html (GitHub Pages client-side app)
│   ├── publish.py           # Generates RSS feed & static JSON API in docs/
│   ├── health.py            # Quarantines repeatedly failing endpoints
│   ├── harvester.py         # Probes ATS slugs for candidate companies
│   └── observe.py / radar.py# Drop Radar & cycle tracking
├── docs/                    # GitHub Pages build targets (index.html, feed.xml, api/)
├── tests/                   # Pytest test suite (155+ passing unit tests)
├── run.py                   # CLI entrypoint (update, discover, harvest, all)
└── ARCHITECTURE.md          # Technical architectural design document
```

---

## 3. Key Operational Rules & Constraints

1. **Connector Isolation & Unstable Feed Disabling**:
   - Connector fetch functions are registered in `CONNECTORS` inside `src/intern_engine/pipeline.py`.
   - Aggressive anti-bot / rate-limiting connectors (such as `linkedin` and `indeed`) are commented out in `pipeline.py`'s `CONNECTORS` map to prevent execution hangs while retaining their modules in `src/intern_engine/connectors/`.
   - Never add blocking network calls to main loops. One failing company feed must never crash the run (wrap in isolated error handlers).

2. **Deduplication & ID Structure**:
   - Job IDs use `<ats_source>:<company_slug>:<external_id>`.
   - Primary deduplication is handled by `_dedup()` in `pipeline.py` using `(company, normalized_title)`.

3. **Regional & Cycle Filtering**:
   - Configured via `data/config.json`. Region matching uses `filters.region_ok()` for `"India"` and `"Remote"`.
   - Explicit seasons in job titles (e.g. "Summer 2027") override inferred seasons. Inferred seasons from posting dates are sticky once recorded.

4. **Testing Before Committing**:
   - Always run `python -m pytest` to verify all unit tests pass before completing changes.

---

## 4. Instructions for Future AI Sessions

- **Context Awareness**: Assume the scope is strictly **India & Remote tech internships**.
- **No Hallucinated Execution**: Distinguish clearly between local background command execution (`python run.py update`) and GitHub Actions remote CI workflows.
- **Maintain Test Hygiene**: Ensure changes do not break existing test coverage in `tests/`.
- **Execution Location**: Always run CI or full scraper processes on GitHub's servers (e.g., via `gh workflow run`), never locally on the user's machine, to protect their IP. Only run it locally if the user explicitly asks you to do so.
