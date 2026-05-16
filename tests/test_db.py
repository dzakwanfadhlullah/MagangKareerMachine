"""Tests for database cache helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import get_raw_pages_by_urls, init_db, save_raw_page


def test_get_raw_pages_by_urls_preserves_input_order(tmp_path):
    db_path = str(tmp_path / "cache.db")
    init_db(db_path)

    save_raw_page(
        {
            "url": "https://example.com/b",
            "title": "B",
            "text_content": "B content",
            "html_content": "<html>B</html>",
            "status_code": 200,
            "page_type": "detail",
            "source_platform": "generic",
        },
        db_path,
    )
    save_raw_page(
        {
            "url": "https://example.com/a",
            "title": "A",
            "text_content": "A content",
            "html_content": "<html>A</html>",
            "status_code": 200,
            "page_type": "listing",
            "source_platform": "generic",
        },
        db_path,
    )

    rows = get_raw_pages_by_urls(
        [
            "https://example.com/a",
            "https://example.com/missing",
            "https://example.com/b",
        ],
        db_path,
    )
    assert [row["url"] for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    print("[PASS] cached raw pages preserve input order")
