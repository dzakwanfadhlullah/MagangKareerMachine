"""Page-level verification helpers for research mode."""

import re
from typing import Optional

from engine.extractor import build_rejected_candidate
from engine.listing_parser import is_listing_title, is_listing_url
from engine.models import RawPage, RejectedCandidate
from engine.research.url_ranker import is_bad_research_url, is_direct_detail_url

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

LISTING_TEXT_PATTERNS = [
    r"\b\d+\s+(?:pekerjaan|jobs?)\b",
    r"\b(?:job|lowongan)\s+search\b",
    r"\blowongan kerja .* indonesia\b",
    r"\bjobs in indonesia\b",
    r"\bshow work arrangement refinements\b",
    r"\bshow classifications refinements\b",
    r"\bdapatkan pemberitahuan pekerjaan\b",
    r"\bkami akan memberi tahu anda jika ada lowongan\b",
]


def detect_closed_page(page: RawPage) -> bool:
    """Detect closed/expired job pages from title and primary text."""
    text = f"{page.title or ''}\n{(page.text_content or '')[:4000]}".lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in CLOSED_PATTERNS)


def detect_listing_page(page: RawPage) -> bool:
    """Detect listing/search pages that slipped through generic page classification."""
    title = page.title or ""
    text = f"{title}\n{(page.text_content or '')[:2500]}".lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in LISTING_TEXT_PATTERNS)


def verify_research_page(page: RawPage) -> Optional[RejectedCandidate]:
    """Return a rejection if a fetched research page should not be extracted."""
    title = page.title or ""
    direct_detail = is_direct_detail_url(page.url)
    if detect_closed_page(page):
        return build_rejected_candidate(page, "closed", title=title, text=page.text_content)
    if (
        page.page_type == "listing"
        or is_listing_url(page.url)
        or is_listing_title(title)
        or is_bad_research_url(page.url)
        or not direct_detail
        or (detect_listing_page(page) and not direct_detail)
    ):
        return build_rejected_candidate(page, "listing_or_category_url", title=title)
    return None
