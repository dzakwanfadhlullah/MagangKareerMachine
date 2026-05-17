"""URL utilities shared by discovery, extraction, dedupe, and validation."""

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_referrer",
    "traceinfo",
    "fbclid",
    "gclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
}


def canonicalize_url(url: str) -> str:
    """Remove fragments and common tracking params while preserving useful query."""
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw

    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path

    if "jobstreet.co.id" in netloc or "jobstreet.com" in netloc:
        match = re.search(r"/(?:id/)?job/(\d+)", path)
        if match:
            return urlunparse(("https", "www.jobstreet.co.id", f"/job/{match.group(1)}", "", "", ""))

    kept_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunparse((
        parsed.scheme.lower(),
        netloc,
        path,
        "",
        urlencode(kept_query),
        "",
    ))


def has_tracking_params(url: str) -> bool:
    """Return True if URL still contains known tracking params/fragments."""
    parsed = urlparse(url or "")
    if parsed.fragment:
        return True
    return any(key.lower() in TRACKING_PARAMS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))
