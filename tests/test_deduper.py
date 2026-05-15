"""Tests untuk Deduper module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import Opportunity
from engine.deduper import (
    normalize_text,
    generate_canonical_key,
    fuzzy_is_duplicate,
    dedupe_opportunities,
)


def test_normalize_text():
    assert normalize_text("  Hello, World!  ") == "hello world"
    assert normalize_text("PT. Example Tech") == "pt example tech"
    assert normalize_text("") == ""
    print("[PASS] normalize_text")


def test_generate_canonical_key():
    opp1 = Opportunity(
        title="Frontend Intern",
        company="PT Example",
        role="Frontend Developer",
        location="Jakarta",
        source_url="https://glints.com/jobs/1",
    )
    opp2 = Opportunity(
        title="Frontend Intern",
        company="PT Example",
        role="Frontend Developer",
        location="Jakarta",
        source_url="https://jobstreet.com/jobs/2",
    )

    key1 = generate_canonical_key(opp1)
    key2 = generate_canonical_key(opp2)
    assert key1 == key2, "Same opportunity from different sources should have same key"
    print(f"[PASS] generate_canonical_key (same -> {key1})")


def test_generate_canonical_key_different():
    opp1 = Opportunity(
        title="Frontend Intern",
        company="PT Example",
        source_url="https://glints.com/1",
    )
    opp2 = Opportunity(
        title="Backend Intern",
        company="PT Other",
        source_url="https://glints.com/2",
    )

    key1 = generate_canonical_key(opp1)
    key2 = generate_canonical_key(opp2)
    assert key1 != key2, "Different opportunities should have different keys"
    print("[PASS] generate_canonical_key (different)")


def test_fuzzy_is_duplicate():
    opp1 = Opportunity(
        title="Frontend Developer Intern - PT Example",
        role="Frontend Developer",
        location="Jakarta",
        source_url="https://a.com",
    )
    opp2 = Opportunity(
        title="Frontend Developer Intern – PT Example",
        role="Frontend Developer",
        location="Jakarta",
        source_url="https://b.com",
    )
    assert fuzzy_is_duplicate(opp1, opp2) is True
    print("[PASS] fuzzy_is_duplicate (similar)")


def test_fuzzy_not_duplicate():
    opp1 = Opportunity(
        title="Frontend Developer Intern",
        source_url="https://a.com",
    )
    opp2 = Opportunity(
        title="Backend Engineer Full-time",
        source_url="https://b.com",
    )
    assert fuzzy_is_duplicate(opp1, opp2) is False
    print("[PASS] fuzzy_is_duplicate (different)")


def test_dedupe_opportunities():
    opps = [
        Opportunity(title="Frontend Intern", company="PT A", role="Frontend", location="Jakarta", source_url="https://a.com", score=80),
        Opportunity(title="Frontend Intern", company="PT A", role="Frontend", location="Jakarta", source_url="https://b.com", score=90),
        Opportunity(title="Backend Intern", company="PT B", role="Backend", location="Bandung", source_url="https://c.com", score=70),
    ]

    result = dedupe_opportunities(opps)
    assert len(result) == 2, f"Expected 2 unique, got {len(result)}"

    # Yang disimpan harus skor tertinggi
    frontend = [o for o in result if "frontend" in o.title.lower()][0]
    assert frontend.score == 90, f"Expected score 90, got {frontend.score}"
    print(f"[PASS] dedupe_opportunities: {len(opps)} -> {len(result)}")


if __name__ == "__main__":
    test_normalize_text()
    test_generate_canonical_key()
    test_generate_canonical_key_different()
    test_fuzzy_is_duplicate()
    test_fuzzy_not_duplicate()
    test_dedupe_opportunities()
    print("\n[OK] All deduper tests passed!")
