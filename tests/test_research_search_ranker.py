"""Tests for research search normalization and URL ranking."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawSearchResult
from engine.research.result_normalizer import canonicalize_url, dedupe_results, normalize_search_hit
from engine.research.search_provider import DuckDuckGoProvider, get_search_provider, search_queries_parallel
from engine.research.url_ranker import is_direct_detail_url, rank_research_results, score_research_url


class FakeProvider:
    name = "fake"

    def search(self, query: str, max_results: int):
        return [
            RawSearchResult(
                query=query,
                title="Frontend Developer Intern",
                snippet="React internship",
                url=f"https://glints.com/id/opportunities/jobs/frontend-developer-intern/{query[-1]}?utm_source=x",
                source="fake",
                page_type="detail",
                source_platform="glints",
            )
        ]


def test_canonicalize_and_normalize_search_hit():
    url = "https://glints.com/id/opportunities/jobs/frontend/abc?utm_source=x&foo=1#frag"
    assert canonicalize_url(url) == "https://glints.com/id/opportunities/jobs/frontend/abc?foo=1"

    result = normalize_search_hit(
        {"title": "Frontend Intern", "body": "React", "href": url},
        query="q",
    )
    assert result is not None
    assert result.source_platform == "glints"
    assert result.page_type == "detail"


def test_parallel_search_provider_dedupes_results():
    results = search_queries_parallel(
        ["q1", "q1"],
        provider=FakeProvider(),
        max_results_per_query=5,
        workers=2,
    )

    assert len(results) == 1
    assert results[0].source == "fake"


def test_search_provider_auto_falls_back_to_ddg_without_keys(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    provider = get_search_provider("auto")

    assert isinstance(provider, DuckDuckGoProvider)


def test_url_ranker_prefers_direct_intern_detail():
    direct = RawSearchResult(
        query="q",
        title="Frontend Developer Intern",
        snippet="React internship Indonesia",
        url="https://glints.com/id/opportunities/jobs/frontend-developer-intern/abc",
        source="fake",
        page_type="detail",
        source_platform="glints",
    )
    listing = RawSearchResult(
        query="q",
        title="Lowongan magang",
        snippet="browse jobs",
        url="https://glints.com/id/en/find-jobs/loker-magang-internship",
        source="fake",
        page_type="listing",
        source_platform="glints",
    )

    assert is_direct_detail_url(direct.url)
    assert score_research_url(direct, target_category="tech") > score_research_url(listing, target_category="tech")
    assert rank_research_results([listing, direct], target_category="tech", max_urls=1) == [direct]


def test_url_ranker_rejects_search_result_pages():
    jobstreet_listing = RawSearchResult(
        query="q",
        title="Backend Developer Internship Jobs in Indonesia",
        snippet="41 backend developer internship jobs",
        url="https://id.jobstreet.com/backend-developer-internship-jobs",
        source="fake",
        page_type="unknown",
        source_platform="jobstreet",
    )
    linkedin_listing = RawSearchResult(
        query="q",
        title="5 pekerjaan Internship Back End Developer di Indonesia",
        snippet="Dapatkan pemberitahuan pekerjaan",
        url="https://id.linkedin.com/jobs/internship-back-end-developer-jobs",
        source="fake",
        page_type="unknown",
        source_platform="linkedin",
    )
    linkedin_detail = RawSearchResult(
        query="q",
        title="Back End Developer Intern",
        snippet="Internship",
        url="https://id.linkedin.com/jobs/view/back-end-developer-intern-at-zettabyte-pte-ltd-4415300468",
        source="fake",
        page_type="detail",
        source_platform="linkedin",
    )

    ranked = rank_research_results(
        [jobstreet_listing, linkedin_listing, linkedin_detail],
        target_category="tech",
        max_urls=10,
    )

    assert ranked == [linkedin_detail]
