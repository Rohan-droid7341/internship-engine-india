"""Wellfound (AngelList) job search connector.

Uses Scrapling's StealthyFetcher for a best-effort public scrape.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

logger = logging.getLogger("intern_engine.connectors.wellfound")

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wellfound")

_SEARCH_URL = "https://wellfound.com/role/l/software-engineer/india"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Regex for parsing Next.js JSON data from Wellfound HTML
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)


def _scrape_page(url: str) -> list[Job]:
    """Fetch Wellfound HTML, extract Apollo GraphQL cache, and extract internship jobs."""
    try:
        import os

        from scrapling.fetchers import StealthyFetcher

        proxy = os.environ.get("WORKDAY_PROXY")
        fetcher = StealthyFetcher(auto_match=False, proxy=proxy) if proxy else StealthyFetcher(auto_match=False)
        resp = fetcher.get(url, headers=_HEADERS, timeout=30, stealth=True)
        html = resp.content or ""

        match = _NEXT_DATA_RE.search(html)
        if not match:
            return []

        jobs: list[Job] = []
        try:
            next_data = json.loads(match.group(1))
            page_props = next_data.get("props", {}).get("pageProps", {})
            apollo_state = page_props.get("initialApolloState", {})
            for key, val in apollo_state.items():
                if not (key.startswith("JobListing:") and isinstance(val, dict)):
                    continue
                try:
                    title = val.get("title")
                    job_id = val.get("id")
                    if not title or not job_id or "intern" not in title.lower():
                        continue

                    # Find company
                    company_ref = val.get("startup", {}).get("__ref", "")
                    company = "Unknown"
                    company_slug = "unknown"
                    if company_ref and company_ref in apollo_state:
                        comp_data = apollo_state[company_ref]
                        company = comp_data.get("name", "Unknown")
                        company_slug = comp_data.get("slug", "unknown")

                    loc_names = val.get("locationNames")
                    location = loc_names[0] if isinstance(loc_names, list) and loc_names else "India"
                    url = f"https://wellfound.com/jobs/{job_id}"

                    jobs.append(
                        Job(
                            id=f"wellfound:{job_id}",
                            source="wellfound",
                            company=company,
                            company_slug=company_slug,
                            title=title,
                            location=location,
                            url=url,
                            posted_at=None,
                        )
                    )
                except Exception:
                    continue
        except (KeyError, json.JSONDecodeError):
            pass

        return jobs
    except Exception as exc:
        logger.warning(f"Wellfound scrape failed: {exc}")
        return []


async def fetch(company: dict, net: Net) -> list[Job]:
    # Aggregator: ignores company parameter
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(_EXECUTOR, _scrape_page, _SEARCH_URL)
    if not jobs:
        logger.warning("Wellfound returned 0 jobs (rate limited or empty)")
        return []
    return jobs
