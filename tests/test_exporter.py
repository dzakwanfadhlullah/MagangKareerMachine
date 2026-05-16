"""Tests for export behavior."""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import init_db
from engine.exporter import EXPORT_COLUMNS, export_all, export_csv, export_json


def test_empty_export_overwrites_stale_files(tmp_path):
    db_path = str(tmp_path / "empty.db")
    csv_path = tmp_path / "results.csv"
    json_path = tmp_path / "results.json"
    csv_path.write_text("stale\nold\n", encoding="utf-8")
    json_path.write_text('[{"title": "stale"}]', encoding="utf-8")

    init_db(db_path)
    export_csv(db_path=db_path, output_path=str(csv_path))
    export_json(db_path=db_path, output_path=str(json_path))

    assert json.loads(json_path.read_text(encoding="utf-8")) == []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert rows == [EXPORT_COLUMNS]


def test_export_all_writes_run_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "empty.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setattr("engine.exporter.EXPORT_DIR", str(export_dir))

    init_db(db_path)
    export_all(db_path=db_path, metadata={"command": "crawl-sources", "target_category": "actuarial"})

    metadata = json.loads((export_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["db_path"] == db_path
    assert metadata["result_count"] == 0
    assert metadata["command"] == "crawl-sources"
    assert metadata["target_category"] == "actuarial"
