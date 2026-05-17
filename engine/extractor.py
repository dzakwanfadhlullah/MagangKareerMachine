"""Extractor — ekstrak metadata lowongan dari teks halaman (rule-based).

Prinsip:
- Role hanya dari strong_titles di primary_text (title+heading)
- supporting_skills hanya menambah confidence, tidak menentukan role
- exclude_titles override role match
- Word-boundary untuk internship detection
- Better null daripada salah
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from rich.console import Console

from engine.models import RawPage, Opportunity, RejectedCandidate
from engine.url_utils import canonicalize_url

console = Console()

CONFIG_PATH = Path("config/keywords.yml")

# --- Regex Patterns ---

STRICT_DATE_PATTERNS = [
    r"\b(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|"
    r"January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b",
]

STRICT_SALARY_PATTERNS = [
    r"Rp\.?\s?(\d{1,3}(?:[.,]\d{3}){1,3})",
    r"IDR\s?(\d{1,3}(?:[.,]\d{3}){1,3})",
    r"(\d+)\s*[-\u2013]\s*(\d+)\s*juta",
    r"(\d+)\s*juta",
    r"(?:uang saku|allowance|stipend)\s*[:]\s*(Rp\.?\s?\d[\d.,]+|\d+\s*juta)",
    r"\b(paid internship|unpaid internship|unpaid)\b",
]

STRICT_DURATION_PATTERNS = [
    r"\b(\d{1,2})\s*(?:bulan|months?)\b",
    r"\b(\d{1,2})\s*(?:minggu|weeks?)\b",
]

COMPANY_PATTERNS = [
    r"(?:at|di|@)\s+([A-Z][A-Za-z\s&.]+?)(?:\s*[-\u2013|,]|\s*$)",
    r"[-\u2013\u2014]\s*(?:PT\.?\s+)?([A-Z][A-Za-z\s&.]+?)(?:\s*[-\u2013|,]|\s*$)",
    r"(?:PT\.?\s+)([A-Z][A-Za-z\s&.]+)",
    r"(?:perusahaan|company)[:\s]+([A-Za-z\s&.]+?)(?:\s*[-\u2013|,.\n]|$)",
]

COMPANY_DESCRIPTION_TERMS = [
    "membantu", "mengembangkan", "maintenance", "melakukan", "bertanggung jawab",
    "assist", "develop", "maintain", "building", "build", "collaborate",
    "membuat", "merancang", "mengimplementasikan",
]

# Word-boundary patterns for internship detection
_INTERN_PATTERNS = [
    re.compile(r"\bintern\b", re.IGNORECASE),
    re.compile(r"\binternship\b", re.IGNORECASE),
    re.compile(r"\bmagang\b", re.IGNORECASE),
    re.compile(r"\bapprentice\b", re.IGNORECASE),
    re.compile(r"\bco-op\b", re.IGNORECASE),
]

_TARGET_TITLE_INTERNSHIP_PATTERNS = _INTERN_PATTERNS + [
    re.compile(r"\btrainee\b", re.IGNORECASE),
    re.compile(r"\bojt\b", re.IGNORECASE),
    re.compile(r"\bpkl\b", re.IGNORECASE),
    re.compile(r"\bpraktik\s+kerja\b", re.IGNORECASE),
]

_PRIOR_INTERNSHIP_CONTEXT = re.compile(
    r"\b(?:prior|previous|past|relevant|required|preferred)\s+internship(?:s)?\b"
    r"|\binternship(?:s)?\s+(?:experience|required|preferred)\b",
    re.IGNORECASE,
)

# For early filter in pipeline (substring OK for speed)
TITLE_INTERNSHIP_SIGNALS = [
    "intern", "internship", "magang", "trainee", "apprentice",
    "program magang", "kerja praktek", "praktik kerja", "co-op",
]

ROLE_DISPLAY = {
    "software_engineering": "Software Engineering",
    "frontend": "Frontend Developer",
    "backend": "Backend Developer",
    "fullstack": "Fullstack Developer",
    "mobile": "Mobile Developer",
    "qa": "Quality Assurance",
    "it_support": "IT Support",
    "data_analyst": "Data Analyst",
    "business_intelligence": "Business Intelligence",
    "data_engineer": "Data Engineer",
    "ai_ml": "AI/ML Engineer",
    "actuarial": "Actuarial",
    "ui_ux": "UI/UX Designer",
    "product": "Product Manager",
}

ROLE_CATEGORY = {
    "Software Engineering": "tech",
    "Frontend Developer": "tech",
    "Backend Developer": "tech",
    "Fullstack Developer": "tech",
    "Mobile Developer": "tech",
    "Quality Assurance": "tech",
    "IT Support": "tech",
    "Data Analyst": "data",
    "Business Intelligence": "data",
    "Data Engineer": "data",
    "AI/ML Engineer": "data",
    "Actuarial": "actuarial",
    "UI/UX Designer": "design",
    "Product Manager": "product",
}

ROLE_KEY_BY_DISPLAY = {
    display.lower().replace("/", "_").replace(" ", "_"): key
    for key, display in ROLE_DISPLAY.items()
}

TARGET_CATEGORY_ALIASES = {
    "technology": "tech",
    "engineering": "tech",
    "software": "software_engineering",
    "software_engineer": "software_engineering",
    "software_engineering": "software_engineering",
    "frontend_developer": "frontend",
    "front_end": "frontend",
    "backend_developer": "backend",
    "back_end": "backend",
    "fullstack_developer": "fullstack",
    "full_stack": "fullstack",
    "mobile_developer": "mobile",
    "quality_assurance": "qa",
    "it": "it_support",
    "support": "it_support",
    "business_intelligence": "business_intelligence",
    "bi": "business_intelligence",
    "machine_learning": "ai_ml",
    "ml": "ai_ml",
    "ai": "ai_ml",
    "uiux": "ui_ux",
    "ui_ux_designer": "ui_ux",
    "product_manager": "product",
    "actuary": "actuarial",
    "aktuaria": "actuarial",
}

TOP_LEVEL_CATEGORIES = {"tech", "data", "actuarial", "design", "product"}

SENIORITY_NON_INTERN_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bsenior\b",
        r"\bmanager\b",
        r"\blead\b",
        r"\bhead\b",
        r"\bhead\s+of\b",
        r"\bsupervisor\b",
        r"\bprincipal\b",
        r"\bdirector\b",
        r"\bvp\b",
        r"\bvice\s+president\b",
        r"\bchief\b",
    ]
]


def load_keywords(config_path: Optional[Path] = None) -> dict:
    """Load keyword config (nested structure)."""
    path = config_path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# === INTERNSHIP DETECTION ===

def check_internship_title(title: str) -> bool:
    """Word-boundary check for internship in title."""
    return any(p.search(title) for p in _INTERN_PATTERNS)


def check_targeted_internship_title(title: str) -> bool:
    """Title-level internship check for targeted user-facing searches."""
    return any(p.search(title) for p in _TARGET_TITLE_INTERNSHIP_PATTERNS)


def _is_prior_internship_requirement(text: str, match_start: int, match_end: int) -> bool:
    window = text[max(0, match_start - 60):match_end + 60]
    return bool(_PRIOR_INTERNSHIP_CONTEXT.search(window))


def title_has_seniority_without_internship(title: str) -> bool:
    """Reject senior/managerial titles unless the title itself says intern/magang."""
    if not title or check_internship_title(title):
        return False
    return any(pattern.search(title) for pattern in SENIORITY_NON_INTERN_PATTERNS)


def detect_internship(text: str, title: str, config: dict) -> tuple[bool, int, str]:
    """
    3-tier internship detection with strong/weak terms.
    Return (is_internship, confidence, source).
    """
    title_lower = title.lower()
    text_lower = text[:3000].lower()

    strong_terms = config.get("internship_terms", {}).get("strong", [])
    weak_terms = config.get("internship_terms", {}).get("weak", [])
    non_intern = config.get("non_internship_terms", [])
    neg_hard = config.get("negative_terms", {}).get("hard_reject", [])
    neg_likely = config.get("negative_terms", {}).get("likely_not_job", [])

    # Hard reject
    for term in neg_hard:
        if term.lower() in text_lower:
            return False, 0, "hard_reject"

    # Likely not job (check title/heading)
    for term in neg_likely:
        if term.lower() in title_lower:
            return False, 0, "likely_not_job"

    if title_has_seniority_without_internship(title):
        return False, 0, "seniority_without_internship_title"

    # Tier 1: Strong term in TITLE (word-boundary)
    if check_internship_title(title):
        return True, 90, "title_strong"

    # Tier 2: Strong term in description (word-boundary)
    strong_count = 0
    for term in strong_terms:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        match = pattern.search(text_lower)
        if match and not _is_prior_internship_requirement(text_lower, match.start(), match.end()):
            strong_count += 1

    # Extra strong signals
    extra_strong = ["program magang", "mahasiswa magang", "internship program"]
    for signal in extra_strong:
        if signal in text_lower:
            strong_count += 1

    if strong_count >= 2:
        return True, min(strong_count * 15 + 30, 85), "description_strong"

    # Tier 3: Weak terms
    weak_count = 0
    for term in weak_terms:
        if term.lower() in text_lower:
            weak_count += 1

    # Non-internship terms reduce confidence
    non_intern_count = 0
    for term in non_intern:
        if term.lower() in title_lower:
            non_intern_count += 1

    if strong_count >= 1 and non_intern_count == 0:
        return True, 60, "description_single_strong"

    if weak_count >= 1 and strong_count >= 1:
        return True, 55, "description_weak_plus_strong"

    if non_intern_count > 0 and strong_count == 0:
        return False, 0, "non_internship_title"

    return False, 0, "no_signal"


# === ROLE DETECTION ===

def detect_role(title: str, description_head: str, config: dict) -> tuple[Optional[str], int]:
    """
    Role detection: strong_titles in primary_text -> supporting_skills for confidence.
    exclude_titles override.
    Return (role_display_name, confidence).
    """
    role_keywords = config.get("role_keywords", {})
    primary = title.lower()
    secondary = description_head[:1500].lower()

    best_role = None
    best_conf = 0

    for role_key, role_cfg in role_keywords.items():
        if not isinstance(role_cfg, dict):
            continue

        strong_titles = role_cfg.get("strong_titles", [])
        supporting = role_cfg.get("supporting_skills", [])
        excludes = role_cfg.get("exclude_titles", [])

        # Check exclude_titles first (in primary text)
        excluded = any(ex.lower() in primary for ex in excludes)
        if excluded:
            continue

        # Check strong_titles in primary text (title)
        strong_match = any(st.lower() in primary for st in strong_titles)
        if not strong_match:
            continue

        # Base confidence from strong title match
        conf = 70

        # Bonus from supporting skills in secondary text
        skill_count = sum(1 for sk in supporting if sk.lower() in secondary)
        conf += min(skill_count * 10, 30)

        # Internship bonus
        if check_internship_title(title):
            conf += 20

        if conf > best_conf:
            best_conf = conf
            best_role = role_key

    if best_role and best_conf >= 60:
        display = ROLE_DISPLAY.get(best_role, best_role.replace("_", " ").title())
        return display, best_conf

    return None, 0


def detect_category(role: Optional[str]) -> Optional[str]:
    """Map role to category. None if no role."""
    if not role:
        return None
    return ROLE_CATEGORY.get(role, None)


def normalize_target_category(target_category: Optional[str]) -> Optional[str]:
    """Normalize category/role target input from CLI into canonical label."""
    if not target_category:
        return None
    target = target_category.strip().lower().replace("-", "_").replace(" ", "_")
    if not target:
        return None
    if target in TARGET_CATEGORY_ALIASES:
        return TARGET_CATEGORY_ALIASES[target]
    if target in TOP_LEVEL_CATEGORIES or target in ROLE_DISPLAY:
        return target
    return ROLE_KEY_BY_DISPLAY.get(target, target)


def _role_to_key(role: Optional[str]) -> Optional[str]:
    if not role:
        return None
    normalized = role.strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")
    return ROLE_KEY_BY_DISPLAY.get(normalized, normalized)


def opportunity_matches_target(opp: Opportunity, target_category: Optional[str]) -> bool:
    """
    Check whether an opportunity matches a targeted crawl/search intent.

    Target may be a top-level category (tech/data/actuarial/design/product)
    or a role key (frontend/backend/data_analyst/mobile/etc).
    """
    target = normalize_target_category(target_category)
    if not target:
        return True
    if target in TOP_LEVEL_CATEGORIES:
        return opp.category == target
    return _role_to_key(opp.role) == target


# === LOCATION ===

def detect_location(text: str, config: dict) -> tuple[Optional[str], Optional[str]]:
    """
    Detect location from grouped locations.
    Return (city_name, area_name).
    """
    text_lower = text[:3000].lower()
    locations = config.get("locations", {})

    for area_name, cities in locations.items():
        if not isinstance(cities, list):
            continue
        # Skip 'indonesia' as it's a fallback
        if area_name == "indonesia":
            continue
        for city in cities:
            if city.lower() in text_lower:
                return city.title(), area_name

    # Fallback: indonesia
    indonesia_terms = locations.get("indonesia", [])
    for term in indonesia_terms:
        if term.lower() in text_lower:
            return "Indonesia", "indonesia"

    return None, None


# === WORK MODE ===

def detect_work_mode(text: str, config: dict) -> Optional[str]:
    """Detect work mode from config work_modes."""
    text_lower = text[:3000].lower()
    work_modes = config.get("work_modes", {})

    # Explicit remote/onsite signals should beat broad hybrid text.
    explicit_remote = [
        r"\bwfh\b",
        r"\bwork\s+from\s+home\b",
        r"\bfull\s+remote\b",
        r"\bfully\s+remote\b",
    ]
    explicit_onsite = [
        r"\bwfo\b",
        r"\bwork\s+from\s+office\b",
        r"\bonsite\b",
        r"\bon-site\b",
    ]
    if any(re.search(pattern, text_lower) for pattern in explicit_onsite):
        return "onsite"
    if any(re.search(pattern, text_lower) for pattern in explicit_remote):
        return "remote"
    if "hybrid" in text_lower:
        return "hybrid"

    for mode in ["hybrid", "remote", "onsite"]:
        signals = work_modes.get(mode, [])
        for signal in signals:
            if signal.lower() in text_lower:
                return mode

    return None


# === NEGATIVE TERM CHECK ===

def check_suspicious_role(title: str, config: dict) -> Optional[str]:
    """Check if title matches suspicious_roles. Return matched term or None."""
    title_lower = title.lower()
    suspicious = config.get("negative_terms", {}).get("suspicious_roles", [])

    for role in suspicious:
        if role.lower() in title_lower:
            return role
    return None


# === FIELD EXTRACTORS (strict) ===

def detect_deadline(text: str) -> Optional[str]:
    deadline_context = ""
    for kw in ["deadline", "batas akhir", "penutupan", "ditutup", "apply before", "closed"]:
        idx = text.lower().find(kw)
        if idx >= 0:
            deadline_context += text[max(0, idx):idx + 100] + " "

    search_text = deadline_context if deadline_context else text[:3000]
    for pattern in STRICT_DATE_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def detect_salary(text: str) -> Optional[str]:
    if salary_hidden(text):
        return None
    for pattern in STRICT_SALARY_PATTERNS:
        match = re.search(pattern, text[:5000], re.IGNORECASE)
        if match:
            result = match.group(0).strip()
            if len(result) < 4 or len(result) > 50:
                continue
            if re.match(r"^(Rp\.?|IDR)\s*$", result):
                continue
            return result
    return None


def normalize_salary(raw_salary: Optional[str], confidence: int = 0) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """Return dashboard display plus numeric min/max when extractable."""
    if not raw_salary or confidence == 0:
        return None, None, None

    raw = re.sub(r"\s+", "", raw_salary.strip())
    raw = re.sub(r"^Rp\.?", "Rp", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^IDR", "Rp", raw, flags=re.IGNORECASE)

    if re.search(r"\b(paidinternship|unpaidinternship|unpaid)\b", raw, re.IGNORECASE):
        label = raw_salary.strip()
        return re.sub(r"\s+", " ", label), None, None

    juta_range = re.search(r"(\d+)\s*[-\u2013]\s*(\d+)\s*juta", raw_salary, re.IGNORECASE)
    if juta_range:
        low = int(juta_range.group(1)) * 1_000_000
        high = int(juta_range.group(2)) * 1_000_000
        return f"Rp{low:,} - Rp{high:,}".replace(",", "."), low, high

    juta = re.search(r"(\d+)\s*juta", raw_salary, re.IGNORECASE)
    if juta:
        value = int(juta.group(1)) * 1_000_000
        return f"Rp{value:,}".replace(",", "."), value, value

    digits = re.sub(r"\D", "", raw_salary)
    if digits:
        value = int(digits)
        return f"Rp{value:,}".replace(",", "."), value, value

    return raw_salary.strip(), None, None


def salary_hidden(text: str) -> bool:
    """Detect explicit platform text saying salary is not displayed."""
    lowered = text[:3000].lower()
    hidden_signals = [
        "perusahaan tidak menampilkan gaji",
        "gaji tidak ditampilkan",
        "salary not displayed",
        "salary undisclosed",
        "undisclosed salary",
    ]
    return any(signal in lowered for signal in hidden_signals)


def salary_confidence(text: str, salary: Optional[str]) -> int:
    """Coarse confidence for salary extraction."""
    if not salary:
        return 0
    lowered = text[:5000].lower()
    if salary_hidden(text):
        return 0
    if any(signal in lowered for signal in ["uang saku", "allowance", "stipend", "salary", "gaji"]):
        return 80
    if re.search(r"\b(?:paid internship|unpaid internship|unpaid)\b", salary, re.IGNORECASE):
        return 70
    return 50


def detect_duration(text: str) -> Optional[str]:
    for pattern in STRICT_DURATION_PATTERNS:
        match = re.search(pattern, text[:5000], re.IGNORECASE)
        if match:
            num = int(match.group(1))
            word = match.group(0).lower()
            if "bulan" in word or "month" in word:
                if 1 <= num <= 24:
                    return match.group(0).strip()
            elif "minggu" in word or "week" in word:
                if 1 <= num <= 52:
                    return match.group(0).strip()
    return None


def extract_company_from_title(title: str) -> Optional[str]:
    """Extract company from common platform title patterns."""
    patterns = [
        r"^(.+?)\s+membuka\s+lowongan\b",
        r"\bdi\s+(.+?)(?:,\s*\||\s*\|\s*Glints|$)",
        r"\bat\s+(.+?)(?:,\s*\||\s*\|\s*Glints|$)",
        r"\bjobs?\s+at\s+(.+?)(?:,\s*\||\s*\|\s*Glints|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title or "", re.IGNORECASE)
        if not match:
            continue
        company = match.group(1).strip(" ,-|\n\t")
        if is_valid_company(company):
            return company
    return None


def is_valid_company(company: Optional[str]) -> bool:
    """Reject company values that look like job-description sentences."""
    if not company:
        return False
    value = re.sub(r"\s+", " ", company).strip()
    lowered = value.lower()
    if len(value) < 2 or len(value) > 80:
        return False
    if lowered in {"indonesia", "linkedin", "glints", "jobstreet"}:
        return False
    if len(value.split()) > 10:
        return False
    if "|" in value:
        return False
    if any(term in lowered for term in COMPANY_DESCRIPTION_TERMS):
        return False
    if re.search(r"[!?;:]{1}", value):
        return False
    return True


def company_confidence(company: Optional[str], title: str = "") -> int:
    """Coarse confidence score for company extraction."""
    if not is_valid_company(company):
        return 0
    if company and company.lower() in (title or "").lower():
        return 90
    return 70


def detect_company(text: str, title: str) -> Optional[str]:
    title_company = extract_company_from_title(title)
    if title_company:
        return title_company

    combined = f"{title}\n{text[:2000]}"
    for line in combined.splitlines():
        if re.match(r"^\s*(?:company|perusahaan)\s*:", line, re.IGNORECASE):
            company = re.split(r":", line, maxsplit=1)[1].strip()
            if is_valid_company(company):
                return company
    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            if is_valid_company(company):
                return company
    return None


def generate_summary(text: str, max_length: int = 300) -> str:
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 30]
    summary = " ".join(lines[:5])
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
    return summary


def generate_summary_short(summary: Optional[str], max_length: int = 180) -> Optional[str]:
    """Compact dashboard summary that never exposes raw debug text wholesale."""
    if not summary:
        return None
    compact = re.sub(r"\s+", " ", summary).strip()
    if len(compact) > max_length:
        compact = compact[:max_length].rsplit(" ", 1)[0] + "..."
    return compact


def detect_extraction_depth(page: RawPage) -> str:
    """Classify how much evidence backed this opportunity."""
    if page.fetch_method == "jobstreet-card-fallback":
        return "listing_card"
    if page.source_platform == "linkedin":
        return "search_snippet"
    return "full_detail"


def detect_verification_level(extraction_depth: str) -> str:
    if extraction_depth == "full_detail":
        return "verified_detail"
    if extraction_depth == "listing_card":
        return "listed_only"
    if extraction_depth == "search_snippet":
        return "search_index_only"
    return "unknown"


def detect_active_status(extraction_depth: str, text: str) -> str:
    lowered = text.lower()
    if re.search(r"\bclosed\b|\bexpired\b|\bditutup\b|\bkadaluarsa\b", lowered):
        return "closed"
    if extraction_depth == "listing_card":
        return "listed"
    if extraction_depth == "search_snippet":
        return "unknown"
    if any(signal in lowered for signal in ["apply", "lamar", "daftar", "listed", "posted"]):
        return "active"
    return "unknown"


def field_status(value: Optional[str], text: str, extraction_depth: str, field: str) -> str:
    """Explain why optional fields are null without treating valid missing data as false positive."""
    if value:
        return "provided"
    if extraction_depth in {"listing_card", "search_snippet"}:
        return "unknown_due_to_partial_extraction"
    lowered = text[:5000].lower()
    if field == "salary" and salary_hidden(text):
        return "not_provided"
    if field == "deadline" and any(signal in lowered for signal in ["closed", "ditutup", "expired"]):
        return "invalid"
    return "not_provided"


def detect_role_taxonomy(role: Optional[str], title: str, text: str, category: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return dashboard-friendly role family/group/specialization."""
    if not role and not category:
        return None, None, None

    family = category or "general"
    role_text = f"{title}\n{role or ''}\n{text[:1200]}".lower()
    specialization = "general"

    specialization_patterns = [
        ("game", [r"\bunity\b", r"\bgame\b", r"\bunreal\b"]),
        ("mobile", [r"\bmobile\b", r"\bflutter\b", r"\bandroid\b", r"\bios\b", r"\bkotlin\b", r"\bswift\b"]),
        ("frontend", [r"\bfront[-\s]?end\b", r"\bfrontend\b", r"\breact\b", r"\bvue\b", r"\bnext\.?js\b"]),
        ("backend", [r"\bback[-\s]?end\b", r"\bbackend\b", r"\bapi\b", r"\bnode\.?js\b", r"\blaravel\b"]),
        ("fullstack", [r"\bfull[-\s]?stack\b", r"\bfullstack\b"]),
        ("web", [r"\bweb developer\b", r"\bweb\b"]),
        ("data", [r"\bdata analyst\b", r"\bbusiness intelligence\b", r"\bbi\b", r"\bdashboard\b"]),
        ("qa", [r"\bqa\b", r"\bquality assurance\b", r"\btester\b"]),
    ]
    for name, patterns in specialization_patterns:
        if any(re.search(pattern, role_text) for pattern in patterns):
            specialization = name
            break

    if category == "tech":
        group = "software_engineering" if specialization not in {"data", "qa"} else specialization
    elif category:
        group = category
    else:
        group = None
    return family, group, specialization


def detect_mixed_employment_signal(title: str, text: str) -> bool:
    haystack = f"{title}\n{text[:800]}".lower()
    if not any(term in haystack for term in ["intern", "internship", "magang"]):
        return False
    return any(re.search(pattern, haystack) for pattern in [
        r"\bintern\s*/\s*staff\b",
        r"\bstaff\s*/\s*intern\b",
        r"\bintern\s+or\s+staff\b",
        r"\binternship\s*/\s*full[-\s]?time\b",
    ])


def source_platform_label(platform: Optional[str]) -> Optional[str]:
    labels = {
        "glints": "Glints",
        "dealls": "Dealls",
        "kalibrr": "Kalibrr",
        "jobstreet": "Jobstreet",
        "linkedin": "LinkedIn",
        "prosple": "Prosple",
        "indeed": "Indeed",
        "lokerid": "Loker.id",
    }
    return labels.get(platform or "", (platform or "").title() if platform else None)


def dashboard_quality(
    extraction_depth: str,
    company_conf: int,
    role_conf: int,
    summary: Optional[str],
    source_url: str,
) -> str:
    """Quality tier for dashboard display, independent from validity gates."""
    has_core = bool(source_url and company_conf >= 60 and role_conf >= 60)
    summary_len = len(summary or "")
    if extraction_depth == "full_detail" and has_core and summary_len >= 80:
        return "high"
    if extraction_depth == "listing_card" and has_core:
        return "medium"
    if extraction_depth == "search_snippet" and has_core and summary_len >= 80:
        return "medium"
    return "low"


def get_source_name(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def build_rejected_candidate(
    page: RawPage,
    reason: str,
    title: Optional[str] = None,
    text: Optional[str] = None,
    internship_confidence: int = 0,
    role_confidence: int = 0,
    score: int = 0,
) -> RejectedCandidate:
    """Build a compact rejected candidate record for audit."""
    from engine.listing_parser import detect_platform

    return RejectedCandidate(
        url=page.url,
        title=title if title is not None else page.title,
        source_platform=page.source_platform or detect_platform(page.url),
        page_type=page.page_type,
        rejection_reason=reason,
        internship_confidence=internship_confidence,
        role_confidence=role_confidence,
        score=score,
        text_snippet=(text or page.text_content or "")[:1000],
    )


# === MAIN EXTRACTOR ===

def extract_opportunity_with_rejection(
    page: RawPage,
    config_path: Optional[Path] = None,
) -> tuple[Optional[Opportunity], Optional[RejectedCandidate]]:
    """
    Extract opportunity with quality gates:
    1. Reject listing pages
    2. Reject hard_reject / likely_not_job
    3. Internship gate (strong/weak)
    4. Suspicious role check
    5. Role detection (strong_titles + exclude_titles)
    6. Strict field extraction
    """
    from engine.listing_parser import classify_page, is_listing_title, detect_platform

    title = page.title or ""
    config = load_keywords(config_path)

    # Gate 1: listing page
    page_type = page.page_type if page.page_type != "unknown" else classify_page(page.url, title)
    if page_type == "listing":
        return None, build_rejected_candidate(page, "listing_page", title=title)
    if is_listing_title(title):
        return None, build_rejected_candidate(page, "listing_title", title=title)

    text = page.text_content
    field_text = f"{title}\n{text}"

    # Gate 2: Internship detection
    is_intern, intern_conf, intern_src = detect_internship(text, title, config)
    if not is_intern:
        return None, build_rejected_candidate(
            page,
            f"not_internship:{intern_src}",
            title=title,
            text=text,
            internship_confidence=intern_conf,
        )

    # Gate 3: Suspicious role check
    suspicious = check_suspicious_role(title, config)

    # Role detection
    role, role_conf = detect_role(title, text, config)

    # If suspicious role, prevent wrong category assignment
    if suspicious:
        role_conf = max(0, role_conf - 50)
        if role_conf < 60:
            role = None
        if role is None:
            return None, build_rejected_candidate(
                page,
                f"suspicious_role:{suspicious}",
                title=title,
                text=text,
                internship_confidence=intern_conf,
                role_confidence=role_conf,
            )

    category = detect_category(role) if role and role_conf >= 60 else None

    # Location (grouped)
    location, location_area = detect_location(field_text, config)
    work_mode = detect_work_mode(field_text, config)

    # Strict fields
    extraction_depth = detect_extraction_depth(page)
    verification_level = detect_verification_level(extraction_depth)
    active_status = detect_active_status(extraction_depth, field_text)
    deadline = detect_deadline(field_text)
    salary_raw = detect_salary(field_text)
    sal_conf = salary_confidence(field_text, salary_raw)
    salary_display, salary_min, salary_max = normalize_salary(salary_raw, sal_conf)
    duration = detect_duration(field_text)
    company = detect_company(text, title)
    comp_conf = company_confidence(company, title)
    summary = generate_summary(text)
    summary_short = generate_summary_short(summary)
    canonical_url = canonicalize_url(page.url)
    source_name = get_source_name(canonical_url)
    platform = page.source_platform or detect_platform(page.url)
    role_family, role_group, role_specialization = detect_role_taxonomy(role, title, text, category)
    mixed_signal = detect_mixed_employment_signal(title, text)
    location_conf = 80 if location else 0
    dash_quality = dashboard_quality(extraction_depth, comp_conf, role_conf, summary, canonical_url)

    opp_title = (title if title else "Untitled")[:200]

    # Overall confidence
    confidence = intern_conf
    if role_conf >= 60:
        confidence = min(100, confidence + 10)

    return Opportunity(
        title=opp_title,
        company=company,
        company_confidence=comp_conf,
        role=role,
        category=category,
        location=location,
        location_area=location_area,
        work_mode=work_mode,
        duration=duration,
        salary=salary_display,
        salary_raw=salary_raw,
        salary_display=salary_display,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_confidence=sal_conf,
        salary_status=field_status(salary_display, field_text, extraction_depth, "salary"),
        location_status=field_status(location, field_text, extraction_depth, "location"),
        duration_status=field_status(duration, field_text, extraction_depth, "duration"),
        deadline_status=field_status(deadline, field_text, extraction_depth, "deadline"),
        location_confidence=location_conf,
        deadline=deadline,
        source_url=canonical_url,
        detail_url=canonical_url,
        original_url=page.url if page.url != canonical_url else None,
        source_name=source_name,
        source_platform=platform,
        raw_text=text[:5000],
        summary=summary,
        summary_short=summary_short,
        source_platform_label=source_platform_label(platform),
        apply_url=canonical_url,
        display_location=location if location else ("Belum tersedia" if extraction_depth in {"listing_card", "search_snippet"} else "Tidak dicantumkan"),
        display_salary=salary_display if salary_display else ("Belum tersedia" if extraction_depth in {"listing_card", "search_snippet"} else "Tidak dicantumkan"),
        score=0,
        extraction_depth=extraction_depth,
        verification_level=verification_level,
        dashboard_quality=dash_quality,
        active_status=active_status,
        role_family=role_family,
        role_group=role_group,
        role_specialization=role_specialization,
        mixed_employment_signal=mixed_signal,
        confidence=confidence,
        is_internship=is_intern,
        internship_confidence=intern_conf,
        role_confidence=role_conf,
        page_type="detail",
        extraction_status="extracted",
    ), None


def extract_opportunity(page: RawPage, config_path: Optional[Path] = None) -> Optional[Opportunity]:
    """
    Extract one opportunity.

    Keeps the legacy API by returning None for rejected pages. Use
    extract_opportunity_with_rejection for audit details.
    """
    opportunity, _ = extract_opportunity_with_rejection(page, config_path)
    return opportunity


def extract_all(pages: list[RawPage], config_path: Optional[Path] = None) -> list[Opportunity]:
    """Extract opportunities. Skip listing + non-internship pages."""
    opportunities, _ = extract_all_with_rejections(pages, config_path)
    return opportunities


def extract_all_with_rejections(
    pages: list[RawPage],
    config_path: Optional[Path] = None,
    target_category: Optional[str] = None,
) -> tuple[list[Opportunity], list[RejectedCandidate]]:
    """Extract opportunities and return rejected candidates for audit."""
    opportunities = []
    rejections = []
    skipped = 0
    normalized_target = normalize_target_category(target_category)

    for page in pages:
        if page.page_type == "listing":
            rejections.append(build_rejected_candidate(page, "listing_page"))
            skipped += 1
            continue
        opp, rejection = extract_opportunity_with_rejection(page, config_path)
        if opp:
            if normalized_target and not check_targeted_internship_title(opp.title):
                rejections.append(build_rejected_candidate(
                    page,
                    "not_internship:target_title_missing_internship",
                    title=opp.title,
                    text=opp.raw_text,
                    internship_confidence=opp.internship_confidence,
                    role_confidence=opp.role_confidence,
                    score=opp.score,
                ))
                skipped += 1
                continue
            if normalized_target and not opportunity_matches_target(opp, normalized_target):
                rejections.append(build_rejected_candidate(
                    page,
                    f"out_of_scope_target:{normalized_target}",
                    title=opp.title,
                    text=opp.raw_text,
                    internship_confidence=opp.internship_confidence,
                    role_confidence=opp.role_confidence,
                    score=opp.score,
                ))
                skipped += 1
                continue
            opportunities.append(opp)
        else:
            if rejection:
                rejections.append(rejection)
            skipped += 1

    if skipped > 0:
        console.print(f"  [dim]Skipped {skipped} non-internship/irrelevant pages[/dim]")
    console.print(f"[green][OK][/green] Extracted {len(opportunities)} opportunities from {len(pages)} pages")
    return opportunities, rejections
