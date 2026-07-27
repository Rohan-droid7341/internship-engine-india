"""LinkedIn Jobs guest search API — no login, no API key needed.

Uses LinkedIn's public /jobs-guest/ endpoint which returns HTML job cards.
Since Scrapling is synchronous we run it in a thread-pool executor so the
async pipeline is not blocked.
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="linkedin")

_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location=India&start={start}&count=25"
)
_MAX_PAGES = 3  # 3 × 25 = 75 results per search term

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.linkedin.com/jobs/search/",
}

# Regexes for parsing LinkedIn's HTML job cards
_LI_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)
_JOB_ID_RE = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_TITLE_RE = re.compile(r'class="[^"]*sr-only[^"]*"[^>]*>\s*([^<]+?)\s*</', re.DOTALL)
_COMPANY_RE = re.compile(r'class="[^"]*hidden-nested-link[^"]*"[^>]*>\s*([^<]+?)\s*</', re.DOTALL)
_LOCATION_RE = re.compile(
    r'class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+?)\s*</', re.DOTALL
)
_DATE_RE = re.compile(r'<time[^>]+datetime="([^"]+)"')


def _scrape_page(url: str) -> str:
    """Fetch one page using Scrapling's plain Fetcher (fast, low overhead)."""
    try:
        import os
        from scrapling.fetchers import Fetcher

        proxy = os.environ.get("WORKDAY_PROXY")
        fetcher = Fetcher(auto_match=False, proxy=proxy) if proxy else Fetcher(auto_match=False)
        resp = fetcher.get(url, headers=_HEADERS, timeout=20)
        return resp.content or ""
    except ImportError:
        # Scrapling not installed — fall back gracefully (returns empty)
        return ""
    except Exception:
        return ""


def _parse_cards(html: str, keywords: str) -> list[Job]:
    jobs: list[Job] = []
    for match in _LI_RE.finditer(html):
        card = match.group(1)
        jid_m = _JOB_ID_RE.search(card)
        if not jid_m:
            continue
        job_id = jid_m.group(1)

        title_m = _TITLE_RE.search(card)
        title = title_m.group(1).strip() if title_m else "Unknown Role"

        comp_m = _COMPANY_RE.search(card)
        company = comp_m.group(1).strip() if comp_m else "Unknown Company"

        loc_m = _LOCATION_RE.search(card)
        location = loc_m.group(1).strip() if loc_m else "India"

        date_m = _DATE_RE.search(card)
        posted_at = date_m.group(1) if date_m else None

        jobs.append(
            Job(
                id=f"linkedin:{job_id}",
                source="linkedin",
                company=company,
                company_slug=re.sub(r"[^a-z0-9]", "-", company.lower()).strip("-"),
                title=title,
                location=location,
                url=f"https://www.linkedin.com/jobs/view/{job_id}/",
                posted_at=posted_at,
            )
        )
    return jobs


async def fetch(company: dict, net: Net) -> list[Job]:
    """Aggregate Indian internship listings from LinkedIn's guest search."""
    keywords = company.get("slug", "software intern").replace("-", "+")
    jobs: list[Job] = []
    loop = asyncio.get_event_loop()

    for page in range(_MAX_PAGES):
        start = page * 25
        url = _SEARCH_URL.format(keywords=keywords, start=start)
        html = await loop.run_in_executor(_EXECUTOR, _scrape_page, url)
        if not html:
            if page == 0:
                raise RuntimeError("LinkedIn rate limited or returned 0 jobs on page 1")
            break
        page_jobs = _parse_cards(html, keywords)
        if not page_jobs:
            if page == 0:
                raise RuntimeError("LinkedIn rate limited or returned 0 jobs on page 1")
            break
        jobs.extend(page_jobs)
        await asyncio.sleep(1.5)  # be polite between pages

    return jobs
