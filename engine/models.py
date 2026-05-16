"""Pydantic data models untuk MagangKareer Engine."""

from pydantic import BaseModel
from typing import Optional


class RawSearchResult(BaseModel):
    """Hasil pencarian mentah sebelum fetch halaman."""

    query: str
    title: str
    snippet: Optional[str] = None
    url: str
    source: str = "web"
    page_type: str = "unknown"  # listing | detail | unknown
    source_platform: Optional[str] = None  # dealls | glints | jobstreet | kalibrr | ...


class RawPage(BaseModel):
    """Konten halaman yang sudah di-fetch."""

    url: str
    title: Optional[str] = None
    text_content: str
    html_content: str = ""  # Raw HTML untuk listing parser
    status_code: int
    page_type: str = "unknown"  # listing | detail | unknown
    source_platform: Optional[str] = None
    fetch_method: Optional[str] = None  # requests | playwright | cached


class DetailLink(BaseModel):
    """Link detail lowongan yang diekstrak dari halaman listing."""

    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    source_platform: str
    listing_url: str  # Halaman listing asal


class Opportunity(BaseModel):
    """Lowongan magang yang sudah dinormalisasi — hanya dari detail page."""

    title: str
    company: Optional[str] = None
    role: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    location_area: Optional[str] = None  # jakarta_area, west_java, etc.
    work_mode: Optional[str] = None  # remote | hybrid | onsite
    duration: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[str] = None
    source_url: str  # Direct detail URL, bukan listing
    detail_url: Optional[str] = None
    source_name: Optional[str] = None
    source_platform: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    score: int = 0
    confidence: int = 0
    is_internship: bool = False
    internship_confidence: int = 0
    role_confidence: int = 0
    canonical_key: Optional[str] = None
    page_type: str = "detail"
    extraction_status: str = "extracted"  # extracted | rejected
    rejection_reason: Optional[str] = None


class RejectedCandidate(BaseModel):
    """Halaman detail yang ditolak extractor/scorer untuk audit false negatives."""

    url: str
    title: Optional[str] = None
    source_platform: Optional[str] = None
    page_type: str = "detail"
    rejection_reason: str
    internship_confidence: int = 0
    role_confidence: int = 0
    score: int = 0
    text_snippet: Optional[str] = None
