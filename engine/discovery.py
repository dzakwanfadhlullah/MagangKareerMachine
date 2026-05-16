"""Discovery helpers for extracting job detail candidates from JSON/API data."""

import json
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from engine.listing_parser import detect_platform, is_listing_url
from engine.models import DetailLink, RawApiResponse


TITLE_KEYS = {
    "title", "jobtitle", "job_title", "name", "position", "positiontitle",
    "position_title", "role", "headline",
}
COMPANY_KEYS = {
    "company", "companyname", "company_name", "employer", "employername",
    "organization", "hiringorganization",
}
URL_KEYS = {"url", "href", "joburl", "job_url", "absoluteurl", "absolute_url", "weburl", "web_url"}
ID_KEYS = {"id", "jobid", "job_id", "jobadid", "job_ad_id", "uuid"}
SLUG_KEYS = {"slug", "jobslug", "job_slug"}
COMPANY_SLUG_KEYS = {"companyslug", "company_slug", "company", "companyname", "company_name"}

DETAIL_URL_PATTERNS = [
    r"https?://(?:www\.)?glints\.com/[^\s\"'<>]*?/opportunities/jobs/[^\s\"'<>]+",
    r"/(?:id/)?(?:en/)?opportunities/jobs/[^\s\"'<>]+",
    r"https?://(?:www\.)?jobstreet\.co\.id/[^\s\"'<>]*?/job/[^\s\"'<>]+",
    r"/id/job/[^\s\"'<>]+",
    r"/job/[0-9][^\s\"'<>]*",
    r"https?://(?:www\.)?kalibrr\.id/[^\s\"'<>]*?/c/[^/]+/jobs/\d+/[^\s\"'<>]+",
    r"/id-ID/c/[^/]+/jobs/\d+/[^\s\"'<>]+",
    r"https?://dealls\.com/loker/[a-z0-9][^\s\"'<>]*~[^\s\"'<>]+",
    r"/loker/[a-z0-9][^\s\"'<>]*~[^\s\"'<>]+",
    r"https?://(?:id\.)?prosple\.com/[^\s\"'<>]*?(?:jobs-internships|graduate-jobs-internships|/job/)[^\s\"'<>]+",
    r"/[^\s\"'<>]*?(?:jobs-internships|graduate-jobs-internships|job)/[^\s\"'<>]+",
]


def _norm_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _clean_url(value: str) -> str:
    return value.strip().strip("\\\"'<>),;]")


def _textify(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text if text else None
    return None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:120]


def _platform_base(platform: str) -> str:
    return {
        "glints": "https://glints.com",
        "jobstreet": "https://www.jobstreet.co.id",
        "kalibrr": "https://www.kalibrr.id",
        "dealls": "https://dealls.com",
        "prosple": "https://id.prosple.com",
        "indeed": "https://id.indeed.com",
    }.get(platform, "")


def _find_direct_urls(text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    normalized = text.replace("\\/", "/")
    for pattern in DETAIL_URL_PATTERNS:
        for match in re.finditer(pattern, normalized, re.IGNORECASE):
            url = urljoin(base_url, _clean_url(match.group(0)))
            if url in seen or is_listing_url(url):
                continue
            seen.add(url)
            urls.append(url)
    return urls


def _walk_values(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


def _dict_text(data: dict, keys: set[str]) -> Optional[str]:
    for key, value in data.items():
        if _norm_key(key) in keys:
            text = _textify(value)
            if text:
                return text
    return None


def _infer_url_from_object(data: dict, platform: str, base_url: str) -> Optional[str]:
    explicit_url = _dict_text(data, URL_KEYS)
    if explicit_url:
        for url in _find_direct_urls(explicit_url, base_url):
            return url
        parsed = urlparse(explicit_url)
        if parsed.scheme and parsed.netloc and not is_listing_url(explicit_url):
            return explicit_url

    title = _dict_text(data, TITLE_KEYS)
    slug = _dict_text(data, SLUG_KEYS)
    job_id = _dict_text(data, ID_KEYS)
    company_slug = _dict_text(data, COMPANY_SLUG_KEYS)

    if platform == "glints" and slug and job_id:
        return urljoin(base_url, f"/id/opportunities/jobs/{slug}/{job_id}")

    if platform == "jobstreet" and job_id:
        if title:
            return urljoin(base_url, f"/id/job/{_slugify(title)}-{job_id}")
        return urljoin(base_url, f"/id/job/{job_id}")

    if platform == "kalibrr" and job_id and (slug or title) and company_slug:
        return urljoin(base_url, f"/id-ID/c/{_slugify(company_slug)}/jobs/{job_id}/{slug or _slugify(title or '')}")

    return None


def _link_from_url(url: str, listing_url: str, platform: str, title: Optional[str] = None, company: Optional[str] = None) -> Optional[DetailLink]:
    if not url or is_listing_url(url):
        return None
    link_platform = platform or detect_platform(url)
    return DetailLink(
        url=url,
        title=title,
        company=company,
        source_platform=link_platform,
        listing_url=listing_url,
        discovery_method="api",
    )


def extract_detail_links_from_json_data(
    listing_url: str,
    data: Any,
    platform: Optional[str] = None,
) -> list[DetailLink]:
    """Extract DetailLink candidates from parsed API/app-state JSON."""
    source_platform = platform or detect_platform(listing_url)
    base_url = _platform_base(source_platform) or listing_url
    links: list[DetailLink] = []
    seen: set[str] = set()

    for value in _walk_values(data):
        if isinstance(value, str):
            for url in _find_direct_urls(value, base_url):
                if url in seen:
                    continue
                link = _link_from_url(url, listing_url, source_platform)
                if link:
                    seen.add(url)
                    links.append(link)
            continue

        if not isinstance(value, dict):
            continue

        title = _dict_text(value, TITLE_KEYS)
        company = _dict_text(value, COMPANY_KEYS)
        inferred_url = _infer_url_from_object(value, source_platform, base_url)
        if inferred_url and inferred_url not in seen:
            link = _link_from_url(inferred_url, listing_url, source_platform, title=title, company=company)
            if link:
                seen.add(inferred_url)
                links.append(link)

    return links


def extract_detail_links_from_json_text(
    listing_url: str,
    text: str,
    platform: Optional[str] = None,
) -> list[DetailLink]:
    """Parse JSON text and extract job detail links."""
    if not text or len(text.strip()) < 2:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return extract_detail_links_from_json_data(listing_url, data, platform=platform)


def raw_api_response_from_capture(
    listing_url: str,
    response_url: str,
    body: str,
    platform: Optional[str] = None,
    status_code: int = 0,
    content_type: Optional[str] = None,
) -> RawApiResponse:
    """Build a compact RawApiResponse model from a captured response."""
    return RawApiResponse(
        listing_url=listing_url,
        response_url=response_url,
        source_platform=platform or detect_platform(listing_url),
        status_code=status_code,
        content_type=content_type,
        body=body,
    )
