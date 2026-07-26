"""Custom career page connector for companies without a standard ATS.

For companies like Flipkart, Ola, CRED, NPCI, Groww, etc. that host their
own career pages, this connector uses Scrapling to fetch and parse the page.

Each company entry in companies.json needs:
    {
      "name": "Flipkart",
      "slug": "flipkart",
      "ats": "custom",
      "careers_url": "https://www.flipkartcareers.com/#!/joblist",
      "job_link_pattern": "/job/"     # optional: substring in job detail links
    }

Scrapling's adaptive selectors auto-detect job links on the page.
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Job
from ..net import Net

_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="custom")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Common regex patterns for extracting job titles and links from raw HTML
_LINK_RE = re.compile(
    r'href=["\']([^"\']*(?:job|career|opening|position|role)[^"\']*)["\']', re.IGNORECASE
)
_TITLE_RE = re.compile(
    r'<(?:h[1-4]|span|div|a)[^>]*class="[^"]*(?:title|position|role|job-name)[^"]*"[^>]*>\s*([^<]{5,100})',
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _scrape_careers_page(url: str, link_pattern: str | None) -> list[dict]:
    """Fetch the careers page and extract job links + titles."""
    results: list[dict] = []
    try:
        from scrapling.fetchers import Fetcher

        fetcher = Fetcher(auto_match=False)
        resp = fetcher.get(url, headers=_HEADERS, timeout=25)
        html = resp.content or ""
    except ImportError:
        return []
    except Exception:
        return []

    # Find all job-related anchor links
    seen_urls: set[str] = set()
    for link_match in _LINK_RE.finditer(html):
        href = link_match.group(1)
        if link_pattern and link_pattern not in href:
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Make absolute URL
        if href.startswith("http"):
            abs_url = href
        elif href.startswith("/"):
            from urllib.parse import urlparse

            parsed = urlparse(url)
            abs_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            abs_url = url.rstrip("/") + "/" + href.lstrip("/")

        # Try to get title from nearby context (rough)
        idx = html.find(link_match.group(0))
        context = html[max(0, idx - 200) : idx + 500]
        title_m = _TITLE_RE.search(context)
        title = _clean(title_m.group(1)) if title_m else ""
        if not title:
            # fallback: grab text inside the <a> tag
            a_text_m = re.search(
                r">" + re.escape(href.split("/")[-1].replace("-", " ")) + r"<",
                context,
                re.IGNORECASE,
            )
            title = (
                href.split("/")[-1].replace("-", " ").replace("_", " ").title()
                if not a_text_m
                else ""
            )

        results.append({"url": abs_url, "title": title or "Open Role"})
        if len(results) >= 30:  # cap per company
            break

    return results


async def fetch(company: dict, net: Net) -> list[Job]:
    """Scrape a custom career page and return any job-like links found."""
    careers_url = company.get("careers_url", "")
    if not careers_url:
        return []

    slug = company.get("slug", "unknown")
    link_pattern = company.get("job_link_pattern")
    loop = asyncio.get_event_loop()

    raw = await loop.run_in_executor(_EXECUTOR, _scrape_careers_page, careers_url, link_pattern)

    jobs: list[Job] = []
    for i, item in enumerate(raw):
        jobs.append(
            Job(
                id=f"custom:{slug}:{i}:{re.sub(r'[^a-z0-9]', '', item['url'][-30:].lower())}",
                source="custom",
                company=company.get("name", slug.title()),
                company_slug=slug,
                title=item["title"],
                location="India",
                url=item["url"],
                posted_at=None,
            )
        )

    return jobs
