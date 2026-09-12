"""Amazon Jobs search API: public JSON, one fixed endpoint.

Specifically targets Amazon India openings (country=IND).
The search payload includes each job's description and qualifications.
"""

from __future__ import annotations

from datetime import datetime

from ..models import Job
from ..net import Net

URL = "https://www.amazon.jobs/en/search.json"
_SEARCH_TERMS = ("intern", "internship", "apprentice")


def _posted(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            continue
    return None


def _format_location(loc: str | None) -> str:
    if not loc:
        return "India"
    cleaned = loc.strip()
    if cleaned.endswith(", IND") or cleaned.endswith(" IND"):
        cleaned = cleaned[:-3] + "India"
    return cleaned


async def fetch(company: dict, net: Net) -> list[Job]:
    jobs: list[Job] = []
    seen_ids: set[str] = set()

    for term in _SEARCH_TERMS:
        for offset in (0, 100):
            params = {
                "country": "IND",
                "base_query": term,
                "result_limit": 100,
                "offset": offset,
                "sort": "recent",
            }
            data = await net.get_json(URL, params=params)
            results = data.get("jobs", [])
            for j in results:
                job_id = str(j.get("id_icims") or j.get("id") or j.get("job_path") or "")
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                path = j.get("job_path") or ""
                description = " ".join(
                    str(j.get(k) or "")
                    for k in ("description", "basic_qualifications", "preferred_qualifications")
                )
                loc = _format_location(j.get("normalized_location") or j.get("location"))
                jobs.append(
                    Job(
                        id=f"amazon:amazon:{job_id}",
                        source="amazon",
                        company="Amazon",
                        company_slug="amazon",
                        title=(j.get("title") or "").strip(),
                        location=loc,
                        url=("https://www.amazon.jobs" + path) if path else "https://www.amazon.jobs",
                        posted_at=_posted(j.get("posted_date")),
                        description=description.strip() or None,
                    )
                )
            if len(results) < 100:
                break
    return jobs
