"""Tests for pipeline-stage filtering and ranking helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import (
    _annotate_discovery_links,
    _prioritize_target_links,
    _target_link_score,
    _update_link_diagnostics,
)


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


def test_discovery_annotation_and_diagnostics_count_target_api_links():
    links = _annotate_discovery_links(
        [
            {
                "title": "Pricing & Valuation Internship (Actuary)",
                "url": "https://example.com/pricing-and-valuation-internship-actuary",
                "source_platform": "glints",
                "listing_url": "https://glints.com/listing",
                "discovery_method": "api",
            },
            {
                "title": "Warehouse Internship",
                "url": "https://example.com/warehouse-internship",
                "source_platform": "glints",
                "listing_url": "https://glints.com/listing",
                "discovery_method": "dom",
            },
        ],
        "actuarial",
    )

    assert links[0]["target_score"] > 0
    assert links[1]["target_score"] == 0

    diagnostics = {
        "https://glints.com/listing": {
            "links": 0,
            "dom_links": 0,
            "script_links": 0,
            "api_links": 0,
            "target_links": 0,
        }
    }
    _update_link_diagnostics(diagnostics, "https://glints.com/listing", links)
    assert diagnostics["https://glints.com/listing"]["links"] == 2
    assert diagnostics["https://glints.com/listing"]["api_links"] == 1
    assert diagnostics["https://glints.com/listing"]["target_links"] == 1
