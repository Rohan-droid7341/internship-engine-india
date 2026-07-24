import json

with open('data/companies.json', 'r', encoding='utf-8') as f:
    current = json.load(f)
with open('data/discovered_india.json', 'r', encoding='utf-8') as f:
    discovered = json.load(f)
with open('data/subagent_india.json', 'r', encoding='utf-8') as f:
    subagent = json.load(f)

merged = {}

for c in current:
    key = f"{c['ats']}:{c['slug']}"
    merged[key] = c

for c in discovered:
    key = f"{c['ats']}:{c['slug']}"
    if key not in merged:
        merged[key] = c

for c in subagent:
    if 'ats' in c and 'slug' in c:
        key = f"{c['ats']}:{c['slug']}"
        if key not in merged:
            merged[key] = c

final_list = list(merged.values())

with open('data/companies.json', 'w', encoding='utf-8') as f:
    json.dump(final_list, f, indent=2)

print(f"Merged successfully. Total unique companies: {len(final_list)}")
