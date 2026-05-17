"""Exporter — ekspor data opportunities ke CSV dan JSON."""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import pandas as pd
from rich.console import Console

from engine.db import get_all_opportunities

console = Console()

EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")

# Kolom untuk ekspor
EXPORT_COLUMNS = [
    "id", "score", "title", "company", "role", "category",
    "company_confidence", "location", "location_area", "work_mode", "duration",
    "salary", "salary_raw", "salary_display", "salary_min", "salary_max", "salary_confidence", "deadline",
    "source_name", "source_platform", "source_url", "detail_url", "original_url",
    "is_internship", "internship_confidence", "role_confidence",
    "score_breakdown", "page_type", "extraction_status", "summary", "first_seen", "last_seen",
]


def ensure_export_dir() -> None:
    """Pastikan folder exports ada."""
    Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)


def _clean_opportunities(opportunities: list[dict]) -> list[dict]:
    """Keep only stable export columns."""
    cleaned = []
    for opp in opportunities:
        row = {col: opp.get(col) for col in EXPORT_COLUMNS if col in opp}
        breakdown = row.get("score_breakdown")
        if isinstance(breakdown, str) and breakdown:
            try:
                row["score_breakdown"] = json.loads(breakdown)
            except json.JSONDecodeError:
                pass
        cleaned.append(row)
    return cleaned


def export_csv(db_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """
    Ekspor semua opportunities ke CSV.
    Return path file yang dihasilkan.
    """
    ensure_export_dir()
    path = output_path or os.path.join(EXPORT_DIR, "results.csv")

    opportunities = get_all_opportunities(db_path)
    df = pd.DataFrame(_clean_opportunities(opportunities), columns=EXPORT_COLUMNS)

    # Pilih kolom yang ada saja
    available_cols = [col for col in EXPORT_COLUMNS if col in df.columns]
    df = df[available_cols]

    df.to_csv(path, index=False, encoding="utf-8-sig")
    if opportunities:
        console.print(f"[green][OK][/green] Exported {len(df)} opportunities to {path}")
    else:
        console.print(f"[yellow][WARN][/yellow] Exported empty results to {path}")
    return path


def export_json(db_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """
    Ekspor semua opportunities ke JSON.
    Return path file yang dihasilkan.
    """
    ensure_export_dir()
    path = output_path or os.path.join(EXPORT_DIR, "results.json")

    opportunities = get_all_opportunities(db_path)
    cleaned = _clean_opportunities(opportunities)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2, default=str)

    if cleaned:
        console.print(f"[green][OK][/green] Exported {len(cleaned)} opportunities to {path}")
    else:
        console.print(f"[yellow][WARN][/yellow] Exported empty results to {path}")
    return path


def export_metadata(
    db_path: Optional[str] = None,
    output_path: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Write run metadata next to exports so stale artifacts are obvious."""
    ensure_export_dir()
    path = output_path or os.path.join(EXPORT_DIR, "run_metadata.json")
    opportunities = get_all_opportunities(db_path)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path or os.getenv("DB_PATH") or "data/magangkareer.db",
        "export_dir": EXPORT_DIR,
        "result_count": len(opportunities),
    }
    if metadata:
        payload.update(metadata)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    console.print(f"[green][OK][/green] Exported run metadata to {path}")
    return path


def export_all(db_path: Optional[str] = None, metadata: Optional[dict] = None) -> tuple[str, str]:
    """Ekspor ke CSV dan JSON sekaligus."""
    csv_path = export_csv(db_path)
    json_path = export_json(db_path)
    export_metadata(db_path, metadata=metadata)
    return csv_path, json_path
