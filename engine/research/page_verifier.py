"""Page-level verification helpers for research mode."""

import re
from typing import Optional

from engine.extractor import build_rejected_candidate
from engine.listing_parser import is_listing_title, is_listing_url
from engine.models import RawPage, RejectedCandidate

CLOSED_PATTERNS = [
    r"\bclosed\b",
    r"\bexpired\b",
    r"\bno longer accepting\b",
    r"\bnot accepting applications\b",
    r"\bjob is no longer available\b",
    r"\blowongan ditutup\b",
    r"\bditutup\b",
    r"\bkadaluarsa\b",
    r"\btidak menerima lamaran\b",
]


def detect_closed_page(page: RawPage) -> bool:
    """Detect closed/expired job pages from title and primary text."""
    text = f"{page.title or ''}\n{(page.text_content or '')[:4000]}".lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in CLOSED_PATTERNS)


def verify_research_page(page: RawPage) -> Optional[RejectedCandidate]:
    """Return a rejection if a fetched research page should not be extracted."""
    title = page.title or ""
    if page.page_type == "listing" or is_listing_url(page.url) or is_listing_title(title):
        return build_rejected_candidate(page, "listing_or_category_url", title=title)
    if detect_closed_page(page):
        return build_rejected_candidate(page, "closed", title=title, text=page.text_content)
    return None
