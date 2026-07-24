"""Skill tags + pay extraction from posting text (runs inside enrichment).

Same philosophy as sponsorship.py: precision over recall. The vocabulary is a
curated list of technologies students actually filter by — whole-word matches
only, so "Go" needs the word Go (not "goal") and bare "C"/"R" are excluded as
too noisy. Pay is extracted only from explicit money-with-period phrases
("$45/hr", "$120,000 per year"), never inferred.
"""

from __future__ import annotations

import re

# Canonical display name -> match pattern. Order = display priority when a
# posting matches more than MAX_SKILLS. Languages first (the strongest filter
# signal), then ML, then infra/web.
_VOCAB: list[tuple[str, str]] = [
    ("Python", r"python"),
    ("Java", r"java(?!\s*script)"),
    ("C++", r"c\+\+"),
    ("C#", r"c#|c\-sharp"),
    ("Go", r"golang|go\s+programming"),
    ("Rust", r"rust"),
    ("TypeScript", r"typescript"),
    ("JavaScript", r"javascript|ecmascript"),
    ("SQL", r"sql"),
    ("Swift", r"swift(?:ui)?"),
    ("Kotlin", r"kotlin"),
    ("Scala", r"scala"),
    ("MATLAB", r"matlab"),
    ("PyTorch", r"pytorch|torch"),
    ("TensorFlow", r"tensorflow"),
    ("scikit-learn", r"scikit[\s-]?learn|sklearn"),
    ("Pandas", r"pandas"),
    ("LLMs", r"llms?|large\s+language\s+models?|gen(?:erative)?\s*ai"),
    ("Computer Vision", r"computer\s+vision|opencv"),
    ("CUDA", r"cuda"),
    ("React", r"react(?:\.?js)?(?:\s+native)?"),
    ("Node.js", r"node\.?js"),
    ("Angular", r"angular(?:js)?"),
    ("Vue", r"vue(?:\.?js)?"),
    ("Django", r"django"),
    ("Flask", r"flask"),
    ("Spring", r"spring\s+boot"),
    (".NET", r"dotnet|asp\.net|\.net\s*(?:core|framework|\d)"),
    ("GraphQL", r"graphql"),
    ("AWS", r"aws|amazon\s+web\s+services"),
    ("GCP", r"gcp|google\s+cloud"),
    ("Azure", r"azure"),
    ("Kubernetes", r"kubernetes|k8s"),
    ("Docker", r"docker"),
    ("Terraform", r"terraform"),
    ("Linux", r"linux|unix"),
    ("Git", r"\bgit\b|github|gitlab"),
    ("Spark", r"apache\s+spark|pyspark|spark\s*(?:sql|streaming)"),
    ("Kafka", r"kafka"),
    ("Hadoop", r"hadoop"),
    ("Airflow", r"airflow"),
    ("PostgreSQL", r"postgres(?:ql)?"),
    ("MongoDB", r"mongodb|mongo"),
    ("Redis", r"redis"),
    ("Tableau", r"tableau"),
    ("ROS", r"ros\s*2|robot\s+operating\s+system"),
    ("Unity", r"unity\s*(?:3d|engine)"),
    ("Unreal", r"unreal\s+engine"),
    ("Verilog", r"(?:system)?verilog|vhdl"),
]

_COMPILED = [
    (name, re.compile(r"(?<![\w+#])(?:" + pat + r")(?![\w+])", re.IGNORECASE))
    for name, pat in _VOCAB
]

MAX_SKILLS = 8

_WS_RE = re.compile(r"\s+")


def extract(text: str | None) -> list[str]:
    """Skill tags found in the text, canonical order, capped at MAX_SKILLS."""
    if not text:
        return []
    found = [name for name, pattern in _COMPILED if pattern.search(text)]
    return found[:MAX_SKILLS]


# --- pay ----------------------------------------------------------------------
# "$45/hr", "$41.50 - $55 per hour"
_HOURLY_RE = re.compile(
    r"\$\s*(\d{2,3}(?:\.\d{1,2})?)"
    r"(?:\s*(?:-|–|—|to)\s*\$?\s*(\d{2,3}(?:\.\d{1,2})?))?"
    r"\s*(?:/\s*|\bper\s+)(?:hour|hr)\b",
    re.IGNORECASE,
)
# "$120,000 - $140,000 per year / annually / /yr"
_ANNUAL_RE = re.compile(
    r"\$\s*(\d{1,3}(?:,\d{3})+|\d{5,6})"
    r"(?:\s*(?:-|–|—|to)\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d{5,6}))?"
    r"[^$\n]{0,30}?(?:/\s*(?:year|yr)|per\s+(?:year|annum)|annual(?:ly|ized)?|a\s+year)",
    re.IGNORECASE,
)


def _hourly_ok(v: float) -> bool:
    return 12 <= v <= 200


def _annual_ok(v: float) -> bool:
    return 20_000 <= v <= 500_000


def _fmt_hourly(v: float) -> str:
    return f"${v:g}"


def _fmt_annual(v: float) -> str:
    return f"${v / 1000:g}k"


def extract_pay(text: str | None) -> str | None:
    """A compact pay string from explicit wage phrases, or None.

    Hourly beats annual (intern pay is usually quoted hourly; an annual figure
    in the same posting is often the conversion or a full-time band).
    """
    if not text:
        return None
    flat = _WS_RE.sub(" ", text)

    m = _HOURLY_RE.search(flat)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else None
        if _hourly_ok(lo) and (hi is None or (_hourly_ok(hi) and hi >= lo)):
            if hi and hi != lo:
                return f"{_fmt_hourly(lo)}–{_fmt_hourly(hi)}/hr"
            return f"{_fmt_hourly(lo)}/hr"

    m = _ANNUAL_RE.search(flat)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", "")) if m.group(2) else None
        if _annual_ok(lo) and (hi is None or (_annual_ok(hi) and hi >= lo)):
            if hi and hi != lo:
                return f"{_fmt_annual(lo)}–{_fmt_annual(hi)}/yr"
            return f"{_fmt_annual(lo)}/yr"
    return None

# --- degree, experience, batch, stipend (Indian contexts) ---
_STIPEND_INR_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{3})+|\d{4,5})(?:\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{4,5}))?\s*(?:/|per|a\s+)?(month|mo)",
    re.IGNORECASE,
)
_STIPEND_K_RE = re.compile(
    r"(\d{1,2})k(?:\s*(?:-|to)\s*(\d{1,2})k)?\s*(?:inr|/month|/mo|per month)",
    re.IGNORECASE,
)
_CTC_LPA_RE = re.compile(
    r"(?:ctc|pay)?\s*(\d{1,2}(?:\.\d{1,2})?)(?:\s*(?:-|to)\s*(\d{1,2}(?:\.\d{1,2})?))?\s*lpa",
    re.IGNORECASE,
)

_DEGREE_RE = re.compile(r"\b(B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?S\.?|M\.?S\.?|Ph\.?D|Bachelor's|Master's)\b", re.IGNORECASE)
_EXP_RE = re.compile(r"(fresher|0-1\s*years?|1-2\s*years?|2\+?\s*years?)", re.IGNORECASE)
_BATCH_RE = re.compile(r"(?:batch|class)\s*(?:of)?\s*(202[4-9])", re.IGNORECASE)

def extract_stipend(text: str | None) -> str | None:
    if not text: return None
    flat = _WS_RE.sub(" ", text)
    m = _STIPEND_INR_RE.search(flat)
    if m:
        lo = m.group(1).replace(",", "")
        hi = m.group(2).replace(",", "") if m.group(2) else None
        if hi and hi != lo: return f"₹{int(lo)//1000}k–{int(hi)//1000}k/mo"
        return f"₹{int(lo)//1000}k/mo"
    m = _STIPEND_K_RE.search(flat)
    if m:
        lo = m.group(1)
        hi = m.group(2) if m.group(2) else None
        if hi and hi != lo: return f"₹{lo}k–{hi}k/mo"
        return f"₹{lo}k/mo"
    m = _CTC_LPA_RE.search(flat)
    if m:
        lo = m.group(1)
        hi = m.group(2) if m.group(2) else None
        if hi and hi != lo: return f"{lo}–{hi} LPA"
        return f"{lo} LPA"
    return None

def extract_degree(text: str | None) -> str | None:
    if not text: return None
    m = _DEGREE_RE.search(text)
    if m:
        d = m.group(1).lower().replace(".", "").replace("'", "")
        if d in ("btech", "be", "bachelors", "bs"): return "B.Tech/BS"
        if d in ("mtech", "me", "masters", "ms"): return "M.Tech/MS"
        if d == "phd": return "PhD"
        return m.group(1)
    return None

def extract_experience(text: str | None) -> str | None:
    if not text: return None
    m = _EXP_RE.search(text)
    if m:
        e = m.group(1).lower()
        if "fresher" in e or "0-1" in e: return "0-1 Yr"
        if "1-2" in e: return "1-2 Yrs"
        if "2+" in e or "2 years" in e: return "2+ Yrs"
        return m.group(1)
    return None

def extract_batch(text: str | None) -> str | None:
    if not text: return None
    m = _BATCH_RE.search(text)
    if m:
        return m.group(1)
    return None

