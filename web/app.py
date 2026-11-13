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
import time
from datetime import UTC, datetime
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
# Cached data getters (TTL: 60s for jobs, 5m for static)
# ---------------------------------------------------------------------------
_jobs_cache: dict[str, list[dict]] = {}
_jobs_cache_time: dict[str, float] = {}
_JOBS_CACHE_TTL = 60  # seconds

_stats_cache: dict | None = None
_stats_cache_time = 0.0
_STATS_CACHE_TTL = 120

_companies_cache: list[dict] | None = None
_companies_cache_time = 0.0
_COMPANIES_CACHE_TTL = 300


def _is_stale(job: dict, max_days: int = 90) -> bool:
    """Return True if a job was posted/seen more than 3 months (90 days) ago."""
    raw = (job.get("posted_at") or job.get("first_seen_at") or "")[:10]
    if not raw:
        return False
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
        now = datetime.now(UTC)
        return (now - dt).days > max_days
    except ValueError:
        return False


def get_open_jobs() -> list[dict]:
    """Fetch all open jobs, newest first, paginating through Supabase."""
    global _jobs_cache, _jobs_cache_time
    now = time.time()
    if "open" in _jobs_cache and (now - _jobs_cache_time.get("open", 0)) < _JOBS_CACHE_TTL:
        return _jobs_cache["open"]

    client = _get_client()
    if client:
        try:
            open_jobs = []
            page_size = 1000
            start = 0
            for _ in range(25):  # safety cap: up to 25,000 jobs
                resp = (
                    client.table("jobs")
                    .select("*")
                    .eq("is_open", True)
                    .order("first_seen_at", desc=True)
                    .range(start, start + page_size - 1)
                    .execute()
                )
                data = resp.data or []
                open_jobs.extend(data)
                if len(data) < page_size:
                    break
                start += page_size
            open_jobs = [j for j in open_jobs if not _is_stale(j)]
            _jobs_cache["open"] = open_jobs
            _jobs_cache_time["open"] = now
            return open_jobs
        except Exception:
            pass
    # Fallback: read from local jobs.json
    store = _load_json("jobs.json")
    jobs = [r for r in store.values() if r.get("is_open") and not _is_stale(r)]
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
            for _ in range(25):  # safety cap: up to 25,000 jobs
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
    """Fetch latest pipeline run stats."""
    global _stats_cache, _stats_cache_time
    now = time.time()
    if _stats_cache and (now - _stats_cache_time) < _STATS_CACHE_TTL:
        return _stats_cache

    client = _get_client()
    if client:
        try:
            resp = (
                client.table("pipeline_runs")
                .select("*")
                .order("started_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                _stats_cache = resp.data[0]
                _stats_cache_time = now
                return _stats_cache
        except Exception:
            pass
    history = _load_jsonl("history.jsonl")
    if history:
        _stats_cache = history[-1]
        _stats_cache_time = now
        return _stats_cache
    return {}


def get_run_history(limit: int = 50) -> list[dict]:
    """Fetch recent pipeline runs for trends."""
    client = _get_client()
    if client:
        try:
            resp = (
                client.table("pipeline_runs")
                .select("started_at,open_total,new_roles,active_sources,duration_seconds")
                .order("started_at", desc=True)
                .limit(limit)
                .execute()
            )
            if resp.data:
                return list(reversed(resp.data))
        except Exception:
            pass
    history = _load_jsonl("history.jsonl")
    return history[-limit:]


def get_companies() -> list[dict]:
    """Fetch the full company registry with range pagination and caching."""
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
            for _ in range(25):  # safety cap: up to 25,000 companies
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
# Template helpers
# ---------------------------------------------------------------------------

def _fmt_date(iso: str | None) -> str:
    """Format an ISO timestamp to human-friendly date."""
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
        now = datetime.now(UTC)
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
templates.env.globals["fmt_date"] = _fmt_date
templates.env.globals["time_ago"] = _time_ago
app.state.fmt_date = _fmt_date
app.state.time_ago = _time_ago


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def page_index(request: Request, q: str | None = None, cat: str | None = None):
    jobs = get_open_jobs()
    stats = get_stats()

    # Optional query filtering
    if q:
        q_lower = q.lower()
        jobs = [
            j for j in jobs
            if q_lower in (j.get("company") or "").lower()
            or q_lower in (j.get("title") or "").lower()
            or q_lower in (j.get("location") or "").lower()
        ]
    if cat:
        jobs = [j for j in jobs if (j.get("category") or "").lower() == cat.lower()]

    # Categories count
    categories: dict[str, int] = {}
    for j in get_open_jobs():
        c = j.get("category") or "Other"
        categories[c] = categories.get(c, 0) + 1

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "jobs": jobs,
            "stats": stats,
            "categories": dict(sorted(categories.items())),
            "total_open": len(jobs),
            "query": q or "",
            "active_cat": cat or "",
            "active": "jobs",
        },
    )


@app.get("/all", response_class=HTMLResponse)
async def page_all(request: Request):
    """Show both open and closed jobs."""
    jobs = get_all_jobs()
    stats = get_stats()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "jobs": jobs,
            "stats": stats,
            "categories": {},
            "total_open": sum(1 for j in jobs if j.get("is_open")),
            "query": "",
            "active_cat": "",
            "active": "all",
            "show_all": True,
        },
    )


@app.get("/stats", response_class=HTMLResponse)
async def page_stats(request: Request):
    stats = get_stats()
    history = get_run_history(30)
    jobs = get_open_jobs()

    by_ats: dict[str, int] = {}
    by_company: dict[str, int] = {}
    for j in jobs:
        ats = j.get("source") or "other"
        by_ats[ats] = by_ats.get(ats, 0) + 1
        comp = j.get("company") or "Unknown"
        by_company[comp] = by_company.get(comp, 0) + 1

    top_companies = sorted(by_company.items(), key=lambda x: x[1], reverse=True)[:15]

    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={
            "request": request,
            "stats": stats,
            "history": history,
            "by_ats": dict(sorted(by_ats.items(), key=lambda x: x[1], reverse=True)),
            "top_companies": top_companies,
            "total_open": len(jobs),
            "active": "stats",
        },
    )


@app.get("/companies", response_class=HTMLResponse)
async def page_companies(request: Request):
    companies = get_companies()

    by_ats: dict[str, int] = {}
    for c in companies:
        ats = c.get("ats") or "other"
        by_ats[ats] = by_ats.get(ats, 0) + 1

    return templates.TemplateResponse(
        request=request,
        name="companies.html",
        context={
            "request": request,
            "companies": companies,
            "by_ats": dict(sorted(by_ats.items())),
            "total": len(companies),
            "active": "companies",
        },
    )


@app.get("/unsubscribe", response_class=HTMLResponse)
async def page_unsubscribe(request: Request, t: str | None = None):
    token = (t or "").strip()
    if not token:
        return templates.TemplateResponse(
        request=request,
        name="unsubscribe.html",
            context={
                "request": request,
                "status": "error",
                "message": "Missing unsubscribe token. Please use the unsubscribe link provided in your email.",
                "active": "unsubscribe",
            },
            status_code=400,
        )

    client = _get_client()
    if not client:
        return templates.TemplateResponse(
        request=request,
        name="unsubscribe.html",
            context={
                "request": request,
                "status": "error",
                "message": "Database service is currently unavailable. Please try again later.",
                "active": "unsubscribe",
            },
            status_code=503,
        )

    try:
        # Call the secure unsubscribe function
        resp = client.rpc("unsubscribe_email", {"token": token}).execute()
        success = bool(resp.data) if resp else False
        if not success:
            del_resp = client.table("email_subscribers").delete().eq("unsub_token", token).execute()
            success = bool(del_resp.data)

        if success:
            return templates.TemplateResponse(
        request=request,
        name="unsubscribe.html",
                context={
                    "request": request,
                    "status": "success",
                    "message": "You have been successfully unsubscribed from daily internship alerts.",
                    "active": "unsubscribe",
                },
            )
        else:
            return templates.TemplateResponse(
        request=request,
        name="unsubscribe.html",
                context={
                    "request": request,
                    "status": "not_found",
                    "message": "This email is already unsubscribed or the link is invalid.",
                    "active": "unsubscribe",
                },
            )
    except Exception as exc:
        return templates.TemplateResponse(
        request=request,
        name="unsubscribe.html",
            context={
                "request": request,
                "status": "error",
                "message": f"An error occurred while unsubscribing: {type(exc).__name__}",
                "active": "unsubscribe",
            },
            status_code=500,
        )


# --- JSON API (same shape as docs/api/) ---

@app.get("/api/jobs")
async def api_jobs():
    jobs = get_open_jobs()
    return JSONResponse({
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
