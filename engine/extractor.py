"""Extractor — ekstrak metadata lowongan dari teks halaman (rule-based).

Prinsip kualitas:
- Role hanya dideteksi dari title + deskripsi awal (maks 1500 char)
- Internship gate: harus ada sinyal magang di title ATAU deskripsi
- Salary/duration/deadline harus format valid, bukan noise
- Better null daripada salah
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from rich.console import Console

from engine.models import RawPage, Opportunity

console = Console()

CONFIG_PATH = Path("config/keywords.yml")


# --- Regex Patterns ---

# Pola tanggal Indonesia/English — harus tanggal eksplisit
STRICT_DATE_PATTERNS = [
    # 19 Mei 2026, 30 May 2026
    r"\b(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|"
    r"January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    # 2026-05-19
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
    # 19/05/2026 or 19-05-2026
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b",
]

# Pola work mode — urutan penting: hybrid dicek duluan
WORK_MODE_MAP = [
    ("hybrid", ["hybrid", "wfo/wfh", "wfh/wfo", "flexible"]),
    ("remote", ["fully remote", "remote", "work from home", "wfh", "kerja dari rumah"]),
    ("onsite", ["onsite", "on-site", "on site", "work from office", "wfo", "di kantor"]),
]

# Pola salary — harus format yang masuk akal
STRICT_SALARY_PATTERNS = [
    # Rp3.000.000 atau Rp 3,000,000 — angka harus 5-9 digit
    r"Rp\.?\s?(\d{1,3}(?:[.,]\d{3}){1,3})",
    # IDR 3,000,000
    r"IDR\s?(\d{1,3}(?:[.,]\d{3}){1,3})",
    # 3-5 juta
    r"(\d+)\s*[-–]\s*(\d+)\s*juta",
    # 3 juta
    r"(\d+)\s*juta",
    # Frasa eksplisit
    r"(?:uang saku|allowance|stipend)\s*[:]\s*(Rp\.?\s?\d[\d.,]+|\d+\s*juta)",
    # paid/unpaid
    r"\b(paid internship|unpaid internship|unpaid)\b",
]

# Pola durasi — harus angka + satuan yang jelas
STRICT_DURATION_PATTERNS = [
    r"\b(\d{1,2})\s*(?:bulan|months?)\b",
    r"\b(\d{1,2})\s*(?:minggu|weeks?)\b",
]

# Pola company
COMPANY_PATTERNS = [
    r"(?:at|di|@)\s+([A-Z][A-Za-z\s&.]+?)(?:\s*[-–|,]|\s*$)",
    r"[-–—]\s*(?:PT\.?\s+)?([A-Z][A-Za-z\s&.]+?)(?:\s*[-–|,]|\s*$)",
    r"(?:PT\.?\s+)([A-Z][A-Za-z\s&.]+)",
    r"(?:perusahaan|company)[:\s]+([A-Za-z\s&.]+?)(?:\s*[-–|,.\n])",
]

# Sinyal kuat internship di title
TITLE_INTERNSHIP_SIGNALS = [
    "intern", "internship", "magang", "trainee", "apprentice",
    "program magang", "kerja praktek", "praktik kerja", "co-op",
]


def load_keywords(config_path: Optional[Path] = None) -> dict:
    """Load keyword config."""
    path = config_path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- Internship Gate ---

def check_internship_title(title: str) -> bool:
    """Cek apakah TITLE mengandung sinyal magang."""
    title_lower = title.lower()
    return any(signal in title_lower for signal in TITLE_INTERNSHIP_SIGNALS)


def detect_internship(text: str, title: str, config: dict) -> tuple[bool, int, str]:
    """
    Deteksi apakah halaman berisi lowongan magang.
    3-tier check: title -> job_type signal -> deskripsi awal.
    Return (is_internship, confidence, source).
    """
    title_lower = title.lower()
    # Hanya pakai deskripsi awal untuk mengurangi noise
    text_lower = text[:3000].lower()

    internship_terms = config.get("internship_terms", [])
    negative_terms = config.get("negative_terms", [])

    # Tier 1: Title check — paling kuat
    if check_internship_title(title):
        return True, 90, "title"

    # Tier 2: Job type signal di deskripsi awal
    job_type_signals = [
        "job type: intern", "tipe pekerjaan: magang", "employment type: intern",
        "jenis pekerjaan: magang", "tipe: magang", "type: internship",
        "job type:internship", "work type: intern",
    ]
    for signal in job_type_signals:
        if signal in text_lower:
            return True, 85, "job_type"

    # Tier 3: Deskripsi — butuh sinyal kuat
    positive_count = 0
    for term in internship_terms:
        if term.lower() in text_lower:
            positive_count += 1

    # Extra positive signals
    extra_positive = ["program magang", "mahasiswa", "fresh graduate",
                      "semester akhir", "akhir kuliah", "kerja praktek"]
    for signal in extra_positive:
        if signal in text_lower:
            positive_count += 1

    # Hitung sinyal negatif
    negative_count = 0
    for term in negative_terms:
        if term.lower() in text_lower:
            negative_count += 1

    if negative_count > 0:
        return False, 0, "negative_signal"

    if positive_count >= 2:
        return True, min(positive_count * 15, 80), "description"

    # Satu sinyal saja tidak cukup — butuh konteks tambahan
    if positive_count == 1:
        return True, 40, "weak_description"

    return False, 0, "no_signal"


# --- Role Detection (title-first) ---

def detect_role(title: str, description_head: str, config: dict) -> tuple[Optional[str], int]:
    """
    Deteksi role dari title dulu, lalu deskripsi awal.
    Return (role, confidence).

    Confidence:
    - 90+: role ada di title
    - 60-80: role ada di deskripsi awal
    - 0: tidak terdeteksi
    """
    role_keywords = config.get("role_keywords", {})
    role_display = {
        "frontend": "Frontend Developer",
        "backend": "Backend Developer",
        "fullstack": "Fullstack Developer",
        "mobile": "Mobile Developer",
        "data_analyst": "Data Analyst",
        "data_engineer": "Data Engineer",
        "ai_ml": "AI/ML Engineer",
        "actuarial": "Actuarial",
    }

    # --- Cek title dulu (paling reliable) ---
    title_lower = title.lower()
    title_match = _match_role(title_lower, role_keywords)
    if title_match:
        return role_display.get(title_match, title_match.replace("_", " ").title()), 95

    # --- Cek deskripsi awal (maks 1500 char) ---
    desc_lower = description_head[:1500].lower()
    desc_match = _match_role(desc_lower, role_keywords)
    if desc_match:
        return role_display.get(desc_match, desc_match.replace("_", " ").title()), 65

    return None, 0


def _match_role(text: str, role_keywords: dict) -> Optional[str]:
    """
    Cari role yang paling cocok dari text.
    Gunakan keyword matching yang lebih ketat:
    - Hanya hitung keyword yang spesifik (bukan generic seperti 'sql', 'api')
    - Butuh minimal threshold match
    """
    # Keyword yang terlalu generic — hanya dihitung jika ada keyword spesifik lain
    GENERIC_KEYWORDS = {
        "sql", "api", "excel", "dashboard", "pipeline",
        "pricing", "valuation", "reserving",
    }

    best_role = None
    best_score = 0

    for role_name, keywords in role_keywords.items():
        specific_count = 0
        generic_count = 0

        for keyword in keywords:
            kw_lower = keyword.lower()
            if kw_lower in text:
                if kw_lower in GENERIC_KEYWORDS:
                    generic_count += 1
                else:
                    specific_count += 1

        # Butuh minimal 1 keyword spesifik untuk match
        if specific_count == 0:
            continue

        score = specific_count * 3 + generic_count * 1
        if score > best_score:
            best_score = score
            best_role = role_name

    return best_role


def detect_category(role: Optional[str]) -> Optional[str]:
    """Map role ke kategori. Return None jika role kosong."""
    if not role:
        return None

    role_lower = role.lower()
    if any(k in role_lower for k in ["frontend", "backend", "fullstack", "mobile", "software", "engineer"]):
        return "tech"
    if any(k in role_lower for k in ["data analyst", "data engineer", "ai", "ml"]):
        return "data"
    if any(k in role_lower for k in ["actuarial", "actuary", "aktuaria"]):
        return "actuarial"
    if any(k in role_lower for k in ["finance", "accounting", "risk", "investment", "banking"]):
        return "finance"
    return None  # Better null daripada "other" yang menyesatkan


# --- Field Detectors (strict) ---

def detect_location(text: str, config: dict) -> Optional[str]:
    """Deteksi lokasi dari teks awal."""
    text_lower = text[:3000].lower()
    locations = config.get("locations", [])

    for loc in locations:
        if loc.lower() in text_lower:
            return loc
    return None


def detect_work_mode(text: str) -> Optional[str]:
    """Deteksi work mode: remote, hybrid, onsite."""
    text_lower = text[:3000].lower()
    for mode, signals in WORK_MODE_MAP:
        for signal in signals:
            if signal in text_lower:
                return mode
    return None


def detect_deadline(text: str) -> Optional[str]:
    """
    Deteksi deadline — hanya tanggal eksplisit.
    Reject kalimat seperti "deadline ketat".
    """
    # Cari di sekitar keyword deadline
    deadline_context = ""
    for keyword in ["deadline", "batas akhir", "penutupan", "ditutup", "apply before", "closed"]:
        idx = text.lower().find(keyword)
        if idx >= 0:
            deadline_context += text[max(0, idx):idx + 100] + " "

    # Cari tanggal eksplisit di context atau seluruh teks awal
    search_text = deadline_context if deadline_context else text[:3000]

    for pattern in STRICT_DATE_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    return None


def detect_salary(text: str) -> Optional[str]:
    """
    Deteksi salary — hanya format valid.
    Reject noise seperti "RP,", angka gabungan aneh, dll.
    """
    search_text = text[:5000]

    for pattern in STRICT_SALARY_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            result = match.group(0).strip()

            # Validasi: buang jika terlalu pendek (e.g., "Rp") atau terlalu panjang
            if len(result) < 4 or len(result) > 50:
                continue

            # Buang jika hanya "Rp" tanpa angka
            if re.match(r"^(Rp\.?|IDR)\s*$", result):
                continue

            return result

    return None


def detect_duration(text: str) -> Optional[str]:
    """
    Deteksi durasi — hanya format valid.
    Angka harus 1-24 (bulan) atau 1-52 (minggu).
    """
    search_text = text[:5000]

    for pattern in STRICT_DURATION_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            num = int(match.group(1))

            # Validasi range
            if "bulan" in match.group(0).lower() or "month" in match.group(0).lower():
                if 1 <= num <= 24:
                    return match.group(0).strip()
            elif "minggu" in match.group(0).lower() or "week" in match.group(0).lower():
                if 1 <= num <= 52:
                    return match.group(0).strip()

    return None


def detect_company(text: str, title: str) -> Optional[str]:
    """Deteksi nama perusahaan dari title atau teks awal."""
    combined = f"{title}\n{text[:2000]}"

    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, combined)
        if match:
            company = match.group(1).strip()
            if len(company) > 2 and len(company) < 100:
                return company

    return None


def generate_summary(text: str, max_length: int = 300) -> str:
    """Generate ringkasan singkat dari teks."""
    lines = [line.strip() for line in text.split("\n") if len(line.strip()) > 30]
    summary = " ".join(lines[:5])

    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(" ", 1)[0] + "..."

    return summary


def get_source_name(url: str) -> str:
    """Ambil nama source dari URL."""
    domain = urlparse(url).netloc
    domain = domain.replace("www.", "")
    return domain


# --- Main Extractor ---

def extract_opportunity(page: RawPage, config_path: Optional[Path] = None) -> Optional[Opportunity]:
    """
    Ekstrak metadata lowongan dari satu halaman DETAIL.

    Quality gates:
    1. Reject listing pages
    2. Internship gate — harus ada sinyal magang
    3. Role detection dari title first
    4. Strict salary/duration/deadline
    """
    from engine.listing_parser import classify_page, is_listing_title, detect_platform

    title = page.title or ""

    # GATE 1: Reject halaman listing
    page_type = page.page_type if page.page_type != "unknown" else classify_page(page.url, title)
    if page_type == "listing":
        return None

    if is_listing_title(title):
        return None

    config = load_keywords(config_path)
    text = page.text_content

    # GATE 2: Internship gate
    is_intern, intern_confidence, intern_source = detect_internship(text, title, config)
    if not is_intern:
        return None

    # Ekstrak fields dengan quality-first approach
    role, role_confidence = detect_role(title, text, config)
    category = detect_category(role) if role_confidence >= 60 else None
    location = detect_location(text, config)
    work_mode = detect_work_mode(text)
    deadline = detect_deadline(text)
    salary = detect_salary(text)
    duration = detect_duration(text)
    company = detect_company(text, title)
    summary = generate_summary(text)
    source_name = get_source_name(page.url)
    platform = page.source_platform or detect_platform(page.url)

    # Clean title
    opp_title = title if title else "Untitled Opportunity"
    opp_title = opp_title[:200]

    # Overall confidence: gabungan internship + role
    confidence = intern_confidence
    if role_confidence >= 60:
        confidence = min(100, confidence + 10)

    return Opportunity(
        title=opp_title,
        company=company,
        role=role,
        category=category,
        location=location,
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
        page_type="detail",
        extraction_status="extracted",
    )


def extract_all(pages: list[RawPage], config_path: Optional[Path] = None) -> list[Opportunity]:
    """
    Ekstrak opportunities HANYA dari halaman detail.
    Halaman listing dan non-internship di-skip.
    """
    opportunities = []
    skipped_listing = 0
    skipped_not_intern = 0

    for page in pages:
        if page.page_type == "listing":
            skipped_listing += 1
            continue

        opp = extract_opportunity(page, config_path)
        if opp:
            opportunities.append(opp)
        else:
            skipped_not_intern += 1

    if skipped_listing > 0:
        console.print(f"  [dim]Skipped {skipped_listing} listing pages[/dim]")
    if skipped_not_intern > 0:
        console.print(f"  [dim]Skipped {skipped_not_intern} non-internship/irrelevant pages[/dim]")
    console.print(f"[green][OK][/green] Extracted {len(opportunities)} opportunities from {len(pages)} pages")
    return opportunities
