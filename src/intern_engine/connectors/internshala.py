"""Internshala connector — rewritten with Scrapling for robust HTML parsing.

Uses Scrapling's Fetcher (lightweight, no browser needed) to parse
Internshala's AJAX endpoint which returns JSON with an HTML fragment.
Adaptive selectors make this self-healing when page structure changes.
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="internshala")

_AJAX_URL = "https://internshala.com/internships_ajax/internship_list_container_ajax/{category}/page-{page}/"
_MAX_PAGES = 3
_AJAX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://internshala.com/internships/",
}

# Scrapling-assisted parsing fallback regexes (used when Scrapling unavailable)
_PATH_RE = re.compile(r'href="(/internship/detail/[^"]+)"')
_TITLE_RE = re.compile(r'class="[^"]*profile[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', re.IGNORECASE)
_COMPANY_RE = re.compile(
    r'class="[^"]*company_name[^"]*"[^>]*>.*?(?:<a[^>]*>)?\s*([^<\n]{2,80}?)\s*(?:</a>)?\s*</div>',
    re.DOTALL | re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r'class="[^"]*location[^"]*"[^>]*>\s*(?:<[^>]+>)*\s*([^<]{2,60}?)\s*(?:<|$)', re.IGNORECASE
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _parse_html_with_scrapling(html: str, category: str) -> list[Job]:
    """Parse internship cards using Scrapling's selector engine."""
    jobs: list[Job] = []
    try:
        from scrapling import Adaptor

        page = Adaptor(html, auto_match=False)

        for card in page.css(".individual_internship"):
            # Title + URL
            title_el = card.css_first(".profile a")
            if not title_el:
                continue
            title = title_el.text.strip()
            path = title_el.attrib.get("href", "")

            # Company name
            comp_el = card.css_first(".company_name")
            company = comp_el.text.strip() if comp_el else "Unknown"

            # Location
            loc_el = card.css_first(".location_link") or card.css_first(".location")
            location = loc_el.text.strip() if loc_el else "—"

            # Stipend
            stipend_el = card.css_first(".stipend")
            stipend = stipend_el.text.strip() if stipend_el else None

            job_id_m = re.search(r"-([a-zA-Z0-9]+)$", path)
            job_id = job_id_m.group(1) if job_id_m else re.sub(r"[^a-z0-9]", "", path)[-12:]

            job = Job(
                id=f"internshala:{category}:{job_id}",
                source="internshala",
                company=company,
                company_slug=category,
                title=title,
                location=location,
                url=f"https://internshala.com{path}",
                posted_at=None,
            )
            if stipend:
                job.stipend = stipend  # type: ignore[attr-defined]
            jobs.append(job)

    except ImportError:
        # Scrapling not available — use regex fallback
        jobs = _parse_html_regex(html, category)
    return jobs


def _parse_html_regex(html: str, category: str) -> list[Job]:
    """Regex-based fallback parser (no external deps)."""
    jobs: list[Job] = []
    cards = html.split("individual_internship")[1:]
    for card in cards:
        path_m = _PATH_RE.search(card)
        title_m = _TITLE_RE.search(card)
        if not path_m or not title_m:
            continue
        path = path_m.group(1)
        title = _clean(title_m.group(1))
        comp_m = _COMPANY_RE.search(card)
        company = _clean(comp_m.group(1)) if comp_m else "Unknown"
        loc_m = _LOCATION_RE.search(card)
        location = _clean(loc_m.group(1)) if loc_m else "—"
        job_id_m = re.search(r"-([a-zA-Z0-9]+)$", path)
        job_id = job_id_m.group(1) if job_id_m else path[-10:]
        jobs.append(
            Job(
                id=f"internshala:{category}:{job_id}",
                source="internshala",
                company=company,
                company_slug=category,
                title=title,
                location=location,
                url=f"https://internshala.com{path}",
                posted_at=None,
            )
        )
    return jobs


def _fetch_page_sync(url: str) -> dict:
    """Synchronous page fetch via Scrapling Fetcher."""
    try:
        from scrapling.fetchers import Fetcher

        fetcher = Fetcher(auto_match=False)
        resp = fetcher.get(url, headers=_AJAX_HEADERS, timeout=20)
        return resp.json() or {}
    except ImportError:
        # Fall back to requests if Scrapling unavailable
        import requests as req

        r = req.get(url, headers=_AJAX_HEADERS, timeout=15)
        return r.json()
    except Exception:
        return {}


async def fetch(company: dict, net: Net) -> list[Job]:
    category = company["slug"]
    jobs: list[Job] = []
    loop = asyncio.get_event_loop()

    for page in range(1, _MAX_PAGES + 1):
        url = _AJAX_URL.format(category=category, page=page)
        data = await loop.run_in_executor(_EXECUTOR, _fetch_page_sync, url)

        html = data.get("html", "")
        if not html:
            break

        page_jobs = _parse_html_with_scrapling(html, category)
        if not page_jobs:
            break
        jobs.extend(page_jobs)
        await asyncio.sleep(0.8)

    return jobs
