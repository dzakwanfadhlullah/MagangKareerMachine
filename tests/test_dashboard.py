"""Tests for dashboard-safe read model."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.dashboard import build_dashboard_row, export_dashboard, validate_dashboard_ready
from engine.db import init_db


def test_build_dashboard_row_excludes_debug_fields():
    row = build_dashboard_row({
        "id": 1,
        "title": "Frontend Developer Intern",
        "company": "Example Co",
        "role": "Frontend Developer",
        "role_family": "tech",
        "role_group": "software_engineering",
        "role_specialization": "frontend",
        "category": "tech",
        "source_platform": "glints",
        "source_platform_label": "Glints",
        "source_url": "https://glints.com/id/opportunities/jobs/frontend/abc",
        "score": 90,
        "dashboard_quality": "high",
        "extraction_depth": "full_detail",
        "verification_level": "verified_detail",
        "active_status": "active",
        "summary_short": "Good internship.",
        "raw_text": "debug text",
        "original_url": "https://tracking.example",
        "first_seen": "2026-05-17",
        "last_seen": "2026-05-17",
    })

    assert row["id"] == "1"
    assert row["last_verified_at"] == "2026-05-17"
    assert "raw_text" not in row
    assert "original_url" not in row


def test_export_dashboard_writes_safe_files(tmp_path):
    db_path = str(tmp_path / "dashboard.db")
    output_dir = tmp_path / "dashboard"
    init_db(db_path)

    opportunities_path, metadata_path = export_dashboard(db_path=db_path, output_dir=str(output_dir))

    assert json.loads(open(opportunities_path, encoding="utf-8").read()) == []
    metadata = json.loads(open(metadata_path, encoding="utf-8").read())
    assert metadata["result_count"] == 0


def test_validate_dashboard_ready_accepts_empty_schema_with_low_count_warning(tmp_path):
    db_path = str(tmp_path / "dashboard-ready.db")
    init_db(db_path)

    issues, warnings, stats = validate_dashboard_ready(db_path=db_path, min_results=1)

    assert issues == []
    assert any("LOW RESULT COUNT" in warning for warning in warnings)
    assert stats["result_count"] == 0
