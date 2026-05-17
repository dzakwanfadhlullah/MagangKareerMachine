"""Dashboard read model and readiness validation."""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.db import get_all_opportunities, get_connection
from engine.extractor import is_valid_company
from engine.listing_parser import is_listing_url
from engine.url_utils import has_tracking_params

DASHBOARD_REQUIRED_FIELDS = [
    "id",
    "title",
    "company",
    "role",
    "role_specialization",
    "category",
    "source_platform",
    "source_url",
    "score",
    "dashboard_quality",
    "extraction_depth",
    "verification_level",
    "active_status",
    "summary_short",
    "first_seen",
    "last_verified_at",
]

DASHBOARD_SAFE_FIELDS = [
    "id",
    "title",
    "company",
    "role",
    "role_family",
    "role_group",
    "role_specialization",
    "category",
    "location",
    "location_area",
    "location_status",
    "work_mode",
    "salary_display",
    "salary_status",
    "duration",
    "duration_status",
    "deadline",
    "deadline_status",
    "source_platform",
    "source_platform_label",
    "source_url",
    "apply_url",
    "score",
    "dashboard_quality",
    "extraction_depth",
    "verification_level",
    "active_status",
    "mixed_employment_signal",
    "display_location",
    "display_salary",
    "summary_short",
    "first_seen",
    "last_verified_at",
]


def _safe_summary(opp: dict) -> Optional[str]:
    summary = opp.get("summary_short") or opp.get("summary")
    if not summary:
        return None
    compact = " ".join(str(summary).split())
    if len(compact) > 180:
        compact = compact[:180].rsplit(" ", 1)[0] + "..."
    return compact


def build_dashboard_row(opp: dict) -> dict:
    """Convert an opportunity DB row into a dashboard-safe contract."""
    row = {
        "id": str(opp.get("id")),
        "title": opp.get("title"),
        "company": opp.get("company"),
        "role": opp.get("role"),
        "role_family": opp.get("role_family"),
        "role_group": opp.get("role_group"),
        "role_specialization": opp.get("role_specialization"),
        "category": opp.get("category"),
        "location": opp.get("location"),
        "location_area": opp.get("location_area"),
        "location_status": opp.get("location_status") or "not_provided",
        "work_mode": opp.get("work_mode"),
        "salary_display": opp.get("salary_display"),
        "salary_status": opp.get("salary_status") or "not_provided",
        "duration": opp.get("duration"),
        "duration_status": opp.get("duration_status") or "not_provided",
        "deadline": opp.get("deadline"),
        "deadline_status": opp.get("deadline_status") or "not_provided",
        "source_platform": opp.get("source_platform"),
        "source_platform_label": opp.get("source_platform_label") or (opp.get("source_platform") or "").title(),
        "source_url": opp.get("source_url"),
        "apply_url": opp.get("apply_url") or opp.get("source_url"),
        "score": opp.get("score") or 0,
        "dashboard_quality": opp.get("dashboard_quality") or "medium",
        "extraction_depth": opp.get("extraction_depth") or "full_detail",
        "verification_level": opp.get("verification_level") or "verified_detail",
        "active_status": opp.get("active_status") or "unknown",
        "mixed_employment_signal": bool(opp.get("mixed_employment_signal")),
        "display_location": opp.get("display_location") or ("Belum tersedia" if (opp.get("location_status") == "unknown_due_to_partial_extraction") else "Tidak dicantumkan"),
        "display_salary": opp.get("display_salary") or ("Belum tersedia" if (opp.get("salary_status") == "unknown_due_to_partial_extraction") else "Tidak dicantumkan"),
        "summary_short": _safe_summary(opp),
        "first_seen": opp.get("first_seen"),
        "last_verified_at": opp.get("last_seen"),
    }
    return {field: row.get(field) for field in DASHBOARD_SAFE_FIELDS}


def dashboard_metadata(rows: list[dict]) -> dict:
    platforms = Counter(row.get("source_platform") or "unknown" for row in rows)
    quality = Counter(row.get("dashboard_quality") or "unknown" for row in rows)
    extraction_depth = Counter(row.get("extraction_depth") or "unknown" for row in rows)
    full_detail_platforms = Counter(
        row.get("source_platform") or "unknown"
        for row in rows
        if row.get("extraction_depth") == "full_detail"
    )
    partial_platforms = Counter(
        row.get("source_platform") or "unknown"
        for row in rows
        if row.get("extraction_depth") != "full_detail"
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result_count": len(rows),
        "accepted_by_platform": dict(platforms),
        "accepted_by_dashboard_quality": dict(quality),
        "accepted_by_extraction_depth": dict(extraction_depth),
        "accepted_full_detail_by_platform": dict(full_detail_platforms),
        "accepted_partial_by_platform": dict(partial_platforms),
        "source_diversity_warning": len(platforms) <= 1 and len(rows) > 1,
        "full_detail_source_diversity_warning": len(full_detail_platforms) <= 1 and len(rows) > 1,
    }


def export_dashboard(
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> tuple[str, str]:
    """Export frontend-safe opportunities and metadata."""
    base = Path(output_dir or os.path.join(os.getenv("EXPORT_DIR", "exports"), "dashboard"))
    base.mkdir(parents=True, exist_ok=True)
    opportunities = get_all_opportunities(db_path)
    rows = [build_dashboard_row(opp) for opp in opportunities]
    metadata = dashboard_metadata(rows)

    opportunities_path = base / "opportunities.json"
    metadata_path = base / "metadata.json"
    opportunities_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(opportunities_path), str(metadata_path)


def user_applications_schema_exists(db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_applications'"
        ).fetchone()
        if not row:
            return False
        columns = {item["name"] for item in conn.execute("PRAGMA table_info(user_applications)").fetchall()}
        return {
            "id",
            "user_id",
            "opportunity_id",
            "status",
            "notes",
            "applied_at",
            "created_at",
            "updated_at",
        }.issubset(columns)
    finally:
        conn.close()


def validate_dashboard_ready(
    db_path: Optional[str] = None,
    min_results: int = 30,
) -> tuple[list[str], list[str], dict]:
    """Return hard issues, warnings, and stats for dashboard readiness."""
    opportunities = get_all_opportunities(db_path)
    rows = [build_dashboard_row(opp) for opp in opportunities]
    issues: list[str] = []
    warnings: list[str] = []

    source_urls = []
    for row in rows:
        source_url = row.get("source_url") or ""
        source_urls.append(source_url)
        if not source_url:
            issues.append(f"[MISSING SOURCE URL] {row.get('title')}")
        elif is_listing_url(source_url):
            issues.append(f"[LISTING URL] {source_url}")
        elif has_tracking_params(source_url):
            issues.append(f"[TRACKING URL] {source_url}")

        for field in DASHBOARD_REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                issues.append(f"[MISSING DASHBOARD FIELD:{field}] {row.get('title') or source_url}")

        company = row.get("company")
        if company and not is_valid_company(company):
            issues.append(f"[BAD COMPANY] {row.get('title')} -> {company}")

        if row.get("work_mode") and row.get("work_mode") not in {"remote", "hybrid", "onsite"}:
            issues.append(f"[BAD WORK MODE] {row.get('title')} -> {row.get('work_mode')}")

        if row.get("dashboard_quality") not in {"high", "medium", "low"}:
            issues.append(f"[BAD QUALITY] {row.get('title')} -> {row.get('dashboard_quality')}")
        if row.get("extraction_depth") not in {"full_detail", "listing_card", "search_snippet"}:
            issues.append(f"[BAD EXTRACTION DEPTH] {row.get('title')} -> {row.get('extraction_depth')}")
        if row.get("active_status") not in {"active", "listed", "unknown", "closed"}:
            issues.append(f"[BAD ACTIVE STATUS] {row.get('title')} -> {row.get('active_status')}")
        if row.get("active_status") == "closed":
            issues.append(f"[CLOSED ACCEPTED] {row.get('title')}")

    duplicates = [url for url, count in Counter(source_urls).items() if url and count > 1]
    for url in duplicates:
        issues.append(f"[DUPLICATE SOURCE URL] {url}")

    metadata = dashboard_metadata(rows)
    platform_count = len(metadata["accepted_by_platform"])
    full_detail_platforms = metadata["accepted_full_detail_by_platform"]
    non_glints_full_detail = {
        platform: count
        for platform, count in full_detail_platforms.items()
        if platform != "glints" and count > 0
    }

    if len(rows) < min_results:
        warnings.append(f"[LOW RESULT COUNT] {len(rows)} accepted results, target {min_results}+")
    if platform_count < 2 and len(rows) > 1:
        warnings.append("[LOW SOURCE DIVERSITY] fewer than 2 accepted platforms")
    if not non_glints_full_detail:
        warnings.append("[NON-GLINTS FULL DETAIL] no non-Glints full-detail accepted result yet")
    if not user_applications_schema_exists(db_path):
        issues.append("[MISSING SCHEMA] user_applications table is missing or incomplete")

    stats = {
        **metadata,
        "required_fields": DASHBOARD_REQUIRED_FIELDS,
        "issues": len(issues),
        "warnings": len(warnings),
    }
    return issues, warnings, stats
