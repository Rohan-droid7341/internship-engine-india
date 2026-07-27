"""Naukri.com job search — India's largest job board.

Uses Naukri's internal search JSON API with browser-like headers.
Scrapling's StealthyFetcher is used to bypass Cloudflare protection.
Falls back to a plain request if Scrapling/Playwright is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="naukri")

# Naukri's internal JSON search API
_API_URL = (
    "https://www.naukri.com/jobapi/v4/search"
    "?noOfResults=20&urlType=search_by_keyword&searchType=adv"
    "&keyword={keyword}&location=india&experience=0&page={page}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Appid": "109",
    "Systemid": "109",
    "Content-Type": "application/json",
    "Referer": "https://www.naukri.com/",
    "X-Requested-With": "XMLHttpRequest",
}

_MAX_PAGES = 3


def _scrape_page(url: str) -> dict:
    """Fetch one page using Scrapling's StealthyFetcher to bypass Cloudflare."""
    try:
        import os
        from scrapling.fetchers import StealthyFetcher

        proxy = os.environ.get("WORKDAY_PROXY")
        fetcher = StealthyFetcher(auto_match=False, proxy=proxy) if proxy else StealthyFetcher(auto_match=False)
        resp = fetcher.get(url, headers=_HEADERS, timeout=30, stealth=True)
        text = resp.content or ""
        # Strip BOM if present
        text = text.lstrip("\ufeff")
        return json.loads(text)
    except ImportError:
        # Playwright / Scrapling not installed — skip gracefully
        return {}
    except Exception:
        return {}


def _location(job: dict) -> str:
    places = job.get("placeholders", [])
    for p in places:
        if p.get("type") == "location":
            return (p.get("label") or "").strip() or "India"
    locs = job.get("locations", [])
    if locs:
        return ", ".join(str(loc) for loc in locs[:3])
    return "India"


async def fetch(company: dict, net: Net) -> list[Job]:
    """Search Naukri for internships matching the company slug as keyword."""
    keyword = company.get("slug", "software").replace("-", "+")
    jobs: list[Job] = []
    loop = asyncio.get_event_loop()

    for page in range(1, _MAX_PAGES + 1):
        url = _API_URL.format(keyword=keyword, page=page)
        data = await loop.run_in_executor(_EXECUTOR, _scrape_page, url)

        job_list = data.get("jobDetails", [])
        if not job_list:
            if page == 1:
                raise RuntimeError("Naukri rate limited or returned 0 jobs on page 1")
            break

        for item in job_list:
            job_id = str(item.get("jobId", ""))
            title = (item.get("title") or "").strip()
            comp = (item.get("companyName") or "Unknown").strip()
            jd_url = item.get("jdURL") or f"https://www.naukri.com/job-listings-{job_id}"

            jobs.append(
                Job(
                    id=f"naukri:{job_id}",
                    source="naukri",
                    company=comp,
                    company_slug=re.sub(r"[^a-z0-9]", "-", comp.lower()).strip("-"),
                    title=title,
                    location=_location(item),
                    url=jd_url,
                    posted_at=item.get("footerPlaceholderLabel"),
                )
            )

        await asyncio.sleep(2.0)  # be extra polite to Naukri

    return jobs
