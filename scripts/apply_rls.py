"""Apply RLS policies to all pipeline tables in Supabase.

Requires:
    SUPABASE_URL        https://<project-ref>.supabase.co
    SUPABASE_SERVICE_KEY  <service_role_key>

Run:
    python scripts/apply_rls.py
"""

import os
import sys

try:
    from supabase import create_client
except ImportError:
    print("Install: pip install supabase")
    sys.exit(1)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SERVICE_KEY:
    print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.")
    sys.exit(1)

# Each statement independently idempotent
STATEMENTS = [
    # Enable RLS
    "ALTER TABLE companies         ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE jobs              ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE company_health    ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE scrape_runs       ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE drop_observations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE known_windows     ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE app_state         ENABLE ROW LEVEL SECURITY",
    # Public read policies (idempotent via IF NOT EXISTS)
    """
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'companies' AND policyname = 'Public read companies') THEN
            CREATE POLICY "Public read companies" ON companies FOR SELECT TO anon USING (true);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Public read jobs') THEN
            CREATE POLICY "Public read jobs" ON jobs FOR SELECT TO anon USING (true);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'scrape_runs' AND policyname = 'Public read scrape_runs') THEN
            CREATE POLICY "Public read scrape_runs" ON scrape_runs FOR SELECT TO anon USING (true);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'drop_observations' AND policyname = 'Public read drop_observations') THEN
            CREATE POLICY "Public read drop_observations" ON drop_observations FOR SELECT TO anon USING (true);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'known_windows' AND policyname = 'Public read known_windows') THEN
            CREATE POLICY "Public read known_windows" ON known_windows FOR SELECT TO anon USING (true);
        END IF;
    END $$
    """,
]


def main() -> None:
    print(f"Connecting to {SUPABASE_URL}")
    _client = create_client(SUPABASE_URL, SERVICE_KEY)

    # supabase-py doesn't expose raw SQL, but we can call the Postgres REST API
    # via httpx using the service key which has access to the SQL endpoint.
    import httpx

    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    for stmt in STATEMENTS:
        stmt = stmt.strip()
        label = stmt[:60].replace("\n", " ")
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/query",
            headers=headers,
            json={"query": stmt},
            timeout=20,
        )
        if resp.status_code in (200, 204):
            print(f"  ✅  {label}…")
        else:
            # Supabase's PostgREST doesn't expose raw SQL — use the SQL API endpoint
            # (available when the service key has permissions)
            resp2 = httpx.post(
                # SQL editor endpoint (project-level API, not PostgREST)
                f"https://api.supabase.com/v1/projects/{SUPABASE_URL.split('//')[-1].split('.')[0]}/database/query",
                headers={
                    "Authorization": f"Bearer {SERVICE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"query": stmt},
                timeout=20,
            )
            if resp2.status_code in (200, 204):
                print(f"  ✅  {label}…")
            else:
                print(f"  ⚠️   HTTP {resp2.status_code} for: {label}")
                print(f"       {resp2.text[:200]}")

    print()
    print("Done. If any statement failed with 'endpoint not found', paste the SQL")
    print("block from schema.sql section 9 into:")
    print("  https://supabase.com/dashboard/project/zvanrgppleycfqwfpxjd/sql/new")


if __name__ == "__main__":
    main()
