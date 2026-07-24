import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath('src'))

from intern_engine import pipeline, filters

async def discover():
    with open('data/companies.json', 'r', encoding='utf-8') as f:
        existing = json.load(f)
        
    existing_slugs = {c['slug'].lower() for c in existing}
    
    # Get all company dirs from temp_repo
    repo_path = '../temp_repo'
    items = os.listdir(repo_path)
    company_names = []
    for item in items:
        if os.path.isdir(os.path.join(repo_path, item)) and not item.startswith('.'):
            company_names.append(item)
            
    # Filter out companies we already have
    missing_companies = [c for c in company_names if c.lower() not in existing_slugs]
    print(f"Found {len(missing_companies)} missing companies in the leetcode repo.", flush=True)
    
    # ATS platforms to brute-force
    ats_platforms = ['greenhouse', 'lever', 'workday', 'ashby', 'smartrecruiters', 'workable']
    
    candidates = []
    for c in missing_companies:
        for ats in ats_platforms:
            candidates.append({
                "name": c.title(),
                "slug": c,
                "ats": ats
            })
            
    print(f"Brute-forcing {len(candidates)} company+ATS combinations...", flush=True)
    
    async def mock_enrich(results, net, wd_net):
        return results
        
    all_found = []
    chunk_size = 500
    for i in range(0, len(candidates), chunk_size):
        batch = candidates[i:i+chunk_size]
        print(f"Processing chunk {i} to {i+chunk_size}...", flush=True)
        results, _ = await pipeline._fetch_all(batch, mock_enrich)
        
        for company, jobs, error in results:
            if error is not None:
                continue
            
            if not jobs:
                continue
                
            has_india = False
            for job in jobs:
                if filters.is_india(job.location):
                    has_india = True
                    break
                    
            if has_india:
                all_found.append(company)
                print(f"  [+] SUCCESS: Discovered {company['name']} on {company['ats']} with roles in India!", flush=True)
                
        # Incremental save
        winners_by_slug = {}
        for c in all_found:
            winners_by_slug[c['slug']] = c
            
        final_winners = list(winners_by_slug.values())
        print(f"--- Chunk complete. {len(final_winners)} new verified companies found so far. ---", flush=True)
        
        temp_list = existing + final_winners
        with open('data/companies.json', 'w', encoding='utf-8') as f:
            json.dump(temp_list, f, indent=2)

    print(f"\nDiscovery complete. Found {len(final_winners)} new verified companies.", flush=True)

if __name__ == "__main__":
    asyncio.run(discover())
