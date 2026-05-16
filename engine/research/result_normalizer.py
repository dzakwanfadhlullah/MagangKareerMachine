"""Normalize search-index results into RawSearchResult rows."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from engine.listing_parser import classify_page, detect_platform
from engine.models import RawSearchResult

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_referrer", "traceinfo", "traceInfo", "fbclid", "gclid", "msclkid",
}


def canonicalize_url(url: str) -> str:
    """Remove fragments and common tracking params while preserving useful query."""
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    kept_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_PARAMS
    ]
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/") or parsed.path,
        "",
        urlencode(kept_query),
        "",
    ))


def normalize_search_hit(hit: dict, query: str, source: str = "ddgs") -> RawSearchResult | None:
    """Normalize provider-specific hit dictionaries."""
    url = canonicalize_url(hit.get("url") or hit.get("href") or "")
    if not url:
        return None
    title = (hit.get("title") or "").strip()
    snippet = (hit.get("snippet") or hit.get("body") or "").strip()
    platform = detect_platform(url)
    return RawSearchResult(
        query=query,
        title=title,
        snippet=snippet,
        url=url,
        source=source,
        page_type=classify_page(url, title),
        source_platform=platform,
    )


def dedupe_results(results: list[RawSearchResult]) -> list[RawSearchResult]:
    """Dedupe search results by canonical URL while preserving order."""
    seen = set()
    deduped = []
    for result in results:
        url = canonicalize_url(result.url)
        if not url or url in seen:
            continue
        seen.add(url)
        result.url = url
        deduped.append(result)
    return deduped
