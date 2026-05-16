"""Tests for discovery audit storage."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import (
    get_connection,
    get_discovery_candidates,
    init_db,
    reset_db,
    save_crawl_queue,
    save_discovery_candidates,
    save_raw_api_responses,
)


def test_discovery_tables_and_queue_metadata(tmp_path):
    db_path = str(tmp_path / "discovery.db")
    init_db(db_path)

    candidates = [{
        "url": "https://glints.com/id/opportunities/jobs/pricing-and-valuation-internship-actuary/1",
        "title": "Pricing & Valuation Internship (Actuary)",
        "source_platform": "glints",
        "listing_url": "https://glints.com/id/en/find-jobs/loker-magang-internship",
        "discovery_method": "api",
        "target_category": "actuarial",
        "target_score": 240,
    }]
    assert save_discovery_candidates(candidates, db_path=db_path) == 1
    rows = get_discovery_candidates(db_path=db_path)
    assert rows[0]["discovery_method"] == "api"
    assert rows[0]["target_score"] == 240

    assert save_crawl_queue(candidates, db_path=db_path) == 1
    conn = get_connection(db_path)
    queued = conn.execute("SELECT discovery_method, target_score FROM crawl_queue").fetchone()
    conn.close()
    assert queued["discovery_method"] == "api"
    assert queued["target_score"] == 240

    responses = [{
        "listing_url": candidates[0]["listing_url"],
        "response_url": "https://api.example.test/jobs",
        "source_platform": "glints",
        "status_code": 200,
        "content_type": "application/json",
        "body": '{"jobs":[]}',
    }]
    assert save_raw_api_responses(responses, db_path=db_path) == 1

    reset_db(db_path)
    assert get_discovery_candidates(db_path=db_path) == []
