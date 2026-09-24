"""FastAPI web app — read-only view of the internship data.

Reads from Supabase Postgres when SUPABASE_URL + SUPABASE_SERVICE_KEY are set.
Falls back to the local JSON files in data/ for local development (no DB needed).

    # Local dev (reads from data/*.json):
    uvicorn web.app:app --reload

    # Production (reads from Supabase):
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uvicorn web.app:app
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent  # repo root
_DATA = _ROOT / "data"
_TEMPLATES = _HERE / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES))

app = FastAPI(
    title="Internship Engine India",
    description="Live internship tracker for India tech internships",
)



# ---------------------------------------------------------------------------
# Data layer: Supabase or local JSON fallback
# ---------------------------------------------------------------------------

def _supabase_client():
    """Return a Supabase client if configured, else None."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = _supabase_client()
    return _client


def _load_json(filename: str) -> dict | list:
    """Load a JSON file from the data/ directory."""
    path = _DATA / filename
    if not path.exists():
        return {} if filename.endswith(".json") and not filename.startswith("[") else []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(filename: str) -> list[dict]:
    """Load a JSONL file from the data/ directory."""
    path = _DATA / filename
    if not path.exists():
        return []
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return lines


# ---------------------------------------------------------------------------
# In-memory caches to keep responses blazing fast (<20ms)
# ---------------------------------------------------------------------------
_companies_cache: list[dict] = []
_companies_cache_time: float = 0
_COMPANIES_CACHE_TTL = 600  # 10 minutes

_jobs_cache: dict[str, list[dict]] = {}
_jobs_cache_time: dict[str, float] = {}
_JOBS_CACHE_TTL = 60  # 1 minute


def get_open_jobs() -> list[dict]:
    """Fetch all open internships, newest first (cached 60s)."""
    global _jobs_cache, _jobs_cache_time
    now = time.time()
    if "open" in _jobs_cache and (now - _jobs_cache_time.get("open", 0)) < _JOBS_CACHE_TTL:
        return _jobs_cache["open"]

    client = _get_client()
    if client:
        try:
            resp = (
                client.table("jobs")
                .select("*")
                .eq("is_open", True)
                .order("first_seen_at", desc=True)
                .execute()
            )
            data = resp.data or []
            if data:
                _jobs_cache["open"] = data
                _jobs_cache_time["open"] = now
                return data
        except Exception:
            pass
    # Fallback: read from local jobs.json
    store = _load_json("jobs.json")
    jobs = [r for r in store.values() if r.get("is_open")]
    jobs.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
    _jobs_cache["open"] = jobs
    _jobs_cache_time["open"] = now
    return jobs


def get_all_jobs() -> list[dict]:
    """Fetch all jobs (open + closed), newest first with pagination."""
    global _jobs_cache, _jobs_cache_time
    now = time.time()
    if "all" in _jobs_cache and (now - _jobs_cache_time.get("all", 0)) < _JOBS_CACHE_TTL:
        return _jobs_cache["all"]

    client = _get_client()
    if client:
        try:
            all_jobs = []
            page_size = 1000
            start = 0
            while True:
                resp = (
                    client.table("jobs")
                    .select("*")
                    .order("first_seen_at", desc=True)
                    .range(start, start + page_size - 1)
                    .execute()
                )
                data = resp.data or []
                all_jobs.extend(data)
                if len(data) < page_size:
                    break
                start += page_size
            if all_jobs:
                _jobs_cache["all"] = all_jobs
                _jobs_cache_time["all"] = now
                return all_jobs
        except Exception:
            pass
    store = _load_json("jobs.json")
    jobs = list(store.values())
    jobs.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
    _jobs_cache["all"] = jobs
    _jobs_cache_time["all"] = now
    return jobs


def get_stats() -> dict:
    """Fetch the latest run stats."""
    client = _get_client()
    if client:
        try:
            resp = (
                client.table("scrape_runs")
                .select("*")
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]
        except Exception:
            pass
    return _load_json("stats.json")


def get_run_history(limit: int = 200) -> list[dict]:
    """Fetch run history for the chart."""
    client = _get_client()
    if client:
        try:
            resp = (
                client.table("scrape_runs")
                .select("generated_at,open_total,new_this_run,companies_total,fetch_success_rate,duration_seconds")
                .order("generated_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            rows.reverse()  # chronological
            return rows
        except Exception:
            pass
    # Fallback: history.jsonl
    lines = _load_jsonl("history.jsonl")
    return lines[-limit:]


def get_companies() -> list[dict]:
    """Fetch the full company registry (all 5,200+ companies) with range pagination and caching."""
    global _companies_cache, _companies_cache_time
    now = time.time()
    if _companies_cache and (now - _companies_cache_time) < _COMPANIES_CACHE_TTL:
        return _companies_cache

    client = _get_client()
    if client:
        try:
            all_companies = []
            page_size = 1000
            start = 0
            while True:
                resp = (
                    client.table("companies")
                    .select("key,ats,slug,name")
                    .order("name")
                    .range(start, start + page_size - 1)
                    .execute()
                )
                data = resp.data or []
                all_companies.extend(data)
                if len(data) < page_size:
                    break
                start += page_size
            if all_companies:
                _companies_cache = all_companies
                _companies_cache_time = now
                return all_companies
        except Exception:
            pass
    loaded = _load_json("companies.json")
    if isinstance(loaded, list) and loaded:
        _companies_cache = loaded
        _companies_cache_time = now
        return loaded
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_date(iso: str | None) -> str:
    """Format an ISO timestamp to a readable date."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(iso)[:10]


def _time_ago(iso: str | None) -> str:
    """Human-readable 'X ago' string."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        return f"{delta.seconds // 60}m ago"
    except (ValueError, TypeError):
        return "—"


# Make helpers available in templates
app.state.fmt_date = _fmt_date
app.state.time_ago = _time_ago


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def homepage(request: Request):
    """Open internships table — same data as the README."""
    jobs = get_open_jobs()
    stats = get_stats()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "jobs": jobs,
            "stats": stats,
            "fmt_date": _fmt_date,
            "time_ago": _time_ago,
        },
    )


@app.get("/all", response_class=HTMLResponse)
async def all_jobs(request: Request):
    """All jobs including closed ones."""
    jobs = get_all_jobs()
    stats = get_stats()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "jobs": jobs,
            "stats": stats,
            "show_closed": True,
            "fmt_date": _fmt_date,
            "time_ago": _time_ago,
        },
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Run metrics and history."""
    stats = get_stats()
    history = get_run_history()
    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={
            "stats": stats,
            "history": history,
            "fmt_date": _fmt_date,
            "time_ago": _time_ago,
        },
    )


@app.get("/companies", response_class=HTMLResponse)
async def companies_page(request: Request):
    """All tracked companies."""
    companies = get_companies()
    # Group by ATS
    by_ats: dict[str, list[dict]] = {}
    for c in companies:
        ats = c.get("ats", "unknown")
        by_ats.setdefault(ats, []).append(c)
    return templates.TemplateResponse(
        request=request,
        name="companies.html",
        context={
            "companies": companies,
            "by_ats": dict(sorted(by_ats.items())),
            "total": len(companies),
        },
    )


# --- JSON API (same shape as docs/api/) ---

@app.get("/api/jobs")
async def api_jobs():
    jobs = get_open_jobs()
    return JSONResponse({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(jobs),
        "jobs": jobs,
    })


@app.get("/api/stats")
async def api_stats():
    return JSONResponse(get_stats())


@app.get("/api/history")
async def api_history():
    return JSONResponse(get_run_history())


@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    """Subscribe an email address to daily internship alerts."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON body."}, status_code=400)

    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        return JSONResponse({"status": "error", "message": "Please enter a valid email address."}, status_code=400)

    client = _get_client()
    if not client:
        return JSONResponse({"status": "error", "message": "Database not configured."}, status_code=503)

    try:
        # Check if already subscribed
        existing = client.table("email_subscribers").select("id").eq("email", email).execute()
        if existing.data:
            return JSONResponse({"status": "exists", "message": "This email is already subscribed!"})

        # Insert new subscriber
        client.table("email_subscribers").insert({"email": email}).execute()
        return JSONResponse({
            "status": "success",
            "message": "You're in! You'll receive a daily digest whenever new internships are spotted.",
        })
    except Exception as exc:
        err_msg = str(exc)
        if "duplicate" in err_msg or "23505" in err_msg:
            return JSONResponse({"status": "exists", "message": "This email is already subscribed!"})
        return JSONResponse({"status": "error", "message": "Failed to subscribe. Please try again."}, status_code=500)

