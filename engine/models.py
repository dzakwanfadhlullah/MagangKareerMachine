"""Pydantic data models untuk MagangKareer Engine."""

from pydantic import BaseModel, Field
from typing import Any, Optional


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
    company_confidence: int = 0
    role: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    location_area: Optional[str] = None  # jakarta_area, west_java, etc.
    work_mode: Optional[str] = None  # remote | hybrid | onsite
    duration: Optional[str] = None
    salary: Optional[str] = None
    salary_raw: Optional[str] = None
    salary_display: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_confidence: int = 0
    salary_status: str = "not_provided"
    location_status: str = "not_provided"
    duration_status: str = "not_provided"
    deadline_status: str = "not_provided"
    location_confidence: int = 0
    deadline: Optional[str] = None
    source_url: str  # Direct detail URL, bukan listing
    detail_url: Optional[str] = None
    original_url: Optional[str] = None
    source_name: Optional[str] = None
    source_platform: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    score: int = 0
    score_breakdown: Optional[dict[str, Any]] = None
    extraction_depth: str = "full_detail"  # full_detail | listing_card | search_snippet
    verification_level: str = "verified_detail"  # verified_detail | listed_only | search_index_only | unknown
    dashboard_quality: str = "medium"  # high | medium | low
    active_status: str = "unknown"  # active | listed | unknown | closed
    role_family: Optional[str] = None
    role_group: Optional[str] = None
    role_specialization: Optional[str] = None
    mixed_employment_signal: bool = False
    summary_short: Optional[str] = None
    source_platform_label: Optional[str] = None
    apply_url: Optional[str] = None
    display_location: Optional[str] = None
    display_salary: Optional[str] = None
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
