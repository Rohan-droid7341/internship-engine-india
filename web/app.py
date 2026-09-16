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
# Data fetchers (Supabase → JSON fallback)
# ---------------------------------------------------------------------------

def get_open_jobs() -> list[dict]:
    """Fetch all open internships, newest first."""
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
            return resp.data or []
        except Exception:
            pass
    # Fallback: read from local jobs.json
    store = _load_json("jobs.json")
    jobs = [r for r in store.values() if r.get("is_open")]
    jobs.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
    return jobs


def get_all_jobs() -> list[dict]:
    """Fetch all jobs (open + closed), newest first."""
    client = _get_client()
    if client:
        try:
            resp = (
                client.table("jobs")
                .select("*")
                .order("first_seen_at", desc=True)
                .limit(1000)
                .execute()
            )
            return resp.data or []
        except Exception:
            pass
    store = _load_json("jobs.json")
    jobs = list(store.values())
    jobs.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
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
    """Fetch the company registry."""
    client = _get_client()
    if client:
        try:
            resp = (
                client.table("companies")
                .select("*")
                .order("name")
                .execute()
            )
            return resp.data or []
        except Exception:
            pass
    return _load_json("companies.json")


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
