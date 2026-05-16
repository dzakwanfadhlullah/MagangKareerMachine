"""Fetcher — ambil dan ekstrak teks dari halaman web publik.

Optimisasi:
- Concurrent fetching via ThreadPoolExecutor
- Skip trafilatura untuk platform known (pakai BS4 langsung)
- Configurable timeout dan workers
"""

import json
import os
import re
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
PLAYWRIGHT_DETAIL_PLATFORMS = {"glints", "jobstreet"}
PLAYWRIGHT_LISTING_PLATFORMS = {"jobstreet"}
PLAYWRIGHT_PLATFORMS = PLAYWRIGHT_DETAIL_PLATFORMS | PLAYWRIGHT_LISTING_PLATFORMS

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


def is_blocked_text(text: str) -> bool:
    text_lower = text.lower()
    return any(signal in text_lower for signal in SKIP_SIGNALS)


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


def _collect_json_strings(value, output: list[str]) -> None:
    """Collect readable text from embedded structured job data."""
    if isinstance(value, dict):
        for child in value.values():
            _collect_json_strings(child, output)
    elif isinstance(value, list):
        for item in value:
            _collect_json_strings(item, output)
    elif isinstance(value, str):
        text = re.sub(r"<[^>]+>", " ", value)
        text = re.sub(r"\s+", " ", text).strip()
        if 3 <= len(text) <= 2000:
            output.append(text)


def extract_structured_text(html: str) -> str:
    """Extract useful strings from JSON-LD and Next.js app state scripts."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        chunks: list[str] = []

        for script in soup.find_all("script"):
            script_id = script.get("id", "")
            script_type = script.get("type", "")
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            if script_type != "application/ld+json" and script_id != "__NEXT_DATA__":
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            _collect_json_strings(data, chunks)

        seen = set()
        unique = []
        for chunk in chunks:
            key = chunk.lower()
            if key not in seen:
                seen.add(key)
                unique.append(chunk)
        return "\n".join(unique)
    except Exception:
        return ""


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


def fetch_rendered_html(url: str, wait_ms: int = 3000) -> Optional[str]:
    """Render a JS-heavy page with Playwright and return final HTML."""
    try:
        from playwright.sync_api import sync_playwright

        console.print(f"  [magenta][PW][/magenta] Rendering JS page: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        console.print(f"  [red][PW ERR][/red] Detail render failed for {url}: {e}")
        return None


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[RawPage]:
    """
    Fetch satu halaman web.
    Known platforms: langsung BS4 (cepat).
    Unknown platforms: trafilatura fallback (thorough).
    """
    if is_binary_url(url):
        return None

    for attempt in range(2):
        try:
            request_timeout = timeout if attempt == 0 else min(timeout * 2, 30)
            response = requests.get(url, headers=HEADERS, timeout=request_timeout, allow_redirects=True)

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            html = response.text
            status_code = response.status_code
            title = extract_title_bs4(html)
            platform = detect_platform(url)
            page_type = classify_page(url, title or "")
            fetch_method = "requests"

            needs_listing_render = platform in PLAYWRIGHT_LISTING_PLATFORMS and page_type == "listing"
            needs_detail_render = platform in PLAYWRIGHT_DETAIL_PLATFORMS and page_type == "detail"
            if needs_listing_render or needs_detail_render:
                rendered_html = fetch_rendered_html(url)
                if rendered_html:
                    html = rendered_html
                    status_code = 200
                    title = extract_title_bs4(html) or title
                    fetch_method = "playwright"

            # Known platforms: BS4 saja (cepat, 3-5x lebih cepat dari trafilatura)
            if platform in KNOWN_PLATFORMS:
                text = extract_text_bs4(html)
            else:
                # Generic: trafilatura first, fallback BS4
                text = extract_text_trafilatura(html, url)
                if not text:
                    text = extract_text_bs4(html)

            structured_text = extract_structured_text(html)
            if structured_text:
                text = f"{text or ''}\n{structured_text}".strip()
            if not text:
                text = ""

            page_type = classify_page(url, title or "")
            allow_short_spa_listing = (
                platform in PLAYWRIGHT_PLATFORMS
                and page_type == "listing"
                and len(html) > 1000
                and not is_blocked_text(text)
                and status_code not in [401, 403, 429]
            )

            is_bad, reason = is_bad_page(title or "", text, status_code)
            if is_bad and not allow_short_spa_listing:
                return None
            if allow_short_spa_listing and len(text.strip()) < 200:
                text = f"{title or platform} listing page\n{text}".strip()

            return RawPage(
                url=url,
                title=title,
                text_content=text[:50000],
                html_content=html,
                status_code=status_code,
                page_type=page_type,
                source_platform=platform,
                fetch_method=fetch_method,
            )

        except (requests.Timeout, requests.RequestException):
            continue

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
