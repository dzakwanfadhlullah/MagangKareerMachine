"""Tests untuk Scorer module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import Opportunity
from engine.scorer import score_opportunity, check_expired


def test_score_high_relevance():
    """Opportunity yang sangat relevan harus skor tinggi."""
    opp = Opportunity(
        title="Frontend Developer Intern",
        company="PT Example",
        role="Frontend Developer",
        location="Jakarta",
        work_mode="remote",
        salary="Rp3.000.000",
        deadline="19 Mei 2026",
        source_url="https://glints.com/jobs/frontend-intern",
        raw_text="Kami membuka lowongan magang frontend developer. Apply sekarang. React Next.js",
    )

    scored = score_opportunity(opp)
    assert scored.score >= 70, f"Expected >= 70, got {scored.score}"
    print(f"[PASS] High relevance score: {scored.score}")


def test_score_low_relevance():
    """Opportunity yang kurang relevan harus skor rendah."""
    opp = Opportunity(
        title="Some Random Page",
        source_url="https://random-blog.com/article",
        raw_text="This is a blog post about technology trends in 2026.",
    )

    scored = score_opportunity(opp)
    assert scored.score < 40, f"Expected < 40, got {scored.score}"
    print(f"[PASS] Low relevance score: {scored.score}")


def test_score_bootcamp_penalty():
    """Bootcamp harus kena penalti berat."""
    opp = Opportunity(
        title="Bootcamp Frontend Developer",
        source_url="https://bootcamp.com/frontend",
        raw_text="Ikuti bootcamp frontend developer. Magang internship program. Daftar sekarang.",
    )

    scored = score_opportunity(opp)
    assert scored.score < 30, f"Expected < 30 (bootcamp penalty), got {scored.score}"
    print(f"[PASS] Bootcamp penalty score: {scored.score}")


def test_check_expired():
    assert check_expired("01 January 2020") is True
    assert check_expired("01 January 2099") is False
    assert check_expired(None) is False
    assert check_expired("invalid date") is False
    print("[PASS] check_expired")


if __name__ == "__main__":
    test_score_high_relevance()
    test_score_low_relevance()
    test_score_bootcamp_penalty()
    test_check_expired()
    print("\n[OK] All scorer tests passed!")
