"""Internshala jobs scraper: AJAX HTML."""
from __future__ import annotations
import re
from ..models import Job
from ..net import Net

URL_TEMPLATE = "https://internshala.com/internships_ajax/internship_list_container_ajax/{category}/page-{page}/"
_MAX_PAGES = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}

# Regex to extract job details from HTML without external dependencies
_URL_TITLE_RE = re.compile(r'<h3 class="heading_4_5 profile">\s*<a href="(/internship/detail/[^"]+)".*?>(.*?)</a>', re.DOTALL)
_COMPANY_RE = re.compile(r'<div class="heading_6 company_name">\s*(?:<a[^>]*>)?\s*(.*?)\s*(?:</a>)?\s*</div>', re.DOTALL)
_LOCATION_RE = re.compile(r'<a class="location_link view_detail_button"[^>]*>\s*(.*?)\s*</a>', re.DOTALL)

async def fetch(company: dict, net: Net) -> list[Job]:
    category = company["slug"]
    jobs = []
    
    for page in range(1, _MAX_PAGES + 1):
        url = URL_TEMPLATE.format(category=category, page=page)
        
        try:
            # We use get_json because net handles HTTP requests and rate limits. 
            # The API returns JSON with an HTML fragment.
            data = await net.get_json(url, headers=HEADERS)
        except Exception:
            # If the response isn't JSON or fails, stop paginating
            break
            
        html = data.get("html", "")
        if not html:
            break
            
        # Split by internship_meta to get individual cards roughly
        cards = html.split('<div class="internship_meta">')[1:]
        
        for card in cards:
            url_title_match = _URL_TITLE_RE.search(card)
            if not url_title_match:
                continue
                
            path = url_title_match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', url_title_match.group(2)).strip()
            
            # Extract internal job ID from the path (usually ends with -ID)
            job_id_match = re.search(r'-([a-zA-Z0-9]+)$', path)
            job_id = job_id_match.group(1) if job_id_match else path
            
            comp_match = _COMPANY_RE.search(card)
            comp_name = re.sub(r'<[^>]+>', '', comp_match.group(1)).strip() if comp_match else "Unknown"
            
            loc_match = _LOCATION_RE.search(card)
            location = re.sub(r'<[^>]+>', '', loc_match.group(1)).strip() if loc_match else "—"
            
            jobs.append(
                Job(
                    id=f"internshala:{category}:{job_id}",
                    source="internshala",
                    company=comp_name,
                    company_slug=category,
                    title=title,
                    location=location,
                    url=f"https://internshala.com{path}",
                    posted_at=None,
                )
            )
            
    return jobs
