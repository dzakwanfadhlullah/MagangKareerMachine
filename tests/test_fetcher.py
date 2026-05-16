"""Tests for fetcher extraction helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.fetcher import extract_structured_text, is_bad_page
from engine.listing_parser import extract_detail_links_from_listing


def test_extract_structured_text_json_ld():
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@type": "JobPosting",
        "title": "Software Engineer Intern",
        "description": "Program magang software engineer. Python, API, SQL.",
        "hiringOrganization": {"name": "PT Example"}
      }
      </script>
    </head><body></body></html>
    """
    text = extract_structured_text(html)
    assert "Software Engineer Intern" in text
    assert "Program magang software engineer" in text
    assert "PT Example" in text
    print("[PASS] JSON-LD structured text extraction")


def test_extract_structured_text_next_data():
    html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "job": {
              "title": "Data Analyst Intern",
              "description": "Internship SQL dashboard reporting"
            }
          }
        }
      }
      </script>
    </body></html>
    """
    text = extract_structured_text(html)
    assert "Data Analyst Intern" in text
    assert "Internship SQL dashboard reporting" in text
    print("[PASS] __NEXT_DATA__ structured text extraction")


def test_spa_listing_falls_back_to_playwright(monkeypatch):
    rendered = """
    <html><body>
        <a href="/id/en/opportunities/jobs/frontend-dev/abc123">Frontend Dev</a>
    </body></html>
    """

    def fake_fetch(url):
        return rendered

    monkeypatch.setattr("engine.listing_parser.fetch_with_playwright", fake_fetch)
    links = extract_detail_links_from_listing(
        "https://glints.com/id/en/find-jobs/loker-front-end-developer-internship",
        "<html><body>No rendered cards yet</body></html>",
    )
    assert len(links) == 1
    assert links[0].url.endswith("/id/en/opportunities/jobs/frontend-dev/abc123")
    print("[PASS] SPA listing fallback to Playwright")


def test_short_page_is_bad_by_default():
    is_bad, reason = is_bad_page("Short", "tiny", 200)
    assert is_bad is True
    assert reason == "Content too short"
    print("[PASS] short page remains bad by default")


def test_late_access_denied_text_does_not_block_valid_page():
    text = "Valid internship listing content " * 80 + " access denied "
    is_bad, reason = is_bad_page("Internship Jobs", text, 200)
    assert is_bad is False
    print("[PASS] late access denied app-state text ignored")
