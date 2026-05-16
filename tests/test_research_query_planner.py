"""Tests for fast research query planning."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.research.profiles import get_research_profile
from engine.research.query_planner import plan_research_queries, terms_for_target


def test_research_profiles():
    fast = get_research_profile("fast")
    normal = get_research_profile("normal")
    deep = get_research_profile("deep")

    assert fast["max_fetch"] < normal["max_fetch"] < deep["max_fetch"]
    assert normal["query_count"] == 24


def test_tech_target_expands_to_developer_roles():
    terms = terms_for_target("tech", query="frontend backend fullstack intern")

    assert "frontend backend fullstack intern" in terms
    assert "frontend developer intern" in terms
    assert "backend developer intern" in terms
    assert "fullstack developer intern" in terms
    assert "mobile developer intern" in terms


def test_research_queries_include_site_specific_direct_job_queries():
    queries = plan_research_queries(
        query="frontend developer intern",
        location="Indonesia",
        target_category="frontend",
        query_count=20,
    )

    assert queries[0] == '"frontend developer intern" "Indonesia"'
    assert any(query.startswith("site:dealls.com/loker") for query in queries)
    assert any("site:glints.com/id/opportunities/jobs" in query for query in queries)
    assert len(queries) == len(set(queries))
    assert len(queries) <= 20


def test_actuarial_research_queries_include_niche_terms():
    queries = plan_research_queries(target_category="actuarial", location="Indonesia", query_count=30)

    assert any("magang aktuaria" in query for query in queries)
    assert any("reinsurance internship" in query for query in queries)
    assert any("IFRS 17 intern" in query for query in queries)
