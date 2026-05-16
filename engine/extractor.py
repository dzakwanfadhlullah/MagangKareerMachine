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
    r"(?:perusahaan|company)[:\s]+([A-Za-z\s&.]+?)(?:\s*[-\u2013|,.\n])",
]

# Word-boundary patterns for internship detection
_INTERN_PATTERNS = [
    re.compile(r"\bintern\b", re.IGNORECASE),
    re.compile(r"\binternship\b", re.IGNORECASE),
    re.compile(r"\bmagang\b", re.IGNORECASE),
    re.compile(r"\bapprentice\b", re.IGNORECASE),
    re.compile(r"\bco-op\b", re.IGNORECASE),
]

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


def load_keywords(config_path: Optional[Path] = None) -> dict:
    """Load keyword config (nested structure)."""
    path = config_path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# === INTERNSHIP DETECTION ===

def check_internship_title(title: str) -> bool:
    """Word-boundary check for internship in title."""
    return any(p.search(title) for p in _INTERN_PATTERNS)


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

    # Tier 1: Strong term in TITLE (word-boundary)
    if check_internship_title(title):
        return True, 90, "title_strong"

    # Tier 2: Strong term in description (word-boundary)
    strong_count = 0
    for term in strong_terms:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if pattern.search(text_lower):
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

    # Check hybrid first (contains terms from both remote and onsite)
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


def detect_company(text: str, title: str) -> Optional[str]:
    combined = f"{title}\n{text[:2000]}"
    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, combined)
        if match:
            company = match.group(1).strip()
            if 2 < len(company) < 100:
                return company
    return None


def generate_summary(text: str, max_length: int = 300) -> str:
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 30]
    summary = " ".join(lines[:5])
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
    return summary


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
    location, location_area = detect_location(text, config)
    work_mode = detect_work_mode(text, config)

    # Strict fields
    deadline = detect_deadline(text)
    salary = detect_salary(text)
    duration = detect_duration(text)
    company = detect_company(text, title)
    summary = generate_summary(text)
    source_name = get_source_name(page.url)
    platform = page.source_platform or detect_platform(page.url)

    opp_title = (title if title else "Untitled")[:200]

    # Overall confidence
    confidence = intern_conf
    if role_conf >= 60:
        confidence = min(100, confidence + 10)

    return Opportunity(
        title=opp_title,
        company=company,
        role=role,
        category=category,
        location=location,
        location_area=location_area,
        work_mode=work_mode,
        duration=duration,
        salary=salary,
        deadline=deadline,
        source_url=page.url,
        detail_url=page.url,
        source_name=source_name,
        source_platform=platform,
        raw_text=text[:5000],
        summary=summary,
        score=0,
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
) -> tuple[list[Opportunity], list[RejectedCandidate]]:
    """Extract opportunities and return rejected candidates for audit."""
    opportunities = []
    rejections = []
    skipped = 0

    for page in pages:
        if page.page_type == "listing":
            rejections.append(build_rejected_candidate(page, "listing_page"))
            skipped += 1
            continue
        opp, rejection = extract_opportunity_with_rejection(page, config_path)
        if opp:
            opportunities.append(opp)
        else:
            if rejection:
                rejections.append(rejection)
            skipped += 1

    if skipped > 0:
        console.print(f"  [dim]Skipped {skipped} non-internship/irrelevant pages[/dim]")
    console.print(f"[green][OK][/green] Extracted {len(opportunities)} opportunities from {len(pages)} pages")
    return opportunities, rejections
