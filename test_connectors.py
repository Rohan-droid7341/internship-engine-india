import asyncio
import sys
sys.path.insert(0, "src")
import httpx
from intern_engine.connectors import unstop, internshala
from intern_engine.net import Net, HostLimiter

async def test_connectors():
    print("Testing Unstop connector...")
    limiter = HostLimiter(8)
    async with httpx.AsyncClient() as client:
        net = Net(client, limiter)
        
        # Test Unstop
        unstop_company = {"name": "Unstop - Software Engineering", "slug": "software-engineering", "ats": "unstop"}
        try:
            unstop_jobs = await unstop.fetch(unstop_company, net)
            print(f"  Unstop fetched {len(unstop_jobs)} jobs.")
            if unstop_jobs:
                print(f"  Sample Unstop job: {unstop_jobs[0].title} at {unstop_jobs[0].company} ({unstop_jobs[0].location})")
        except Exception as e:
            print(f"  Unstop error: {e}")

        # Test Internshala
        print("\nTesting Internshala connector...")
        internshala_company = {"name": "Internshala - Computer Science", "slug": "computer-science-internship", "ats": "internshala"}
        try:
            internshala_jobs = await internshala.fetch(internshala_company, net)
            print(f"  Internshala fetched {len(internshala_jobs)} jobs.")
            if internshala_jobs:
                print(f"  Sample Internshala job: {internshala_jobs[0].title} at {internshala_jobs[0].company} ({internshala_jobs[0].location})")
        except Exception as e:
            print(f"  Internshala error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connectors())
