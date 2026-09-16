"""Optional Postgres (Supabase) mirror of the full data layer.

Best-effort by design: if SUPABASE_URL / SUPABASE_SERVICE_KEY aren't set (or the
client can't be built), every function no-ops and the engine runs exactly as
before.  When configured, each run mirrors ALL entities into Postgres — the
analytical / API / query layer — while the README/CSV/dashboard remain exported
views and the JSON files stay the pipeline's working state.

Synced entities:
  - companies        (from data/companies.json)
  - jobs             (from data/jobs.json, with all India-specific fields)
  - company_health   (from data/health.json)
  - scrape_runs      (from data/stats.json)
  - drop_observations (from data/observed.json)
  - known_windows    (from data/known_windows.json)
  - app_state        (from data/mail_state.json + data/whatsapp_state.json)
"""

from __future__ import annotations

import json
import os

from . import filters, paths

_BATCH_SIZE = 500


def _client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def enabled() -> bool:
    return _client() is not None


def _upsert_batched(client, table: str, rows: list[dict], conflict: str) -> None:
    """Upsert rows in batches to stay within Supabase/PostgREST limits."""
    for i in range(0, len(rows), _BATCH_SIZE):
        client.table(table).upsert(
            rows[i : i + _BATCH_SIZE], on_conflict=conflict
        ).execute()


# ---------------------------------------------------------------------------
# 1. companies
# ---------------------------------------------------------------------------

def _company_rows(store_data: dict | None = None) -> list[dict]:
    try:
        with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
            companies = json.load(f)
    except (OSError, json.JSONDecodeError):
        companies = []

    seen: set[str] = set()
    rows = []
    for c in companies:
        ats, slug = c.get("ats"), c.get("slug")
        if ats and slug:
            k = f"{ats}:{slug}"
            if k not in seen:
                seen.add(k)
                rows.append({
                    "key": k,
                    "ats": ats,
                    "slug": slug,
                    "name": c.get("name") or slug,
                })

    # Also register any company referenced by jobs (e.g. portal/custom listings)
    if store_data:
        for r in store_data.values():
            src = r.get("source")
            slug = r.get("company_slug")
            name = r.get("company") or slug or "Unknown"
            if src and slug:
                k = f"{src}:{slug}"
                if k not in seen:
                    seen.add(k)
                    rows.append({
                        "key": k,
                        "ats": src,
                        "slug": slug,
                        "name": name,
                    })

    return rows


def _sync_companies(client, store_data: dict | None = None) -> set[str]:
    rows = _company_rows(store_data)
    if rows:
        _upsert_batched(client, "companies", rows, "key")
    return {r["key"] for r in rows}


# ---------------------------------------------------------------------------
# 2. jobs (with all India-specific fields)
# ---------------------------------------------------------------------------

def _classify_region(location: str) -> str:
    """Classify a location into India / Remote / International."""
    if filters.is_india(location):
        return "India"
    if filters.is_remote_or_hybrid(location):
        return "Remote"
    return "International"


def _job_rows(store_data: dict, valid_company_keys: set[str] | None = None) -> list[dict]:
    rows = []
    for r in store_data.values():
        location = r.get("location") or ""
        ckey = f"{r.get('source')}:{r.get('company_slug')}"
        # Set foreign key only if the company exists, else None
        if valid_company_keys is not None and ckey not in valid_company_keys:
            ckey = None

        rows.append(
            {
                "id": r["id"],
                "company_key": ckey,
                "source": r.get("source"),
                "company": r.get("company"),
                "title": r.get("title"),
                "location": location,
                "url": r.get("url"),
                "category": r.get("category"),
                "season": r.get("season"),
                "season_inferred": bool(r.get("season_inferred")),
                "region": _classify_region(location),
                # Compensation
                "salary": r.get("salary"),
                "stipend": r.get("stipend"),
                # India enrichment fields
                "degree": r.get("degree"),
                "experience": r.get("experience"),
                "batch": r.get("batch"),
                "skills": r.get("skills"),  # list[str] -> Postgres text[]
                # Lifecycle
                "posted_at": r.get("posted_at"),
                "first_seen_at": r.get("first_seen_at"),
                "last_seen_at": r.get("last_seen_at"),
                "closed_at": r.get("closed_at"),
                "enriched_at": r.get("enriched_at"),
                "is_open": bool(r.get("is_open")),
            }
        )
    return rows


def _sync_jobs(client, store_data: dict, valid_company_keys: set[str] | None = None) -> int:
    rows = _job_rows(store_data, valid_company_keys)
    if rows:
        _upsert_batched(client, "jobs", rows, "id")
    return len(rows)


# ---------------------------------------------------------------------------
# 3. company_health (circuit breaker state)
# ---------------------------------------------------------------------------

def _health_rows(health_data: dict, valid_company_keys: set[str] | None = None) -> list[dict]:
    return [
        {
            "company_key": key,
            "consecutive_failures": entry.get("consecutive_failures", 0),
            "last_attempt_at": entry.get("last_attempt_at"),
            "last_error": (entry.get("last_error") or "")[:500],
        }
        for key, entry in health_data.items()
        if isinstance(entry, dict) and (valid_company_keys is None or key in valid_company_keys)
    ]


def _sync_health(client, health_data: dict, valid_company_keys: set[str] | None = None) -> int:
    rows = _health_rows(health_data, valid_company_keys)
    if rows:
        _upsert_batched(client, "company_health", rows, "company_key")
    return len(rows)


# ---------------------------------------------------------------------------
# 4. scrape_runs (run metrics)
# ---------------------------------------------------------------------------

_RUN_FIELDS = (
    "generated_at",
    "duration_seconds",
    "companies_total",
    "quarantined",
    "fetched_ok",
    "fetch_errors",
    "fetch_success_rate",
    "roles_matched",
    "new_this_run",
    "open_total",
    "roles_by_source",
    "roles_by_cycle",
    "roles_by_region",
    "detection_latency",
    "posting_lifetime",
)


def _run_row(stats: dict) -> dict:
    return {k: stats.get(k) for k in _RUN_FIELDS}


def _sync_run(client, stats: dict) -> bool:
    client.table("scrape_runs").insert(_run_row(stats)).execute()
    return True


# ---------------------------------------------------------------------------
# 5. drop_observations (from observed.json)
# ---------------------------------------------------------------------------

def _observation_rows(observed: dict) -> list[dict]:
    rows = []
    companies = observed.get("companies") or {}
    for key, entry in companies.items():
        display_name = entry.get("name") or key
        for season, cyc in (entry.get("cycles") or {}).items():
            rows.append(
                {
                    "company_key": key,
                    "display_name": display_name,
                    "season": season,
                    "first_posted": cyc.get("first_posted"),
                    "count": cyc.get("count", 1),
                }
            )
    return rows


def _sync_observations(client, observed: dict) -> int:
    rows = _observation_rows(observed)
    if rows:
        _upsert_batched(client, "drop_observations", rows, "company_key,season")
    return len(rows)


# ---------------------------------------------------------------------------
# 6. known_windows (from known_windows.json)
# ---------------------------------------------------------------------------

def _window_rows() -> list[dict]:
    try:
        with open(paths.KNOWN_WINDOWS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for entry in data.get("companies") or []:
        name = entry.get("name")
        if not name:
            continue
        rows.append(
            {
                "company_name": name,
                "opens_month": entry.get("opens"),
                "precision": entry.get("precision", "month"),
                "note": entry.get("note"),
                "source": entry.get("src"),
                "verified_at": data.get("verified_at"),
            }
        )
    return rows


def _sync_windows(client) -> int:
    rows = _window_rows()
    if rows:
        _upsert_batched(client, "known_windows", rows, "company_name")
    return len(rows)


# ---------------------------------------------------------------------------
# 7. app_state (mail digest + WhatsApp state)
# ---------------------------------------------------------------------------

def _state_rows() -> list[dict]:
    rows = []
    for label, path in (
        ("mail_digest", paths.MAIL_STATE_PATH),
        ("whatsapp_reminder", paths.WHATSAPP_STATE_PATH),
    ):
        try:
            with open(path, encoding="utf-8") as f:
                value = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if value:
            rows.append({"key": label, "value": json.dumps(value)})
    return rows


def _sync_state(client) -> int:
    rows = _state_rows()
    if rows:
        _upsert_batched(client, "app_state", rows, "key")
    return len(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync(store_data: dict, stats: dict) -> bool:
    """Legacy entry point: sync companies + jobs + run metrics.

    Kept for backward compatibility with run.py.
    Prefer full_sync() for complete mirroring.
    """
    return full_sync(store_data=store_data, stats=stats)


def full_sync(
    *,
    store_data: dict | None = None,
    stats: dict | None = None,
    health_data: dict | None = None,
    observed: dict | None = None,
) -> bool:
    """Mirror all available entities into Postgres.

    Each argument is optional: pass what you have, skip what you don't.
    Companies and known_windows are always synced (read from disk).
    """
    client = _client()
    if client is None:
        return False
    try:
        # Always sync these (read from disk, cheap)
        valid_company_keys = _sync_companies(client, store_data)
        _sync_windows(client)
        _sync_state(client)

        # Sync what was passed in
        if store_data is not None:
            _sync_jobs(client, store_data, valid_company_keys)
        if stats is not None:
            _sync_run(client, stats)
        if health_data is not None:
            _sync_health(client, health_data, valid_company_keys)
        if observed is not None:
            _sync_observations(client, observed)
        return True
    except Exception as exc:  # noqa: BLE001 — DB is a mirror; never break the run
        print(f"  (Postgres sync skipped: {type(exc).__name__}: {exc})")
        return False
