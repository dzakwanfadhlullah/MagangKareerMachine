"""Tests for JSON/API discovery extraction."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.discovery import extract_detail_links_from_json_data, extract_detail_links_from_json_text


def test_extracts_direct_glints_url_from_json_text():
    body = """
    {
      "data": {
        "jobs": [
          {
            "title": "Pricing & Valuation Internship (Actuary)",
            "url": "https://glints.com/id/opportunities/jobs/pricing-and-valuation-internship-actuary/abc-123"
          }
        ]
      }
    }
    """
    links = extract_detail_links_from_json_text(
        "https://glints.com/id/en/find-jobs/loker-magang-internship",
        body,
        platform="glints",
    )
    assert len(links) == 1
    assert links[0].discovery_method == "api"
    assert "pricing-and-valuation-internship-actuary" in links[0].url


def test_infers_jobstreet_url_from_job_object():
    data = {
        "results": [
            {
                "jobId": 123456,
                "jobTitle": "Actuarial Intern",
                "companyName": "Insurance Co",
            }
        ]
    }
    links = extract_detail_links_from_json_data(
        "https://www.jobstreet.co.id/id/actuarial-internship-jobs",
        data,
        platform="jobstreet",
    )
    assert len(links) == 1
    assert links[0].url == "https://www.jobstreet.co.id/id/job/actuarial-intern-123456"
    assert links[0].title == "Actuarial Intern"
    assert links[0].company == "Insurance Co"


def test_infers_glints_url_from_slug_and_id():
    data = {
        "job": {
            "id": "ba7ee3f7-a31c-4b9e-959c-6d745a7eda11",
            "slug": "pricing-and-valuation-internship-actuary",
            "title": "Pricing & Valuation Internship (Actuary)",
            "companyName": "PT Maskapai Reasuransi Indonesia Tbk.",
        }
    }
    links = extract_detail_links_from_json_data(
        "https://glints.com/id/en/find-jobs/loker-actuarial-internship",
        data,
        platform="glints",
    )
    assert len(links) == 1
    assert links[0].url.endswith("/pricing-and-valuation-internship-actuary/ba7ee3f7-a31c-4b9e-959c-6d745a7eda11")
    assert links[0].title == "Pricing & Valuation Internship (Actuary)"


def test_dedupes_repeated_json_urls():
    url = "https://glints.com/id/opportunities/jobs/actuarial-intern/abc"
    data = {"a": url, "b": [{"url": url, "title": "Actuarial Intern"}]}
    links = extract_detail_links_from_json_data(
        "https://glints.com/id/en/find-jobs/loker-actuarial-internship",
        data,
        platform="glints",
    )
    assert len(links) == 1
