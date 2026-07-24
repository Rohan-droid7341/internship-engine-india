import asyncio
import aiohttp
import json
import re

ATS_SYSTEMS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithPostings",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
}

async def check_ats(session, company_name):
    slug = re.sub(r'[^a-z0-9]', '', company_name.lower())
    results = []
    
    for ats_name, url_template in ATS_SYSTEMS.items():
        if ats_name == "ashby":
            try:
                payload = {
                    "operationName": "ApiJobBoardWithPostings",
                    "variables": {"organizationHostedJobsPageName": slug},
                    "query": "query ApiJobBoardWithPostings($organizationHostedJobsPageName: String!) { jobBoard: jobBoardWithPostings(organizationHostedJobsPageName: $organizationHostedJobsPageName) { jobPostings { id } } }"
                }
                async with session.post(url_template, json=payload, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data", {}).get("jobBoard"):
                            results.append({"name": company_name, "slug": slug, "ats": ats_name})
            except:
                pass
        else:
            url = url_template.format(slug=slug)
            try:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        results.append({"name": company_name, "slug": slug, "ats": ats_name})
            except:
                pass
    return results

async def main():
    # Provide a list of top Indian startups
    startups = [
        "Unacademy", "Razorpay", "Meesho", "Groww", "Pine Labs",
        "Dunzo", "Swiggy", "Zomato", "PhonePe", "ShareChat",
        "Dream11", "BrowserStack", "Postman", "Khatabook", "CoinSwitch"
    ]
    
    async with aiohttp.ClientSession() as session:
        tasks = [check_ats(session, name) for name in startups]
        all_results = await asyncio.gather(*tasks)
        
    found = []
    for r in all_results:
        found.extend(r)
        
    with open('data/companies.json', 'r', encoding='utf-8') as f:
        existing = json.load(f)
        
    existing_slugs = {c['slug'] for c in existing}
    
    new_adds = 0
    for c in found:
        if c['slug'] not in existing_slugs:
            existing.append(c)
            new_adds += 1
            print(f"[+] Found ATS for {c['name']} on {c['ats']}!")
            
    with open('data/companies.json', 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2)
        
    print(f"Added {new_adds} new startups to companies.json.")

if __name__ == "__main__":
    asyncio.run(main())
