import asyncio
import json
import os
import sys

# Ensure src is in pythonpath
sys.path.insert(0, os.path.abspath('src'))

from intern_engine import pipeline, filters, config

async def run_spider():
    # Load old seed list
    with open('data/companies_old.json', 'r', encoding='utf-8') as f:
        seed_companies = json.load(f)

    print(f"Loaded {len(seed_companies)} companies to scan for India presence...")

    # We use a custom fetch_all wrapper to just hit the APIs and check locations.
    # To avoid rate limits and memory issues, we'll process in chunks or rely on pipeline's built-in semaphore.
    
    cfg = config.load_config()
    
    # We want to use the pipeline's fetch logic
    async def process_batch(companies_batch):
        # We don't need a complex enrich stage, we just need the fetch results
        async def mock_enrich(results, net, wd_net):
            # Just return the raw results directly
            return results
            
        results, _ = await pipeline._fetch_all(companies_batch, mock_enrich)
        # _fetch_all returns whatever mock_enrich returns. So results is a list of (company, jobs, error)
        
        found = []
        for company, jobs, error in results:
            if error is not None:
                continue
            
            # Check if any job is in India
            has_india = False
            for job in jobs:
                if filters.is_india(job.location):
                    has_india = True
                    break
            
            if has_india:
                found.append(company)
                print(f"  [+] Discovered {company['name']} has roles in India!")
                
        return found
        
    all_found = []
    chunk_size = 500
    for i in range(0, len(seed_companies), chunk_size):
        batch = seed_companies[i:i+chunk_size]
        print(f"Processing chunk {i} to {i+chunk_size}...")
        found = await process_batch(batch)
        all_found.extend(found)
        
    print(f"\nSpider complete. Found {len(all_found)} companies with live India roles out of {len(seed_companies)}.")
    
    # Save the discovered companies
    with open('data/discovered_india.json', 'w', encoding='utf-8') as f:
        json.dump(all_found, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_spider())
