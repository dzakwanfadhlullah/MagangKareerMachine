"""Fetcher — ambil dan ekstrak teks dari halaman web publik.

Optimisasi:
- Concurrent fetching via ThreadPoolExecutor
- Skip trafilatura untuk platform known (pakai BS4 langsung)
- Configurable timeout dan workers
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse

import requests
from rich.console import Console

from engine.models import RawSearchResult, RawPage
from engine.listing_parser import classify_page, detect_platform

console = Console()

DEFAULT_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "10"))
DEFAULT_WORKERS = int(os.getenv("FETCH_WORKERS", "5"))

# Platform yang HTML-nya bisa langsung di-parse BS4 tanpa trafilatura
KNOWN_PLATFORMS = {"dealls", "glints", "kalibrr", "jobstreet"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

BINARY_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".png", ".jpg", ".jpeg", ".gif", ".mp4"}
SKIP_SIGNALS = ["captcha", "recaptcha", "verify you are human", "access denied"]
LOGIN_SIGNALS = ["login", "sign in", "log in", "masuk"]


def is_binary_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in BINARY_EXTENSIONS)


def is_bad_page(title: str, text: str, status_code: int) -> tuple[bool, str]:
    text_lower = text.lower()
    title_lower = (title or "").lower()

    if status_code in [401, 403, 429]:
        return True, f"HTTP {status_code}"
    for signal in SKIP_SIGNALS:
        if signal in text_lower:
            return True, f"Skip signal: {signal}"
    for signal in LOGIN_SIGNALS:
        if signal in title_lower and len(text) < 1000:
            return True, f"Login page: {signal}"
    if len(text.strip()) < 200:
        return True, "Content too short"
    return False, ""


def extract_text_bs4(html: str) -> Optional[str]:
    """Ekstrak teks dari HTML menggunakan BeautifulSoup (cepat)."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return None


def extract_text_trafilatura(html: str, url: str) -> Optional[str]:
    """Ekstrak teks bersih — hanya untuk generic/unknown platforms."""
    try:
        import trafilatura
        return trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    except Exception:
        return None


def extract_title_bs4(html: str) -> Optional[str]:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)
        return None
    except Exception:
        return None


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[RawPage]:
    """
    Fetch satu halaman web.
    Known platforms: langsung BS4 (cepat).
    Unknown platforms: trafilatura fallback (thorough).
    """
    if is_binary_url(url):
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        html = response.text
        status_code = response.status_code
        title = extract_title_bs4(html)
        platform = detect_platform(url)

        # Known platforms: BS4 saja (cepat, 3-5x lebih cepat dari trafilatura)
        if platform in KNOWN_PLATFORMS:
            text = extract_text_bs4(html)
        else:
            # Generic: trafilatura first, fallback BS4
            text = extract_text_trafilatura(html, url)
            if not text:
                text = extract_text_bs4(html)

        if not text:
            text = ""

        is_bad, reason = is_bad_page(title or "", text, status_code)
        if is_bad:
            return None

        page_type = classify_page(url, title or "")

        return RawPage(
            url=url,
            title=title,
            text_content=text[:50000],
            html_content=html,
            status_code=status_code,
            page_type=page_type,
            source_platform=platform,
        )

    except requests.Timeout:
        return None
    except requests.RequestException:
        return None


def fetch_all(
    results: list[RawSearchResult],
    existing_urls: Optional[set[str]] = None,
    workers: int = DEFAULT_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[RawPage]:
    """Fetch semua URL — concurrent dengan ThreadPoolExecutor."""
    existing = existing_urls or set()
    urls_to_fetch = []

    for result in results:
        if result.url not in existing:
            urls_to_fetch.append(result.url)

    if not urls_to_fetch:
        console.print(f"[green][OK][/green] All {len(results)} URLs already fetched")
        return []

    total = len(urls_to_fetch)
    console.print(f"  Fetching {total} pages with {workers} workers...")

    pages = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(fetch_page, url, timeout): url
            for url in urls_to_fetch
        }

        done_count = 0
        for future in as_completed(future_map):
            done_count += 1
            url = future_map[future]
            try:
                page = future.result()
                if page:
                    pages.append(page)
            except Exception:
                pass

            if done_count % 10 == 0 or done_count == total:
                console.print(f"  [dim]Progress: {done_count}/{total} done, {len(pages)} OK[/dim]")

    console.print(f"[green][OK][/green] Fetched {len(pages)} pages from {total} URLs")
    return pages


def fetch_detail_urls(
    urls: list[str],
    existing_urls: Optional[set[str]] = None,
    workers: int = DEFAULT_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[RawPage]:
    """Fetch detail URLs — concurrent, force page_type=detail."""
    existing = existing_urls or set()
    to_fetch = [u for u in urls if u not in existing]

    if not to_fetch:
        console.print(f"[green][OK][/green] All {len(urls)} detail URLs already fetched")
        return []

    total = len(to_fetch)
    console.print(f"  Fetching {total} detail pages with {workers} workers...")

    pages = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(fetch_page, url, timeout): url
            for url in to_fetch
        }

        done_count = 0
        for future in as_completed(future_map):
            done_count += 1
            url = future_map[future]
            try:
                page = future.result()
                if page:
                    page.page_type = "detail"
                    pages.append(page)
            except Exception:
                pass

            if done_count % 10 == 0 or done_count == total:
                console.print(f"  [dim]Progress: {done_count}/{total} done, {len(pages)} OK[/dim]")

    console.print(f"[green][OK][/green] Fetched {len(pages)} detail pages from {total} URLs")
    return pages
