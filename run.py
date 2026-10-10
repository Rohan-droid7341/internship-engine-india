"""Command-line entrypoint.

    python run.py harvest     # probe curated candidates -> data/companies.json
    python run.py discover    # mine public datasets for company tokens (big scale-up)
    python run.py update      # fetch -> filter -> enrich -> store -> publish everything
    python run.py all         # discover + harvest + update
    python run.py fetch-only  # fetch + enrich ONLY — no README, no website,
                              # no mailing, no Discord/WhatsApp, no Supabase.
                              # Safe for test branches to validate fetch logic.
"""

import os
import sys

# Make the package under src/ importable without installation.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from intern_engine import (  # noqa: E402
    dashboard,
    db,
    discover,
    harvester,
    health,
    mailer,
    notify,
    observe,
    pipeline,
    publish,
    readme,
    trends,
)


def cmd_harvest() -> None:
    found, candidates = harvester.harvest()
    print(f"Harvested {len(found)}/{len(candidates)} candidates -> data/companies.json")
    by_ats: dict[str, int] = {}
    for c in found:
        by_ats[c["ats"]] = by_ats.get(c["ats"], 0) + 1
    for ats, n in sorted(by_ats.items()):
        print(f"  {ats:<12} {n}")


def cmd_discover() -> None:
    companies, n_found = discover.discover()
    print(f"Discovered {n_found} tokens from public datasets.")
    print(f"Company list now has {len(companies)} companies -> data/companies.json")
    by_ats: dict[str, int] = {}
    for c in companies:
        by_ats[c["ats"]] = by_ats.get(c["ats"], 0) + 1
    for ats, n in sorted(by_ats.items()):
        print(f"  {ats:<12} {n}")


def cmd_update() -> None:
    if not os.path.exists(os.path.join("data", "companies.json")):
        print("No data/companies.json yet — run `python run.py harvest` first.")
        sys.exit(1)
    stats, store_data, new_ids = pipeline.run_update()
    trends.write_readme_charts(store_data)
    summary = readme.generate(store_data)
    dashboard.generate(store_data, stats)
    feed_entries = publish.write_feed(store_data)
    publish.write_api(store_data, stats)
    ics_events = publish.write_radar_ics(store_data)
    if db.full_sync(
        store_data=store_data,
        stats=stats,
        health_data=health.load(),
        observed=observe.load(),
    ):
        print("  synced to Postgres   yes")
    if notify.send_new_roles(store_data, new_ids):
        print(f"  Discord alert        {len(new_ids)} new roles")
    notify.check_sandbox_reminder()
    sent = mailer.send_digest(store_data, new_ids)
    if sent:
        print(f"  email alert          sent to {sent} subscribers ({len(new_ids)} new roles)")
    print("Update complete:")
    for k, v in stats.items():
        print(f"  {k:<24} {v}")
    print(f"  README open roles      {summary['open']}")
    print(f"  feed entries           {feed_entries}")
    print(f"  radar calendar events  {ics_events}")


def cmd_fetch_only() -> None:
    """Fetch + enrich ONLY.

    Intentionally skips every side-effect so new fetch logic can be validated
    safely on a test branch without touching:
      - README / website / feed / API / calendar / SVG charts
      - Supabase / Postgres sync
      - Email digest (Brevo)
      - Discord / WhatsApp notifications

    Reads from and writes ONLY to data/jobs.json (raw store).
    Run with:  python run.py fetch-only
    """
    if not os.path.exists(os.path.join("data", "companies.json")):
        print("No data/companies.json yet — run `python run.py harvest` first.")
        sys.exit(1)

    print("⚙  fetch-only mode — no README, no website, no mailing, no notifications")
    stats, store_data, new_ids = pipeline.run_update()

    print("\nFetch complete (raw stats):")
    for k, v in stats.items():
        print(f"  {k:<24} {v}")
    print(f"  new role ids           {len(new_ids)}")
    print("\n✅  fetch-only run done. Nothing was published or notified.")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "harvest":
        cmd_harvest()
    elif cmd == "discover":
        cmd_discover()
    elif cmd == "update":
        cmd_update()
    elif cmd == "fetch-only":
        cmd_fetch_only()
    elif cmd == "all":
        cmd_discover()
        cmd_harvest()
        cmd_update()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
