"""Quick smoke test for India/Remote region support."""
import sys
sys.path.insert(0, "src")

from intern_engine import config, filters, pipeline

print("=== Import Check ===")
print(f"All imports OK")
print(f"Connectors: {list(pipeline.CONNECTORS.keys())}")

print("\n=== Config Check ===")
cfg = config.load_config()
print(f"Regions: {cfg.get('regions')}")
print(f"want_india: {config.want_india(cfg)}")
print(f"want_remote: {config.want_remote(cfg)}")
print(f"want_us: {config.want_us(cfg)}")

print("\n=== India Location Detection ===")
tests_india = [
    ("Bangalore, India", True),
    ("Bengaluru, Karnataka", True),
    ("Hyderabad, Telangana", True),
    ("Mumbai, Maharashtra", True),
    ("Pune, India", True),
    ("Gurgaon, Haryana", True),
    ("San Francisco, CA", False),
    ("New York, NY", False),
    ("London, UK", False),
]
for loc, expected in tests_india:
    result = filters.is_india(loc)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: is_india('{loc}') = {result} (expected {expected})")

print("\n=== Remote/Hybrid Detection ===")
tests_remote = [
    ("Remote", True),
    ("Remote - India", True),
    ("Hybrid - Bangalore", True),
    ("Work From Home", True),
    ("San Francisco, CA", False),
    ("Bangalore, India", False),
]
for loc, expected in tests_remote:
    result = filters.is_remote_or_hybrid(loc)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: is_remote_or_hybrid('{loc}') = {result} (expected {expected})")

print("\n=== Region OK (India + Remote mode) ===")
tests_region = [
    ("Bangalore, India", True),
    ("Remote", True),
    ("Remote - India", True),
    ("Hybrid - Bangalore", True),
    ("San Francisco, CA", False),
    ("New York, NY", False),
    ("Remote - US", False),
    ("Remote - Nationwide", False),
    ("CAD Remote - ON", False),
]
for loc, expected in tests_region:
    result = filters.region_ok(loc, want_us=False, want_canada=False,
                               want_india=True, want_remote=True)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: region_ok('{loc}') = {result} (expected {expected})")

print("\nDone!")
