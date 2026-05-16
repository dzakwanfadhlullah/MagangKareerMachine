"""Tests for research page verification."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawPage
from engine.research.page_verifier import verify_research_page


def test_research_page_verifier_rejects_aggregator_listing_text():
    page = RawPage(
        url="https://id.linkedin.com/jobs/internship-back-end-developer-jobs",
        title="5 pekerjaan Internship Back End Developer di Indonesia",
        text_content="Dapatkan pemberitahuan pekerjaan Internship Back End Developer baru di Indonesia.",
        status_code=200,
        page_type="unknown",
        source_platform="linkedin",
    )

    rejection = verify_research_page(page)

    assert rejection is not None
    assert rejection.rejection_reason == "listing_or_category_url"


def test_research_page_verifier_allows_direct_job_detail():
    page = RawPage(
        url="https://id.linkedin.com/jobs/view/back-end-developer-intern-at-zettabyte-pte-ltd-4415300468",
        title="Back End Developer Intern",
        text_content="Back End Developer Intern role for students.",
        status_code=200,
        page_type="detail",
        source_platform="linkedin",
    )

    assert verify_research_page(page) is None
