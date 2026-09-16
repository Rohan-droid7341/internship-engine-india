-- internship-engine-india: Postgres schema (Supabase)
--
-- This file is the version-controlled source of truth for the database.
-- Apply with:  psql $DATABASE_URL -f schema.sql
-- Or paste into the Supabase SQL editor.
--
-- The JSON files in data/ remain the CI pipeline's working state;
-- Postgres is the analytical / API / query layer, synced at the end
-- of every pipeline run by db.py.

-- ============================================================
-- 1. companies — the ATS board registry
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
    key         TEXT PRIMARY KEY,               -- "greenhouse:stripe"
    ats         TEXT NOT NULL,
    slug        TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ats, slug)
);
CREATE INDEX IF NOT EXISTS idx_companies_ats ON companies (ats);

-- ============================================================
-- 2. jobs — the core internship data
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,           -- "greenhouse:stripe:123456"
    company_key     TEXT REFERENCES companies(key) ON DELETE SET NULL,
    source          TEXT NOT NULL,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT NOT NULL DEFAULT '',
    url             TEXT,
    category        TEXT NOT NULL DEFAULT 'Other',
    season          TEXT,
    season_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    region          TEXT,                       -- "India" / "Remote" / "International"
    -- Compensation
    salary          TEXT,                       -- USD: "$45/hr", "$120k/yr"
    stipend         TEXT,                       -- INR: "₹25k/mo", "10 LPA"
    -- India enrichment fields
    degree          TEXT,                       -- "B.Tech/BS", "M.Tech/MS", "PhD"
    experience      TEXT,                       -- "0-1 Yr", "Fresher", "2+ Yrs"
    batch           TEXT,                       -- graduation year, e.g. "2026"
    skills          TEXT[],                     -- '{"Python","React","SQL"}'
    -- Lifecycle timestamps
    posted_at       TIMESTAMPTZ,               -- real publish date, frozen once set
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    closed_at       TIMESTAMPTZ,
    enriched_at     TIMESTAMPTZ,
    is_open         BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_jobs_open       ON jobs (is_open) WHERE is_open;
CREATE INDEX IF NOT EXISTS idx_jobs_season     ON jobs (season);
CREATE INDEX IF NOT EXISTS idx_jobs_company    ON jobs (company_key);
CREATE INDEX IF NOT EXISTS idx_jobs_source     ON jobs (source);
CREATE INDEX IF NOT EXISTS idx_jobs_region     ON jobs (region);
CREATE INDEX IF NOT EXISTS idx_jobs_posted     ON jobs (posted_at DESC NULLS LAST);

-- ============================================================
-- 3. company_health — circuit breaker state
-- ============================================================
CREATE TABLE IF NOT EXISTS company_health (
    company_key          TEXT PRIMARY KEY REFERENCES companies(key) ON DELETE CASCADE,
    consecutive_failures INT NOT NULL DEFAULT 0,
    last_attempt_at      TIMESTAMPTZ,
    last_error           TEXT
);

-- ============================================================
-- 4. scrape_runs — per-run metrics time series
-- ============================================================
CREATE TABLE IF NOT EXISTS scrape_runs (
    id                  SERIAL PRIMARY KEY,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_seconds    REAL,
    companies_total     INT,
    quarantined         INT,
    fetched_ok          INT,
    fetch_errors        INT,
    fetch_success_rate  REAL,
    roles_matched       INT,
    new_this_run        INT,
    open_total          INT,
    roles_by_source     JSONB,
    roles_by_cycle      JSONB,
    roles_by_region     JSONB,
    detection_latency   JSONB,
    posting_lifetime    JSONB
);
CREATE INDEX IF NOT EXISTS idx_runs_time ON scrape_runs (generated_at DESC);

-- ============================================================
-- 5. drop_observations — radar ground truth (observed.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS drop_observations (
    company_key   TEXT NOT NULL,               -- normalized company name
    display_name  TEXT,                        -- clean display name
    season        TEXT NOT NULL,
    first_posted  DATE NOT NULL,
    count         INT NOT NULL DEFAULT 1,
    PRIMARY KEY (company_key, season)
);

-- ============================================================
-- 6. known_windows — hand-curated posting calendars
-- ============================================================
CREATE TABLE IF NOT EXISTS known_windows (
    company_name TEXT PRIMARY KEY,
    opens_month  VARCHAR(2),                   -- "08" = August; NULL = rolling
    precision    TEXT NOT NULL DEFAULT 'month', -- "month" | "rolling"
    note         TEXT,
    source       TEXT,
    verified_at  DATE
);

-- ============================================================
-- 7. app_state — singleton state (mail digest, WhatsApp, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_state (
    key        TEXT PRIMARY KEY,               -- "mail_digest", "whatsapp_reminder"
    value      JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Views
-- ============================================================

-- Analytics: how long do companies keep postings open?
CREATE OR REPLACE VIEW company_posting_stats AS
SELECT
    company_key,
    company,
    COUNT(*)                                                      AS total_jobs,
    COUNT(*) FILTER (WHERE is_open)                               AS open_jobs,
    ROUND(AVG(EXTRACT(EPOCH FROM (closed_at - first_seen_at)) / 86400)
        FILTER (WHERE closed_at IS NOT NULL), 1)                  AS avg_days_open,
    MAX(first_seen_at)                                            AS last_posting
FROM jobs
GROUP BY company_key, company;

-- Dashboard: all open roles with every field
CREATE OR REPLACE VIEW open_internships AS
SELECT
    j.id, j.company, j.title, j.location, j.url,
    j.season, j.season_inferred, j.category, j.region,
    j.stipend, j.salary, j.degree, j.experience, j.batch,
    j.skills, j.posted_at, j.first_seen_at, j.enriched_at
FROM jobs j
WHERE j.is_open
ORDER BY j.first_seen_at DESC;
