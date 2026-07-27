"""Indeed India job search connector.

Uses Scrapling's StealthyFetcher to bypass Cloudflare protection.
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indeed")

_SEARCH_URL = "https://in.indeed.com/jobs?q={keyword}&start={start}"
_MAX_PAGES = 3  # 3 pages * 15 jobs = ~45 jobs per keyword

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Extracts the jobTitle, companyName, jobLocationCity, etc. from Indeed's mosaic data
_MOSAIC_RE = re.compile(r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});', re.DOTALL)


def _scrape_page(url: str) -> list[Job]:
    try:
        import os
        from scrapling.fetchers import StealthyFetcher

        proxy = os.environ.get("WORKDAY_PROXY")
        fetcher = StealthyFetcher(auto_match=False, proxy=proxy) if proxy else StealthyFetcher(auto_match=False)
        resp = fetcher.get(url, headers=_HEADERS, timeout=30, stealth=True)
        html = resp.content or ""
        
        m = _MOSAIC_RE.search(html)
        if not m:
            return []
            
        import json
        data = json.loads(m.group(1))
        results = data.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results", [])
        
        jobs = []
        for item in results:
            job_key = item.get("jobkey")
            title = item.get("title")
            company = item.get("company")
            location = item.get("jobLocationCity") or item.get("formattedLocation") or "India"
            url = f"https://in.indeed.com/viewjob?jk={job_key}"
            
            if not job_key or not title or not company:
                continue
                
            jobs.append(
                Job(
                    id=f"indeed:{job_key}",
                    source="indeed",
                    company=company,
                    company_slug=re.sub(r"[^a-z0-9]", "-", company.lower()).strip("-"),
                    title=title,
                    location=location,
                    url=url,
                    posted_at=None,
                )
            )
        return jobs
    except Exception:
        return []


async def fetch(company: dict, net: Net) -> list[Job]:
    keyword = company.get("slug", "software intern").replace("-", "+")
    jobs: list[Job] = []
    loop = asyncio.get_event_loop()

    for page in range(_MAX_PAGES):
        start = page * 10
        url = _SEARCH_URL.format(keyword=keyword, start=start)
        page_jobs = await loop.run_in_executor(_EXECUTOR, _scrape_page, url)
        
        if not page_jobs:
            if page == 0:
                raise RuntimeError("Indeed rate limited or returned 0 jobs on page 1")
            break
            
        jobs.extend(page_jobs)
        await asyncio.sleep(2.5)  # Indeed is strict, wait between pages

    return jobs
