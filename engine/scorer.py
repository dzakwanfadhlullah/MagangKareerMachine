"""Scorer — hitung skor relevansi untuk setiap opportunity."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

from engine.models import Opportunity

console = Console()

SCORING_PATH = Path("config/scoring.yml")
KEYWORDS_PATH = Path("config/keywords.yml")

# Sumber resmi / career page
OFFICIAL_DOMAINS = [
    "jobstreet.co.id", "glints.com", "dealls.com", "kalibrr.id",
    "indeed.com", "linkedin.com", "prosple.com", "karir.com",
    "careers", "career", "jobs",
]

# Sinyal apply/lamar
APPLY_SIGNALS = [
    "apply", "lamar", "daftar", "submit", "apply now",
    "lamar sekarang", "kirim lamaran", "register",
]


def load_scoring_config(config_path: Optional[Path] = None) -> dict:
    """Load scoring config dari YAML."""
    path = config_path or SCORING_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_keywords_config(config_path: Optional[Path] = None) -> dict:
    """Load keywords config dari YAML."""
    path = config_path or KEYWORDS_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_expired(deadline_str: Optional[str]) -> bool:
    """Cek apakah deadline sudah lewat."""
    if not deadline_str:
        return False

    # Coba parse beberapa format tanggal
    formats = [
        "%d %B %Y",    # 19 May 2026
        "%Y-%m-%d",    # 2026-05-19
        "%d/%m/%Y",    # 19/05/2026
        "%d-%m-%Y",    # 19-05-2026
    ]

    # Map bulan Indonesia ke English
    id_months = {
        "januari": "January", "februari": "February", "maret": "March",
        "april": "April", "mei": "May", "juni": "June", "juli": "July",
        "agustus": "August", "september": "September", "oktober": "October",
        "november": "November", "desember": "December",
    }

    normalized = deadline_str.strip()
    for id_month, en_month in id_months.items():
        normalized = re.sub(id_month, en_month, normalized, flags=re.IGNORECASE)

    for fmt in formats:
        try:
            deadline_date = datetime.strptime(normalized, fmt)
            return deadline_date < datetime.now()
        except ValueError:
            continue

    return False


def score_opportunity(
    opp: Opportunity,
    scoring_path: Optional[Path] = None,
    keywords_path: Optional[Path] = None,
) -> Opportunity:
    """
    Hitung skor untuk satu opportunity.
    Skor range 0–100, di-clamp.
    """
    config = load_scoring_config(scoring_path)
    keywords = load_keywords_config(keywords_path)
    scores = config.get("score", {})
    penalties = config.get("penalty", {})

    raw_text = (opp.raw_text or "").lower()
    title_lower = (opp.title or "").lower()
    combined = f"{title_lower} {raw_text}"

    total = 0
    breakdown = {
        "internship_score": 0,
        "role_match_score": 0,
        "source_quality_score": 0,
        "metadata_completeness_score": 0,
        "active_status_score": 0,
        "field_confidence_score": 0,
        "penalty_score": 0,
        "final_score": 0,
    }

    # --- Positive Scores ---

    # Internship detected
    intern_cfg = keywords.get("internship_terms", {})
    all_intern_terms = intern_cfg.get("strong", []) + intern_cfg.get("weak", []) if isinstance(intern_cfg, dict) else intern_cfg
    for term in all_intern_terms:
        if term.lower() in combined:
            value = scores.get("internship_detected", 30)
            breakdown["internship_score"] += value
            total += value
            break

    # Role detected
    if opp.role:
        value = scores.get("role_detected", 25)
        breakdown["role_match_score"] += value
        total += value

    # Location detected
    if opp.location:
        value = scores.get("location_detected", 10)
        breakdown["metadata_completeness_score"] += value
        total += value

    # Apply signal
    for signal in APPLY_SIGNALS:
        if signal in combined:
            value = scores.get("apply_signal", 10)
            breakdown["active_status_score"] += value
            total += value
            break

    if opp.active_status == "listed":
        breakdown["active_status_score"] += 5
        total += 5
    elif opp.active_status == "active" and breakdown["active_status_score"] == 0:
        breakdown["active_status_score"] += 8
        total += 8

    # Deadline detected
    if opp.deadline:
        value = scores.get("deadline_detected", 10)
        breakdown["active_status_score"] += value
        total += value

    # Official career source
    source_url = (opp.source_url or "").lower()
    for domain in OFFICIAL_DOMAINS:
        if domain in source_url:
            value = scores.get("official_career_source", 10)
            breakdown["source_quality_score"] += value
            total += value
            break

    # Remote bonus
    if opp.work_mode == "remote":
        value = scores.get("remote_bonus", 5)
        breakdown["field_confidence_score"] += value
        total += value

    # Paid signal
    if (opp.salary_display or opp.salary) and "unpaid" not in (opp.salary_display or opp.salary or "").lower():
        value = scores.get("paid_signal", 5)
        breakdown["field_confidence_score"] += value
        total += value

    if opp.extraction_depth == "full_detail":
        breakdown["field_confidence_score"] += 5
        total += 5
    elif opp.extraction_depth == "search_snippet":
        breakdown["penalty_score"] -= 10
        total -= 10

    # --- Penalties ---

    # Bootcamp/course penalty
    neg_cfg = keywords.get("negative_terms", {})
    hard_reject = neg_cfg.get("hard_reject", []) if isinstance(neg_cfg, dict) else neg_cfg
    for term in hard_reject:
        if term.lower() in combined:
            if "bootcamp" in term.lower():
                value = penalties.get("bootcamp", -40)
            elif "course" in term.lower() or "kelas" in term.lower():
                value = penalties.get("course", -35)
            else:
                value = 0
            breakdown["penalty_score"] += value
            total += value
            break

    # Expired penalty
    if check_expired(opp.deadline):
        value = penalties.get("expired", -50)
        breakdown["penalty_score"] += value
        total += value

    if opp.mixed_employment_signal:
        breakdown["penalty_score"] -= 5
        total -= 5

    # Clamp ke 0–100
    total = max(0, min(100, total))

    # Update opportunity
    opp.score = total
    breakdown["final_score"] = total
    opp.score_breakdown = breakdown
    return opp


def score_all(
    opportunities: list[Opportunity],
    scoring_path: Optional[Path] = None,
    keywords_path: Optional[Path] = None,
) -> list[Opportunity]:
    """Hitung skor untuk semua opportunities."""
    scored = []
    for opp in opportunities:
        scored_opp = score_opportunity(opp, scoring_path, keywords_path)
        scored.append(scored_opp)

    # Urutkan berdasarkan score DESC
    scored.sort(key=lambda x: x.score, reverse=True)

    # Statistik
    high = sum(1 for o in scored if o.score >= 75)
    mid = sum(1 for o in scored if 40 <= o.score < 75)
    low = sum(1 for o in scored if o.score < 40)
    console.print(f"[green][OK][/green] Scored {len(scored)} opportunities (high={high}, mid={mid}, low={low})")

    return scored
