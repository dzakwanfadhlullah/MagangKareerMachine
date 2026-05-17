"""Tests for fast research pipeline integration."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import get_all_opportunities, get_discovery_candidates, get_rejected_candidates
from engine.models import RawSearchResult
from engine.research.page_verifier import detect_closed_page, verify_research_page
from engine.research.research_pipeline import (
    _build_jobstreet_card_fallback_page,
    _detail_links_to_search_results,
    _seed_research_results,
    _select_followup_results_with_quota,
    run_research_pipeline,
)
from engine.models import DetailLink, RawPage


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


class EmptyProvider:
    name = "empty"

    def search(self, query: str, max_results: int):
        return []


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
    metadata = json.loads((export_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["accepted_by_platform"] == {"generic": 1}
    assert metadata["source_diversity_warning"] is True
    assert metadata["accepted_results"] == 1


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


def test_research_pipeline_saves_canonical_url_and_original_url(monkeypatch, tmp_path):
    db_path = str(tmp_path / "research_url.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.exporter.EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.research.research_pipeline.export_all.__globals__['EXPORT_DIR']", str(export_dir), raising=False)

    raw_url = (
        "https://glints.com/id/opportunities/jobs/frontend-developer-intern/abc"
        "?utm_referrer=explore&traceInfo=123"
    )

    def fake_fetch_all(results, existing_urls=None, workers=1, timeout=10):
        return [
            RawPage(
                url=raw_url,
                title="Frontend Developer Intern",
                text_content="Frontend Developer Intern. Internship React role. Program magang mahasiswa. Jakarta.",
                status_code=200,
                page_type="detail",
                source_platform="glints",
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
    opportunity = get_all_opportunities(db_path)[0]
    assert opportunity["source_url"] == "https://glints.com/id/opportunities/jobs/frontend-developer-intern/abc"
    assert opportunity["detail_url"] == "https://glints.com/id/opportunities/jobs/frontend-developer-intern/abc"
    assert opportunity["original_url"] == raw_url


def test_followup_selection_keeps_platform_quota():
    results = []
    for idx in range(12):
        results.append(RawSearchResult(
            query="q",
            title=f"Frontend Developer Intern {idx}",
            snippet="internship React",
            url=f"https://glints.com/id/opportunities/jobs/frontend-developer-intern/{idx}",
            source="test",
            page_type="detail",
            source_platform="glints",
        ))
    for idx in range(6):
        results.append(RawSearchResult(
            query="q",
            title=f"Backend Developer Internship {idx}",
            snippet="internship backend",
            url=f"https://www.jobstreet.co.id/job/{9000 + idx}",
            source="test",
            page_type="detail",
            source_platform="jobstreet",
        ))

    selected = _select_followup_results_with_quota(results, target_category="tech", max_urls=8)
    platforms = [result.source_platform for result in selected]

    assert len(selected) == 8
    assert platforms.count("jobstreet") >= 3
    assert platforms.count("glints") >= 3


def test_jobstreet_card_fallback_requires_internship_title():
    good = RawSearchResult(
        query="listing-followup:https://id.jobstreet.com/web-developer-internship-jobs",
        title="Software Engineer Internship",
        snippet="Company: OPPO Indonesia",
        url="https://www.jobstreet.co.id/job/91761487?type=standard",
        source="card",
        page_type="detail",
        source_platform="jobstreet",
    )
    page = _build_jobstreet_card_fallback_page(good)
    assert page is not None
    assert page.title == "Software Engineer Internship"
    assert "Company: OPPO Indonesia" in page.text_content

    bad = good.model_copy(update={"title": "Full Stack Developer"})
    assert _build_jobstreet_card_fallback_page(bad) is None


def test_followup_conversion_prefers_richer_jobstreet_card_metadata():
    links = [
        DetailLink(
            url="https://www.jobstreet.co.id/job/91761487?type=standard&origin=cardTitle",
            title=None,
            company=None,
            source_platform="jobstreet",
            listing_url="listing",
            discovery_method="script",
        ),
        DetailLink(
            url="https://www.jobstreet.co.id/id/job/91761487?type=standard&origin=cardTitle",
            title="Software Engineer Internship",
            company="OPPO Indonesia",
            source_platform="jobstreet",
            listing_url="listing",
            discovery_method="card",
        ),
    ]
    results = _detail_links_to_search_results(links)
    assert len(results) == 1
    assert results[0].title == "Software Engineer Internship"
    assert "Company: OPPO Indonesia" in (results[0].snippet or "")


def test_research_seeds_include_dealls_kalibrr_and_prosple_for_tech():
    seeds = _seed_research_results(
        query="frontend backend fullstack software engineer internship",
        location="Indonesia",
        target_category="tech",
    )
    platforms = {seed.source_platform for seed in seeds}

    assert {"dealls", "kalibrr", "prosple"}.issubset(platforms)
    assert all(seed.page_type == "listing" for seed in seeds)


def test_research_pipeline_uses_seed_urls_when_search_index_empty(monkeypatch, tmp_path):
    db_path = str(tmp_path / "research_seed_fallback.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.exporter.EXPORT_DIR", str(export_dir))
    monkeypatch.setattr("engine.research.research_pipeline.export_all.__globals__['EXPORT_DIR']", str(export_dir), raising=False)

    seen_platforms = set()

    def fake_fetch_all(results, existing_urls=None, workers=1, timeout=10):
        seen_platforms.update(result.source_platform for result in results)
        return []

    monkeypatch.setattr("engine.research.research_pipeline.fetch_all", fake_fetch_all)

    saved = run_research_pipeline(
        query="frontend backend fullstack software engineer internship",
        location="Indonesia",
        target_category="tech",
        profile="fast",
        query_count=1,
        max_fetch=5,
        workers=1,
        timeout=1,
        provider=EmptyProvider(),
    )

    assert saved == 0
    assert {"dealls", "kalibrr", "prosple"}.issubset(seen_platforms)
    metadata = json.loads((export_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert {"dealls", "kalibrr", "prosple"}.issubset(set(metadata["platforms_seeded"]))
