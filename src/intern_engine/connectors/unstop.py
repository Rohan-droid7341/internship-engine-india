"""Unstop jobs API: public search."""

from __future__ import annotations

from ..models import Job
from ..net import Net

URL = "https://unstop.com/api/public/opportunity/search-result"
_MAX_PAGES = 5
_MIN_STIPEND_INR = 50000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://unstop.com/internships",
    "Accept": "application/json",
}


async def fetch(company: dict, net: Net) -> list[Job]:
    category = company["slug"]
    jobs = []

    for page in range(1, _MAX_PAGES + 1):
        params = {"page": str(page), "opportunity": "internships", "searchTerm": category}
        data = await net.get_json(URL, params=params, headers=HEADERS)

        # Handle variations in response format
        items = (
            data.get("data", {}).get("data", [])
            if isinstance(data.get("data"), dict)
            else data.get("data", [])
        )
        if not items:
            items = data.get("opportunities", [])

        if not items:
            break

        for item in items:
            # Check stipend requirement: must be paid and >= 50,000 INR
            jd = item.get("jobDetail") or {}
            paid_unpaid = jd.get("paid_unpaid")
            if paid_unpaid != "paid":
                continue

            min_s = jd.get("min_salary") or 0
            max_s = jd.get("max_salary") or 0
            salary = max(min_s, max_s)
            if salary < _MIN_STIPEND_INR:
                continue

            pay_in = jd.get("pay_in") or "monthly"
            stipend_str = f"₹{salary:,}/{pay_in}"

            org = item.get("organisation", {})
            comp_name = org.get("name", "Unknown")

            cities = item.get("city", []) or jd.get("locations", [])
            location = ", ".join(cities) if cities else "India"

            path = (
                item.get("seo_url")
                or item.get("opportunityUrl")
                or item.get("public_url")
                or f"opportunity/{item.get('id')}"
            )
            url = path if path.startswith("http") else f"https://unstop.com/{path.lstrip('/')}"

            jobs.append(
                Job(
                    id=f"unstop:{category}:{item.get('id')}",
                    source="unstop",
                    company=comp_name,
                    company_slug=category,
                    title=(item.get("title") or "").strip(),
                    location=location,
                    url=url,
                    posted_at=item.get("start_date") or item.get("published_date"),
                    stipend=stipend_str,
                )
            )

        # Pagination check if applicable
        current_page = data.get("data", {}).get("current_page")
        last_page = data.get("data", {}).get("last_page")
        if current_page and last_page and current_page >= last_page:
            break

    return jobs
