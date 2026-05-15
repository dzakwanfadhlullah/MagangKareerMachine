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


class RawPage(BaseModel):
    """Konten halaman yang sudah di-fetch."""

    url: str
    title: Optional[str] = None
    text_content: str
    status_code: int


class Opportunity(BaseModel):
    """Lowongan magang yang sudah dinormalisasi."""

    title: str
    company: Optional[str] = None
    role: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None  # remote | hybrid | onsite
    duration: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[str] = None
    source_url: str
    source_name: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    score: int = 0
    confidence: int = 0
    canonical_key: Optional[str] = None
