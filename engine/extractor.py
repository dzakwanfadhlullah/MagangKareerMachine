"""Extractor — ekstrak metadata lowongan dari teks halaman (rule-based)."""

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

# Pola tanggal Indonesia/English
DATE_PATTERNS = [
    # 19 Mei 2026, 30 May 2026
    r"\b(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|"
    r"January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    # 2026-05-19
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
    # 19/05/2026 or 19-05-2026
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b",
    # Apply before 30 June, Penutupan lamaran: ...
    r"(?:apply before|deadline|penutupan|batas akhir|ditutup)[:\s]+(.+?)(?:\.|$)",
]

# Pola work mode
WORK_MODE_MAP = {
    "remote": ["remote", "wfh", "work from home", "kerja dari rumah", "fully remote"],
    "hybrid": ["hybrid", "wfo/wfh", "flexible"],
    "onsite": ["onsite", "on-site", "on site", "wfo", "work from office", "di kantor"],
}

# Pola salary
SALARY_PATTERNS = [
    r"Rp\s?[\d.,]+",
    r"IDR\s?[\d.,]+",
    r"\d+[\-–]\d+\s*juta",
    r"\d+\s*juta",
    r"(?:uang saku|allowance|stipend)[:\s]+[\w\d.,\s]+",
    r"paid internship",
    r"unpaid",
]

# Pola durasi
DURATION_PATTERNS = [
    r"(\d+)\s*(?:bulan|months?)",
    r"(\d+)\s*(?:minggu|weeks?)",
    r"(\d+)\s*(?:hari|days?)",
]

# Pola company
COMPANY_PATTERNS = [
    r"(?:at|di|@)\s+([A-Z][A-Za-z\s&.]+?)(?:\s*[-–|,]|\s*$)",
    r"[-–—]\s*(?:PT\.?\s+)?([A-Z][A-Za-z\s&.]+?)(?:\s*[-–|,]|\s*$)",
    r"(?:PT\.?\s+)([A-Z][A-Za-z\s&.]+)",
    r"(?:perusahaan|company)[:\s]+([A-Za-z\s&.]+?)(?:\s*[-–|,.\n])",
]


def load_keywords(config_path: Optional[Path] = None) -> dict:
    """Load keyword config."""
    path = config_path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_internship(text: str, config: dict) -> tuple[bool, int]:
    """
    Deteksi apakah teks berisi lowongan magang.
    Return (is_internship, confidence_score).
    """
    text_lower = text.lower()
    internship_terms = config.get("internship_terms", [])
    negative_terms = config.get("negative_terms", [])

    # Hitung sinyal positif
    positive_count = 0
    for term in internship_terms:
        if term.lower() in text_lower:
            positive_count += 1

    # Extra positive signals
    extra_positive = ["program magang", "mahasiswa", "fresh graduate", "semester akhir", "akhir kuliah"]
    for signal in extra_positive:
        if signal in text_lower:
            positive_count += 1

    # Hitung sinyal negatif
    negative_count = 0
    for term in negative_terms:
        if term.lower() in text_lower:
            negative_count += 1

    is_internship = positive_count > 0 and negative_count == 0
    confidence = min(positive_count * 20, 100) - (negative_count * 30)
    confidence = max(0, min(100, confidence))

    return is_internship, confidence


def detect_role(text: str, config: dict) -> Optional[str]:
    """Deteksi role dari teks berdasarkan keyword mapping."""
    text_lower = text.lower()
    role_keywords = config.get("role_keywords", {})

    best_role = None
    best_count = 0

    for role_name, keywords in role_keywords.items():
        count = 0
        for keyword in keywords:
            if keyword.lower() in text_lower:
                count += 1
        if count > best_count:
            best_count = count
            best_role = role_name

    if best_role:
        # Format nama role
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
        return role_display.get(best_role, best_role.replace("_", " ").title())

    return None


def detect_category(role: Optional[str]) -> Optional[str]:
    """Map role ke kategori."""
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
    return "other"


def detect_location(text: str, config: dict) -> Optional[str]:
    """Deteksi lokasi dari teks."""
    text_lower = text.lower()
    locations = config.get("locations", [])

    for loc in locations:
        if loc.lower() in text_lower:
            return loc
    return None


def detect_work_mode(text: str) -> Optional[str]:
    """Deteksi work mode: remote, hybrid, onsite."""
    text_lower = text.lower()
    for mode, signals in WORK_MODE_MAP.items():
        for signal in signals:
            if signal in text_lower:
                return mode
    return None


def detect_deadline(text: str) -> Optional[str]:
    """Deteksi deadline dari teks menggunakan regex."""
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def detect_salary(text: str) -> Optional[str]:
    """Deteksi informasi gaji/uang saku dari teks."""
    for pattern in SALARY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def detect_duration(text: str) -> Optional[str]:
    """Deteksi durasi magang dari teks."""
    for pattern in DURATION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def detect_company(text: str, title: str) -> Optional[str]:
    """Deteksi nama perusahaan dari teks atau title."""
    # Coba dari title dulu
    combined = f"{title}\n{text[:2000]}"

    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, combined)
        if match:
            company = match.group(1).strip()
            # Filter: company harus minimal 2 kata atau diawali PT
            if len(company) > 2 and len(company) < 100:
                return company

    return None


def generate_summary(text: str, max_length: int = 300) -> str:
    """Generate ringkasan singkat dari teks."""
    # Ambil beberapa kalimat pertama yang bermakna
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


def extract_opportunity(page: RawPage, config_path: Optional[Path] = None) -> Optional[Opportunity]:
    """
    Ekstrak metadata lowongan dari satu halaman.

    Return Opportunity jika halaman berisi lowongan magang.
    Return None jika tidak relevan.
    """
    config = load_keywords(config_path)
    text = page.text_content
    title = page.title or ""

    # Deteksi internship
    is_internship, confidence = detect_internship(text, config)
    if not is_internship and confidence < 20:
        return None

    # Ekstrak semua field
    role = detect_role(text, config)
    category = detect_category(role)
    location = detect_location(text, config)
    work_mode = detect_work_mode(text)
    deadline = detect_deadline(text)
    salary = detect_salary(text)
    duration = detect_duration(text)
    company = detect_company(text, title)
    summary = generate_summary(text)
    source_name = get_source_name(page.url)

    # Gunakan title dari page, bersihkan
    opp_title = title if title else "Untitled Opportunity"
    opp_title = opp_title[:200]  # Limit panjang

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
        source_name=source_name,
        raw_text=text[:5000],  # Simpan sebagian teks mentah
        summary=summary,
        score=0,  # Akan diisi oleh scorer
        confidence=confidence,
    )


def extract_all(pages: list[RawPage], config_path: Optional[Path] = None) -> list[Opportunity]:
    """Ekstrak opportunities dari semua halaman."""
    opportunities = []

    for page in pages:
        opp = extract_opportunity(page, config_path)
        if opp:
            opportunities.append(opp)

    console.print(f"[green][OK][/green] Extracted {len(opportunities)} opportunities from {len(pages)} pages")
    return opportunities
