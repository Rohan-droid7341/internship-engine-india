import asyncio
import json
import httpx
import re

async def check_ats(company_name, slug_candidates):
    async with httpx.AsyncClient() as client:
        for slug in slug_candidates:
            # Check Greenhouse
            try:
                r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=5.0)
                if r.status_code == 200:
                    return {"name": company_name, "slug": slug, "ats": "greenhouse"}
            except: pass
            
            # Check Lever
            try:
                r = await client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=5.0)
                if r.status_code == 200 and len(r.json()) > 0:
                    return {"name": company_name, "slug": slug, "ats": "lever"}
            except: pass

            # Check Ashby
            try:
                r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=5.0)
                if r.status_code == 200:
                    return {"name": company_name, "slug": slug, "ats": "ashby"}
            except: pass
            
            # Check Workable
            try:
                r = await client.post(f"https://apply.workable.com/api/v3/accounts/{slug}/jobs", json={"query": ""}, timeout=5.0)
                if r.status_code == 200:
                    return {"name": company_name, "slug": slug, "ats": "workable"}
            except: pass
            
    return None

async def main():
    companies_to_add = [
        "Acko", "Apna", "BharatPe", "CoinDCX", "Dailyhunt", "Darwinbox", "Delhivery",
        "Digit Insurance", "Drip Capital", "Dunzo", "Eruditus", "Exotel", "Innovaccer",
        "Khatabook", "MindTickle", "MPL", "Nykaa", "OYO", "PharmEasy", "Spinny",
        "Urban Company", "Vedantu", "Vymo", "Zepto", "BNY Mellon", "Wells Fargo",
        "DE Shaw", "ThoughtSpot", "Directi", "Media.net", "Curefit", "Myntra", 
        "Udaan", "InMobi", "Zeta", "Rubrik", "Nutanix", "AlphaGrep", "Quadeye", 
        "Graviton", "WorldQuant", "Tower Research", "Deel", "Arcesium"
    ]
    
    with open('data/companies.json', 'r', encoding='utf-8') as f:
        existing_companies = json.load(f)
        
    existing_names = {c['name'].lower() for c in existing_companies}
    existing_names.update({c['name'].lower() + ' india' for c in existing_companies})
    existing_slugs = {c['slug'].lower() for c in existing_companies}
    
    found_new = []
    
    for name in companies_to_add:
        if name.lower() in existing_names or f"{name.lower()} india" in existing_names:
            continue
            
        slugs = [
            name.lower().replace(" ", ""),
            name.lower().replace(" ", "-"),
            name.lower().replace(" ", "_"),
            name.split()[0].lower(),
            name.lower().replace(" ", "") + "india",
            name.split()[0].lower() + "india"
        ]
        
        # skip if we already have the most common slug
        if any(s in existing_slugs for s in slugs):
            continue
            
        print(f"Checking {name}...")
        result = await check_ats(name, slugs)
        if result:
            print(f"  FOUND: {result}")
            found_new.append(result)
            existing_slugs.add(result['slug'])
        else:
            print(f"  Not found on supported ATS")
            
    if found_new:
        existing_companies.extend(found_new)
        with open('data/companies.json', 'w', encoding='utf-8') as f:
            json.dump(existing_companies, f, indent=2)
        print(f"\nAdded {len(found_new)} new companies to data/companies.json")

if __name__ == "__main__":
    asyncio.run(main())
