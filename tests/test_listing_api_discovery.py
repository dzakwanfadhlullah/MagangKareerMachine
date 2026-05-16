"""Tests for listing parser API-response discovery fallback."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.listing_parser import extract_detail_links_from_listing


def test_glints_listing_extracts_embedded_api_response_links():
    body = {
        "data": {
            "jobs": [{
                "id": "ba7ee3f7-a31c-4b9e-959c-6d745a7eda11",
                "slug": "pricing-and-valuation-internship-actuary",
                "title": "Pricing & Valuation Internship (Actuary)",
                "companyName": "PT Maskapai Reasuransi Indonesia Tbk.",
            }]
        }
    }
    html = (
        "<html><body>"
        f"<script type='application/json' data-api-response='true'>{json.dumps(body)}</script>"
        "</body></html>"
    )

    links = extract_detail_links_from_listing(
        "https://glints.com/id/en/find-jobs/loker-actuarial-internship",
        html,
    )

    assert len(links) == 1
    assert links[0].discovery_method == "api"
    assert "pricing-and-valuation-internship-actuary" in links[0].url


def test_jobstreet_listing_extracts_embedded_api_response_links():
    body = {"jobs": [{"jobId": 123456, "jobTitle": "Actuarial Intern", "companyName": "Insurance Co"}]}
    html = (
        "<html><body>"
        f"<script type='application/json' data-api-response='true'>{json.dumps(body)}</script>"
        "</body></html>"
    )

    links = extract_detail_links_from_listing(
        "https://www.jobstreet.co.id/id/actuarial-internship-jobs",
        html,
    )

    assert len(links) == 1
    assert links[0].discovery_method == "api"
    assert links[0].url == "https://www.jobstreet.co.id/id/job/actuarial-intern-123456"
