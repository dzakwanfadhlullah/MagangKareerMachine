"""Pydantic data models untuk MagangKareer Engine."""

from pydantic import BaseModel, Field
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


class DetailLink(BaseModel):
    """Link detail lowongan yang diekstrak dari halaman listing."""

    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    source_platform: str
    listing_url: str  # Halaman listing asal
    discovery_method: str = "dom"  # dom | script | api | search | manual
    target_score: int = 0


class DiscoveryCandidate(BaseModel):
    """Kandidat detail URL hasil discovery sebelum fetch/extract final."""

    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    source_platform: Optional[str] = None
    listing_url: Optional[str] = None
    discovery_method: str = "unknown"
    target_category: Optional[str] = None
    target_score: int = 0
    status: str = "discovered"  # discovered | queued | fetched | accepted | rejected
    rejection_reason: Optional[str] = None


class RawApiResponse(BaseModel):
    """XHR/fetch JSON response captured while rendering a listing."""

    listing_url: str
    response_url: str
    source_platform: Optional[str] = None
    status_code: int = 0
    content_type: Optional[str] = None
    body: str


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
    api_responses: list[RawApiResponse] = Field(default_factory=list)


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
