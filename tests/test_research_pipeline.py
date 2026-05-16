"""Tests for fast research pipeline integration."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import get_all_opportunities, get_discovery_candidates, get_rejected_candidates
from engine.models import RawSearchResult
from engine.research.page_verifier import detect_closed_page, verify_research_page
from engine.research.research_pipeline import run_research_pipeline
from engine.models import RawPage


class StaticProvider:
    name = "static"

    def search(self, query: str, max_results: int):
        return [
            RawSearchResult(
                query=query,
                title="Frontend Developer Intern",
                snippet="React internship Indonesia",
                url="https://example.com/jobs/frontend-developer-intern",
                source="static",
                page_type="detail",
                source_platform="generic",
            ),
            RawSearchResult(
                query=query,
                title="Career Advice",
                snippet="tips karir",
                url="https://example.com/blog/career-advice",
                source="static",
                page_type="detail",
                source_platform="generic",
            ),
        ]


class ListingProvider:
    name = "listing"

    def search(self, query: str, max_results: int):
        return [
            RawSearchResult(
                query=query,
                title="Frontend Developer Internship Jobs",
                snippet="frontend internship Indonesia",
                url="https://glints.com/id/en/find-jobs/loker-front-end-developer-internship",
                source="listing",
                page_type="listing",
                source_platform="glints",
            )
        ]


def test_page_verifier_rejects_closed_and_listing_pages():
    closed = RawPage(
        url="https://example.com/jobs/frontend",
        title="Frontend Intern",
        text_content="This job is no longer available.",
        status_code=200,
        page_type="detail",
    )
    assert detect_closed_page(closed)
    assert verify_research_page(closed).rejection_reason == "closed"

    listing = RawPage(
        url="https://glints.com/id/en/find-jobs/loker-magang-internship",
        title="Find Jobs",
        text_content="Browse jobs",
        status_code=200,
        page_type="listing",
    )
    assert verify_research_page(listing).rejection_reason == "listing_or_category_url"


def test_research_pipeline_accepts_static_direct_result(monkeypatch, tmp_path):
    db_path = str(tmp_path / "research.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.exporter.EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.research.research_pipeline.export_all.__globals__['EXPORT_DIR']", str(export_dir), raising=False)

    def fake_fetch_all(results, existing_urls=None, workers=1, timeout=10):
        return [
            RawPage(
                url=results[0].url,
                title="Frontend Developer Intern",
                text_content="""
                Frontend Developer Intern
                Internship frontend developer role for React, Next.js, TypeScript.
                Program magang untuk mahasiswa. Lokasi Jakarta.
                """,
                status_code=200,
                page_type="detail",
                source_platform="generic",
                fetch_method="test",
            )
        ]

    monkeypatch.setattr("engine.research.research_pipeline.fetch_all", fake_fetch_all)

    saved = run_research_pipeline(
        query="frontend developer intern",
        location="Indonesia",
        target_category="frontend",
        profile="fast",
        query_count=1,
        max_fetch=1,
        workers=1,
        timeout=1,
        provider=StaticProvider(),
    )

    assert saved == 1
    opportunities = get_all_opportunities(db_path)
    assert opportunities[0]["role"] == "Frontend Developer"
    assert opportunities[0]["category"] == "tech"
    assert get_discovery_candidates(db_path=db_path)
    assert get_rejected_candidates(db_path=db_path) == []


def test_research_pipeline_follows_listing_detail_links(monkeypatch, tmp_path):
    db_path = str(tmp_path / "research_listing.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.exporter.EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.research.research_pipeline.export_all.__globals__['EXPORT_DIR']", str(export_dir), raising=False)

    def fake_fetch_all(results, existing_urls=None, workers=1, timeout=10):
        return [
            RawPage(
                url=results[0].url,
                title="Find Jobs",
                text_content="Browse frontend developer internship jobs",
                html_content='<a href="/id/opportunities/jobs/frontend-developer-intern/abc">Frontend Developer Intern</a>',
                status_code=200,
                page_type="listing",
                source_platform="glints",
                fetch_method="test",
            )
        ]

    def fake_fetch_detail_urls(urls, existing_urls=None, workers=1, timeout=10):
        return [
            RawPage(
                url=urls[0],
                title="Frontend Developer Intern",
                text_content="""
                Frontend Developer Intern
                Internship frontend developer role for React.
                Program magang mahasiswa. Lokasi Jakarta.
                """,
                status_code=200,
                page_type="detail",
                source_platform="glints",
                fetch_method="test",
            )
        ]

    monkeypatch.setattr("engine.research.research_pipeline.fetch_all", fake_fetch_all)
    monkeypatch.setattr("engine.research.research_pipeline.fetch_detail_urls", fake_fetch_detail_urls)

    saved = run_research_pipeline(
        query="frontend developer intern",
        location="Indonesia",
        target_category="frontend",
        profile="fast",
        query_count=1,
        max_fetch=3,
        workers=1,
        timeout=1,
        provider=ListingProvider(),
    )

    assert saved == 1
    opportunities = get_all_opportunities(db_path)
    assert opportunities[0]["source_url"] == "https://glints.com/id/opportunities/jobs/frontend-developer-intern/abc"
    assert get_rejected_candidates(db_path=db_path)[0]["rejection_reason"] == "listing_or_category_url"
