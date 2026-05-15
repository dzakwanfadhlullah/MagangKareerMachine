"""Exporter — ekspor data opportunities ke CSV dan JSON."""

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console

from engine.db import get_all_opportunities

console = Console()

EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")

# Kolom untuk ekspor
EXPORT_COLUMNS = [
    "id", "score", "title", "company", "role", "category",
    "location", "work_mode", "duration", "salary", "deadline",
    "source_name", "source_platform", "source_url", "detail_url",
    "page_type", "extraction_status", "summary", "first_seen", "last_seen",
]


def ensure_export_dir() -> None:
    """Pastikan folder exports ada."""
    Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)


def export_csv(db_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """
    Ekspor semua opportunities ke CSV.
    Return path file yang dihasilkan.
    """
    ensure_export_dir()
    path = output_path or os.path.join(EXPORT_DIR, "results.csv")

    opportunities = get_all_opportunities(db_path)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities to export")
        return path

    df = pd.DataFrame(opportunities)

    # Pilih kolom yang ada saja
    available_cols = [col for col in EXPORT_COLUMNS if col in df.columns]
    df = df[available_cols]

    df.to_csv(path, index=False, encoding="utf-8-sig")
    console.print(f"[green][OK][/green] Exported {len(df)} opportunities to {path}")
    return path


def export_json(db_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """
    Ekspor semua opportunities ke JSON.
    Return path file yang dihasilkan.
    """
    ensure_export_dir()
    path = output_path or os.path.join(EXPORT_DIR, "results.json")

    opportunities = get_all_opportunities(db_path)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities to export")
        return path

    # Pilih kolom yang relevan
    cleaned = []
    for opp in opportunities:
        item = {col: opp.get(col) for col in EXPORT_COLUMNS if col in opp}
        cleaned.append(item)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2, default=str)

    console.print(f"[green][OK][/green] Exported {len(cleaned)} opportunities to {path}")
    return path


def export_all(db_path: Optional[str] = None) -> tuple[str, str]:
    """Ekspor ke CSV dan JSON sekaligus."""
    csv_path = export_csv(db_path)
    json_path = export_json(db_path)
    return csv_path, json_path
