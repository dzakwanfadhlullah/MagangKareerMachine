"""Tests for tiered source loading and crawl profiles."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.searcher import (
    get_crawl_profile,
    iter_manual_source_entries,
    load_sources,
    search_manual_sources,
)


def test_tiered_sources_loaded():
    config = load_sources()
    entries = iter_manual_source_entries(config)
    platforms = {entry.get("platform") for entry in entries}

    assert "tier_1" in config["sources"]
    assert "tier_2" in config["sources"]
    assert len(entries) >= 13
    for platform in {"dealls", "glints", "kalibrr", "jobstreet", "lokerid", "prosple", "indeed"}:
        assert platform in platforms
    print(f"[PASS] tiered sources loaded -> {len(entries)} entries")


def test_search_manual_sources_keeps_tier_order():
    results = search_manual_sources()
    assert results[0].url == "https://dealls.com/loker/tipe/loker-magang"
    assert results[0].query == "manual_source:tier_1"
    assert any(r.source_platform == "indeed" for r in results)
    print("[PASS] manual sources keep tier order")


def test_targeted_sources_are_prepended():
    config = load_sources()
    entries = iter_manual_source_entries(config, target_category="actuarial")
    results = search_manual_sources(target_category="actuarial")

    assert entries[0]["tier"] == "role:actuarial"
    assert entries[0]["name"] == "glints_magang_targeted_scan"
    assert results[0].query == "manual_source:role:actuarial"
    assert results[0].source_platform == "glints"
    assert any(entry["name"] == "manulife_actuarial_internship_2026" for entry in entries)
    manulife = next(r for r in results if "Manulife-6-5-months-Actuarial" in r.url)
    assert manulife.page_type == "detail"
    assert any(r.query == "manual_source:tier_1" for r in results)


def test_crawl_profiles():
    quick = get_crawl_profile("quick")
    normal = get_crawl_profile("normal")
    deep = get_crawl_profile("deep")

    assert quick["max_total_detail"] < normal["max_total_detail"] < deep["max_total_detail"]
    assert normal["max_sources"] == 8
    assert deep["workers"] == 8
    print("[PASS] crawl profiles")
