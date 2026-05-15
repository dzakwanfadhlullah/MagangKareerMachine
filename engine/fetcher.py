"""Fetcher — ambil dan ekstrak teks dari halaman web publik."""

import os
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from rich.console import Console

from engine.models import RawSearchResult, RawPage

console = Console()

FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "15"))

# User-Agent agar tidak di-block
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Ekstensi file binary yang harus di-skip
BINARY_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".png", ".jpg", ".jpeg", ".gif", ".mp4"}

# Kata kunci halaman yang harus di-skip
SKIP_SIGNALS = ["captcha", "recaptcha", "verify you are human", "access denied"]
LOGIN_SIGNALS = ["login", "sign in", "log in", "masuk"]


def is_binary_url(url: str) -> bool:
    """Cek apakah URL mengarah ke file binary."""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in BINARY_EXTENSIONS)


def is_bad_page(title: str, text: str, status_code: int) -> tuple[bool, str]:
    """
    Cek apakah halaman tidak layak diproses.
    Return (is_bad, reason).
    """
    text_lower = text.lower()
    title_lower = (title or "").lower()

    # Status code buruk
    if status_code in [401, 403, 429]:
        return True, f"HTTP {status_code}"

    # CAPTCHA
    for signal in SKIP_SIGNALS:
        if signal in text_lower:
            return True, f"Skip signal: {signal}"

    # Login page dengan konten pendek
    for signal in LOGIN_SIGNALS:
        if signal in title_lower and len(text) < 1000:
            return True, f"Login page: {signal}"

    # Konten terlalu pendek
    if len(text.strip()) < 200:
        return True, "Content too short"

    return False, ""


def extract_text_trafilatura(html: str, url: str) -> Optional[str]:
    """Ekstrak teks bersih dari HTML menggunakan trafilatura."""
    try:
        import trafilatura
        text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
        return text
    except Exception:
        return None


def extract_text_bs4(html: str) -> Optional[str]:
    """Fallback: ekstrak teks dari HTML menggunakan BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Hapus script dan style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Bersihkan whitespace berlebih
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return None


def extract_title_bs4(html: str) -> Optional[str]:
    """Ekstrak title dari HTML."""
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


def fetch_page(url: str) -> Optional[RawPage]:
    """
    Fetch satu halaman web dan ekstrak teks bersih.

    Strategi:
    1. Skip URL binary
    2. HTTP GET dengan requests
    3. Ekstrak teks dengan trafilatura
    4. Fallback ke BeautifulSoup
    5. Validasi halaman (skip captcha, login, dll)
    """
    # Skip binary URLs
    if is_binary_url(url):
        console.print(f"  [dim]Skip binary: {url}[/dim]")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True)

        # Cek content type
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            console.print(f"  [dim]Skip non-HTML: {url}[/dim]")
            return None

        html = response.text
        status_code = response.status_code

        # Ekstrak title
        title = extract_title_bs4(html)

        # Ekstrak teks: trafilatura first, fallback ke bs4
        text = extract_text_trafilatura(html, url)
        if not text:
            text = extract_text_bs4(html)
        if not text:
            text = ""

        # Validasi halaman
        is_bad, reason = is_bad_page(title or "", text, status_code)
        if is_bad:
            console.print(f"  [dim]Skip ({reason}): {url}[/dim]")
            return None

        return RawPage(
            url=url,
            title=title,
            text_content=text[:50000],  # Limit teks agar tidak terlalu besar
            status_code=status_code,
        )

    except requests.Timeout:
        console.print(f"  [yellow]Timeout: {url}[/yellow]")
        return None
    except requests.RequestException as e:
        console.print(f"  [red]Fetch error: {url} — {e}[/red]")
        return None


def fetch_all(results: list[RawSearchResult], existing_urls: Optional[set[str]] = None) -> list[RawPage]:
    """
    Fetch semua URL dari search results.
    Skip URL yang sudah pernah di-fetch.
    """
    existing = existing_urls or set()
    pages = []
    total = len(results)

    for i, result in enumerate(results, 1):
        # Skip jika sudah pernah di-fetch
        if result.url in existing:
            console.print(f"  [dim]({i}/{total}) Already fetched: {result.url}[/dim]")
            continue

        console.print(f"  [cyan]({i}/{total})[/cyan] Fetching: {result.url}")
        page = fetch_page(result.url)

        if page:
            pages.append(page)

    console.print(f"[green][OK][/green] Fetched {len(pages)} pages from {total} URLs")
    return pages
