"""Unstop jobs API: public search."""
from __future__ import annotations
from ..models import Job
from ..net import Net

URL = "https://unstop.com/api/public/opportunity/search-result"
_MAX_PAGES = 3

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
        items = data.get("data", {}).get("data", []) if isinstance(data.get("data"), dict) else data.get("data", [])
        if not items:
            items = data.get("opportunities", [])
        
        if not items:
            break
            
        for item in items:
            org = item.get("organisation", {})
            comp_name = org.get("name", "Unknown")
            
            cities = item.get("city", [])
            location = ", ".join(cities) if cities else "—"
            
            path = item.get("seo_url") or item.get("opportunityUrl") or item.get("public_url") or f"opportunity/{item.get('id')}"
            
            jobs.append(
                Job(
                    id=f"unstop:{category}:{item.get('id')}",
                    source="unstop",
                    company=comp_name,
                    company_slug=category,
                    title=(item.get("title") or "").strip(),
                    location=location,
                    url=f"https://unstop.com/{path.lstrip('/')}",
                    posted_at=item.get("start_date") or item.get("published_date"),
                )
            )
            
        # Pagination check if applicable
        current_page = data.get("data", {}).get("current_page")
        last_page = data.get("data", {}).get("last_page")
        if current_page and last_page and current_page >= last_page:
            break
            
    return jobs
