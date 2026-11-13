# AUDIT — Internship Engine: Bugs, Fixes & Cleanup Plan (v3)

**Date:** 2026-11-14 · **Status:** completed & verified (189 passing tests, 0 lint errors, 0 accuracy violations) · **Executor:** Antigravity
**v3 changes:** merged external review corrections — live host is Vercel (Render/Docker deleted), Greenhouse content fix is `html.unescape` (not base64), atomic-write fix extended to `store.save`, pagination fix covers `get_open_jobs`, digest accumulates roles across runs, deletions synchronized with `run.py`/`update.yml`, dormant unstop fix dropped.

## Decision log

| Decision | Source |
|---|---|
| Live deployment = Vercel (`https://internship-engine-india.vercel.app`) — verified live; Render/Docker are unused | User + verified |
| Subscribe endpoint stays open (no rate-limit / double opt-in) | User |
| Gemini model = `gemini-2.0-flash` (free tier) | User |
| Delete audit (`audit.yml` + `tools/audit_seasons.py`) | User |
| Keep linkedin connector file, stay **dormant** (not registered) | User |
| Delete indeed connector + its 9 registry entries | User |
| Delete CSV feature | User |
| Delete GitHub Pages output (docs dashboard/unsubscribe/api JSON); web app is the only live surface | User |
| Remove Feedrabbit links | User |
| Delete ROADMAP.md | User |
| Leave harmless-but-stale internals alone (skills dead regexes, priority.py, candidates.json) | User |
| Keys: no rotation — remove all committed traces, read from env only | User |
| Skip unstop connector fix (dormant) | External review + user |

## Deferred (TBD)

- **`scripts/apply_rls.py`:** left in place for now (broken but harmless; superseded by schema.sql §9). Delete later on user call.

---

## Part 1 — Breaking bugs (🔴)

1. **`readme.py:344`** — calls `filters.is_foreign()`; real function is `is_foreign_country()` (filters.py:615). Any remote foreign role crashes README generation.
   *Fix:* rename the call; add regression test with a remote foreign location.
2. **`requirements.txt:2`** — `requests==2.34.2` is not a real PyPI release; every fresh CI install fails.
   *Fix:* `requests==2.32.4`.
3. **`mailer.py:86-88` + `run.py:73`** — `should_send()` bypasses the 22h throttle whenever `new_ids` is passed (always in CI) → up to 8 emails/day despite "one email a day".
   *Fix:* enforce `_MIN_HOURS_BETWEEN` against `last_digest_at` in every path; **and** select roles with `first_seen_at > last_digest_at` (not run-local `new_ids`) so jobs discovered during intervening runs are never lost from the digest.
4. **`compensation.py:588` + `update.yml:54`** — model `gemini-3.8-flash` doesn't exist; all grounding calls 404.
   *Fix:* set both to `gemini-2.0-flash`; stop hardcoding in the workflow (env owns it).
5. **`enrich.py:42`** — Greenhouse boards API returns `content` as **HTML-escaped HTML** (verified live: `"&lt;h2&gt;..."`), never unescaped → pay/sponsorship classification reads escaped gibberish for the largest source; test fixtures mask it.
   *Fix:* `html.unescape(data.get("content") or "")`; fix the test fixture to send escaped HTML.

## Part 2 — Key leaks & security (no rotation → traces must fully vanish)

6. **`data/config.json:21-22`** — Supabase URL + anon key committed publicly.
   *Fix:* read from env (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) in config.py; engine + web read env only; requires 2 new GitHub Secrets (note for user). Remove the JSON keys entirely.
7. **`compensation.py:592,614,635`** — Gemini key in URL query string; leaked via logged exception text and `resp.text[:120]`.
   *Fix:* send key via `x-goog-api-key` header; sanitize everything logged (no URL echo, no response body).
8. **`tools/test_whatsapp.py:13-14`** — prints real Twilio/phone values into CI logs. Remove prints.
9. *(Resolved by Part 5 D1)* — hardcoded keys in docs pages disappear when the Pages surface is deleted.
10. **`schema.sql:156`** — `unsubscribe_email` is SECURITY DEFINER without `SET search_path = pg_catalog, public`. Add it; add `security_invoker = true` to surviving views.
11. **`mailer.py:103,210,219,226-235`** — no URL scheme allowlist (`javascript:` links could reach inboxes); raw scraped title in subject; silent truncation of subscriber #251+; missing `List-Unsubscribe` + `List-Unsubscribe-Post` headers (Gmail/Yahoo bulk-sender compliance).
    *Fix:* allowlist `http(s)://`, sanitize subject, log truncation, add headers.
12. **`web/app.py`** — failed Supabase client cached forever (:63-67); empty-but-healthy DB silently serves stale local JSON (:127,167,248); `get_all_jobs()` paginates but **`get_open_jobs()` (:118-124) does not** → PostgREST hard caps at 1,000 rows, silently dropping roles once the open pool crosses 1k.
    *Fix:* retry client creation when env present; distinguish DB-down from DB-empty; pagination guard with safety cap (max 25 pages) on **both** functions.

## Part 3 — Connector bugs (🔶)

13. **`naukri.py:106`** — `posted_at` = "Few Days Ago" text → staleness filter never fires for Naukri; latency stats garbage.
    *Fix:* resolve relative labels like `workday._resolve_posted` ("X Days Ago" → now−X, "Few Days Ago" → now−3d, "30+ Days Ago" → now−30d).
14. **`custom_careers.py:128`** — job IDs embed list position `i` → roles churn "new/closed" on every reorder.
    *Fix:* ID = `custom:{slug}:{md5(link)[:8]}` (one-time ID migration note).
15. **`wellfound.py:73,92`** — empty `locationNames[0]` IndexError drops the entire page via blanket except.
    *Fix:* per-record try/except; safe location extraction.
16. **`workday.py:49-52`** — "Posted 3 Hours Ago" → `None`; freshest roles lose dates.
    *Fix:* extend resolver to hours.
17. **`oracle.py:42-44,62`** — `limit`/`offset` as separate params likely ignored → page-size default breaks the pagination break condition.
    *Fix:* move into finder expression (`findReqs;siteNumber=CX_1,limit=50,offset=N`); verify live.
18. **Scrapers bypass `Net`** (internshala, naukri, wellfound, custom_careers; linkedin dormant): no retry/backoff/limiter/timeout policy; one empty page trips the 6h circuit breaker.
    *Fix:* route through `Net` where possible; for Scrapling-dependent ones unify timeout/retry; make empty page-1 a warning, not an exception.
19. **`pipeline.py` registry cleanup** — remove commented-out CONNECTORS entries + unused `instahyre`/`unstop` imports; delete 9 `indeed` entries from `companies.json`; linkedin's 12 entries stay (dormant).
    *Unstop connector code itself: left as-is (dormant, per decision log).*

## Part 4 — Engine logic (🔷)

20. **`observe.py:101`** — `count` increments per run per open role (measures runs, not roles); bug mirrored into Postgres `drop_observations`.
    *Fix:* count first-sightings only.
21. **`health.py:61-64,57-59`** — naive `last_attempt_at` vs aware `now` raises uncaught `TypeError`; repeat offender with missing timestamp escapes quarantine.
    *Fix:* force UTC on parse, catch TypeError, quarantine when `consecutive_failures >= 3` regardless.
22. **Non-atomic state writes** — **`store.py:35-39` (the critical one: `data/jobs.json`)**, `observe.py:110-112`, `mailer.py:40-50`, `notify.py:120-128`: a crash/SIGTERM mid-write truncates the file; `store.load` then silently returns `{}` (total data loss); read-modify-write races between overlapping runs.
    *Fix:* shared `atomic_write_json(path, data)` helper in a new `intern_engine/utils.py` using `tempfile.NamedTemporaryFile` + `os.replace()` (**cross-platform: no fcntl — Windows + Linux CI safe**); wire into store.save, observe.save, health.save, mailer state, notify state; `observe.save()` also needs `makedirs(DATA_DIR, exist_ok=True)`.
23. **`db.py:310,309,167-171`** — `json.dumps` before JSONB insert (double-encoded state); emptied state rows never cleared in PG; jobs purged from JSON store never deleted from PG (unbounded growth).
    *Fix:* insert dict directly; delete rows absent from store; clear empty state rows.
24. **`schema.sql:217` vs trends.py/readme.py** — two different "days open" definitions; view sorts `first_seen_at` while everything else sorts `posted_at`.
    *Fix:* unify on posted→closed (views are being deleted in D9 anyway — moot after cleanup).
25. **`pipeline.py:164,234`** — undated roles bypass `max_age_days` entirely.
    *Fix:* apply cutoff to `first_seen_at` fallback.
26. **`pipeline.py:130`** — dedup winner between same-date duplicates depends on `asyncio.gather` completion order (nondeterministic).
    *Fix:* stable secondary tiebreak key.
27. **`config.py:69-76`** — zero schema validation (string `"cycles"` explodes per-character later; non-dict JSON crashes uncaught); `cycles[0]` unguarded in 4 places (`readme.py:508`, `dashboard.py:212`, `publish.py:119,226`).
    *Fix:* minimal validation + safe defaults.
28. **`config.py:42,48`** — `repo_slug` regex requires trailing `\s`; URL on the last line of `.git/config` (no newline) silently falls back to the hardcoded repo.
    *Fix:* drop the `\s`; add test.
29. **`notify.py:119,141,95,59` + `run.py:70-71`** — docstring says 65h, code gates 62h; hardcoded sandbox keyword `"join type-against"`; silent failure paths; "Discord alert" printed even when only WhatsApp sent.
    *Fix:* single constant, env-configured keyword, log failures, accurate run output.
30. **`net.py:44,86`** — `Retry-After` HTTP-date form ignored; retry-exhaustion error discards the last status code.

## Part 5 — Deletions (⚪)

| # | Item | Notes |
|---|------|-------|
| D1 | **GitHub Pages surface** | Delete static dashboard + unsubscribe HTML generation (`docs/index.html`, `docs/unsubscribe.html`, `dashboard.py` HTML writer) and `docs/api/*.json` writes (Vercel app serves `/api`). **Port the unsubscribe flow to the Vercel web app first** (see Part 3.1 of execution notes) so `mailer.py:215,224` links keep working. **Keep** `docs/feed.xml`, `docs/radar.ics`, `docs/trends-*.svg` as repo artifacts. Repoint all `config.pages_base()` links to `https://internship-engine-india.vercel.app`. Preserve dashboard.py logic still consumed elsewhere (radar/stats/feed) |
| D2 | **CSV feature** | `readme.py:520-544`, README line 258, `paths.CSV_PATH`, `data/internships.csv` |
| D3 | **Feedrabbit** | `readme.py:151-158` + header/footer references |
| D4 | **Audit** | `.github/workflows/audit.yml` + `tools/audit_seasons.py` (NameError-dead since sponsorship removal) |
| D5 | **Apology** | `.github/workflows/apology.yml` + `scripts/send_apology.py` (one-time Oct 2026 incident blast) |
| D6 | ~~Delete Vercel~~ → **INVERTED: keep Vercel, delete unused hosts** | Keep `vercel.json`, `api/index.py`, `api/requirements.txt` (live production host, verified). **Delete `render.yaml` + `Dockerfile`** (unused; git history preserves them) |
| D7 | **ROADMAP.md** | Entirely stale (US scope, "shipped" visa features, deleted-file references, wrong counts) |
| D8 | **Indeed connector** | `connectors/indeed.py` + 9 `companies.json` entries (linkedin stays, dormant) |
| D9 | **schema.sql** | `open_internships` view (zero refs), `company_posting_stats` view (never queried), `uuid-ossp` extension (unused) |
| D10 | **`requirements-dev.txt`** | Remove `reportlab==4.2.5` (imported nowhere) |
| D11 | **`.python-version` (3.12)** | Contradicts CI/pyproject (3.11) |
| D12 | **`data/compensation_cache.json`** | Perpetually `{}` after ~1,100 runs |
| D13 | **Dead code** | `db.enabled()`, `db.sync()`, `web/app.py:74,296`, `readme.py:162-164`, commented CONNECTORS entries, `.pytest_cache` stale cache |
| D14 | **Resume artifacts** | `resume_certa.*`, `test_user_res1.*`, `rc_final-1.png`, `resume_page-1.png` (~1.4MB) + gitignore patterns (`*.aux`, `*.log`, `*.out`, `resume*`) |
| D15 | **Root orphans** | `discover_startups.py`, `find_ats.py`, `extract_leetcode_companies.py` |

*Left alone (per user call):* skills.py dead pay/batch regexes, priority.py US company names, candidates.json pruning, `scripts/apply_rls.py` (TBD), companies.html full-registry render.

## Part 6 — README / docs refresh

31. "Updates every hour" badge (:176) + "polled every hour" (:232-233) → **every 3 hours** (actual cron).
32. Remove contradictory "Note on dates" section (:306-314) — claims undated dashes; reality: 100% dated.
33. Remove Feedrabbit; **repoint all `{pages}` links to `https://internship-engine-india.vercel.app`** — dashboard, RSS, JSON API, `#subscribe` anchor, unsubscribe links.
34. Derive "Platforms Scraped" footer (:294-299) from `pipeline.CONNECTORS` reality; drop deleted connectors.
35. Stale docstrings: `enrich.py:1-9`, `skills.py:3` reference the deleted `sponsorship` module.
36. `ARCHITECTURE.md`: remove `build_seasons.py` ref (:190), "17 sources" → real count, "93 tests" → 182, Pages refs → Vercel app, workflow table updated post-D4-D6, config examples → env vars (post key removal).
37. `PROJECT_CONTEXT.md`: refresh counts (163→182 tests; ~5,211→5,803 companies); note Pages removal.
38. `CONTRIBUTING.md:35`: `run.py all` = discover + harvest + update.
39. `README.md` regenerate automatically once readme.py is fixed (it's 100% machine-generated).

## Part 7 — Workflows / infra

40. **Synchronize deletions with CI + entrypoint** (critical — verified `update.yml:61-64` stages the deleted files):
    - `update.yml`: remove `data/*.csv`, `docs/index.html`, `docs/unsubscribe.html`, `docs/api/*.json` from the `git add` list.
    - `run.py`: remove `dashboard.generate` (Pages writer), `publish.write_api`, CSV writing from `cmd_update`; keep `trends.write_readme_charts`, `publish.write_feed`, `publish.write_radar_ics`.
41. **Silent-failure rebase-push loops** (`update.yml:71-74`, `discover.yml:50-53`): 3 failed rebases exit green → data silently lost. Add `exit 1` after the loop.
42. `ci.yml`: lint the full tree (`tools/`, `web/`, `scripts/`); replace nonexistent `ruff.toml` path filter with `pyproject.toml`; include `web/**` in trigger paths; **wire `tools/verify_accuracy.py` into CI** (functional but orphaned); fix stale "hourly" comments.
43. Add `timeout-minutes` to all scheduled jobs.
44. `update.yml`: stop hardcoding `GEMINI_MODEL` (env owns it — see #4).

## Part 8 — Tests

45. Regression tests for: #1, #3 (throttle + accumulation), #5 (escaped HTML), #13-17 connector parsing, #14 stable IDs, #20-22 (observe/health/atomic writes incl. store.save), #27-28 (config), #12 (web client retry + pagination guards on both functions).
46. New coverage: `notify.py`, `config.py`, end-to-end subscribe → unsubscribe against the new web route.
47. Fix tautological assertion `tests/test_mailer.py:35`.

## Execution order

| Batch | Items | Est. |
|---|---|---|
| 1 — Stop the bleeding | #1-5 (crash, pin, throttle+accumulation, model, escaped HTML) | ~2h |
| 2 — Key trace removal + security | #6-11 | ~2h |
| 3 — Web parity then deletions | unsubscribe route + pagination fixes first (#12), then D1-D15 + sync (#40) | ~3h |
| 4 — Connectors | #13-19 | ~3h |
| 5 — Engine logic | #20-30 | ~3.5h |
| 6 — README/docs | #31-39 | ~1.5h |
| 7 — Workflows | #40-44 (post-deletion sync included in Batch 3) | ~1.5h |
| 8 — Tests | #45-47 | ~3h |

**Notes for user (not code work):**
- Add GitHub Secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (after #6 removes them from `data/config.json`).
- Batch 3 ordering matters: build the web-app unsubscribe route + pagination fixes **before** deleting the Pages surface, so subscriber links never 404.
- CI must pass at every batch boundary (`pytest` + `ruff`).
- Company-discovery/mining plan lives separately in `DISCOVERY_PLAN.md`.
