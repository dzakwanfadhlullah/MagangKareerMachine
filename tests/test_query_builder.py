"""Tests for query expansion."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.query_builder import build_queries_from_raw


def test_actuarial_target_expands_query_terms_and_site_queries():
    queries = build_queries_from_raw("actuarial internship", "Indonesia", target_category="actuarial")

    assert any("magang aktuaria" in query for query in queries)
    assert any("pricing valuation internship" in query for query in queries)
    assert any("reinsurance internship" in query for query in queries)
    assert any(query.startswith("site:glints.com/id/opportunities/jobs") for query in queries)
    assert any(query.startswith("site:jobstreet.co.id") for query in queries)
    assert queries[:4] == [
        '"actuarial internship" "Indonesia"',
        '"actuarial intern" "Indonesia"',
        '"actuary internship" "Indonesia"',
        '"actuary intern" "Indonesia"',
    ]
    assert len(queries) == len(set(queries))


def test_generic_query_keeps_default_expansion():
    queries = build_queries_from_raw("frontend developer", "Indonesia")

    assert queries[0] == '"frontend developer" "Indonesia"'
    assert any("frontend developer internship" in query for query in queries)
