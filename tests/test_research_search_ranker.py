"""Tests for research search normalization and URL ranking."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawSearchResult
from engine.research.result_normalizer import canonicalize_url, dedupe_results, normalize_search_hit
from engine.research.search_provider import search_queries_parallel
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
