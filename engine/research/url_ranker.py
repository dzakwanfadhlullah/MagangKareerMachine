"""URL filtering and ranking for fast research candidates."""

import re
from urllib.parse import urlparse

from engine.extractor import normalize_target_category
from engine.listing_parser import detect_platform, is_listing_url
from engine.models import RawSearchResult

DIRECT_DETAIL_PATTERNS = [
    r"glints\.com/.*/opportunities/jobs/",
    r"dealls\.com/loker/[a-z0-9].*~",
    r"kalibrr\.(?:id|com)/.*/c/.+/jobs/\d+/",
    r"jobstreet\.co\.id/.*/job/",
    r"prosple\.com/.*/(?:jobs-internships|graduate-jobs-internships|job)/",
    r"linkedin\.com/jobs/view/",
    r"indeed\.com/.*/viewjob\?",
    r"loker\.id/.*/lowongan-kerja/",
    r"/careers?/.+",
    r"/jobs?/(?:view/)?\d+",
    r"/jobs?/[a-z0-9][a-z0-9-]+(?:[?#]|$)",
]

BAD_PATH_PATTERNS = [
    r"/blog",
    r"/article",
    r"/tips",
    r"/career-advice",
    r"/course",
    r"/bootcamp",
    r"/kelas",
    r"/login",
    r"/signup",
]

RESEARCH_LISTING_URL_PATTERNS = [
    r"jobstreet\.[^/]+/[^?#]*-jobs(?:[?#]|$)",
    r"linkedin\.com/jobs/(?!view/)[^?#]*-jobs(?:[?#]|$)",
    r"jora\.com/lowongan-[^?#]*-di-[^?#]+",
    r"indeed\.[^/]+/q-[^?#]*lowongan",
    r"/jobs/search",
    r"/jobs/(?:search|collections|people|recommended)",
]

SOURCE_QUALITY = {
    "dealls": 12,
    "glints": 12,
    "kalibrr": 10,
    "jobstreet": 10,
    "prosple": 8,
    "generic": 4,
}


def is_direct_detail_url(url: str) -> bool:
    """Return True if URL looks like a direct job detail page."""
    if not url or is_listing_url(url):
        return False
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in DIRECT_DETAIL_PATTERNS)


def is_bad_research_url(url: str) -> bool:
    """Reject obvious non-job research URLs."""
    if not url:
        return True
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http") or not parsed.netloc:
        return True
    lowered = url.lower()
    if any(re.search(pattern, lowered) for pattern in BAD_PATH_PATTERNS):
        return True
    return any(re.search(pattern, lowered) for pattern in RESEARCH_LISTING_URL_PATTERNS)


def score_research_url(result: RawSearchResult, target_category: str | None = None) -> int:
    """Score raw search result before fetching."""
    if is_bad_research_url(result.url):
        return -100

    platform = result.source_platform or detect_platform(result.url)
    text = f"{result.title} {result.snippet} {result.url}".lower()
    target = normalize_target_category(target_category)

    score = SOURCE_QUALITY.get(platform, 4)
    if is_direct_detail_url(result.url):
        score += 40
    if result.page_type == "detail":
        score += 10
    if any(signal in text for signal in ["intern", "internship", "magang", "trainee", "apprentice"]):
        score += 25
    if target and target in text:
        score += 20
    if target == "tech" and any(signal in text for signal in [
        "frontend", "front-end", "backend", "back-end", "fullstack", "software engineer",
        "software developer", "web developer", "mobile developer",
    ]):
        score += 25
    if target == "actuarial" and any(signal in text for signal in [
        "actuarial", "actuary", "aktuaria", "valuation", "reserving", "reinsurance",
    ]):
        score += 25
    if any(signal in text for signal in ["closed", "ditutup", "expired"]):
        score -= 60
    if is_listing_url(result.url):
        score -= 50
    return score


def rank_research_results(
    results: list[RawSearchResult],
    target_category: str | None = None,
    max_urls: int = 40,
) -> list[RawSearchResult]:
    """Filter, score, and rank search results before limited fetch."""
    scored = []
    for result in results:
        score = score_research_url(result, target_category=target_category)
        if score < 0:
            continue
        result.snippet = f"{result.snippet or ''}\nresearch_url_score={score}".strip()
        scored.append((score, result))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [result for _, result in scored[:max_urls]]
