"""Tests for pipeline-stage filtering and ranking helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import _prioritize_target_links, _target_link_score


def test_target_link_score_detects_actuarial_card():
    link = {
        "title": "Pricing & Valuation Internship (Actuary)",
        "url": "https://glints.com/id/opportunities/jobs/pricing-and-valuation-internship-actuary/123",
    }
    assert _target_link_score(link, "actuarial") >= 100


def test_target_priority_moves_actuarial_before_generic_internships():
    links = [
        {"title": "Warehouse Internship", "url": "https://example.com/warehouse-internship"},
        {"title": "Legal Internship", "url": "https://example.com/legal-internship"},
        {
            "title": "Pricing & Valuation Internship (Actuary)",
            "url": "https://example.com/pricing-and-valuation-internship-actuary",
        },
    ]

    prioritized = _prioritize_target_links(links, "actuarial")

    assert prioritized[0]["title"] == "Pricing & Valuation Internship (Actuary)"
    assert [link["title"] for link in prioritized[1:]] == ["Warehouse Internship", "Legal Internship"]
