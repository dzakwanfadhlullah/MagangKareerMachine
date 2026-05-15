"""Listing Parser — extract job detail links dari halaman listing per platform.

Adapter per platform:
- DeallsAdapter: requests + BS4 (SSR)
- KalibrrAdapter: requests + BS4 (SSR)
- GlintsAdapter: Playwright (SPA)
- JobstreetAdapter: Playwright (SPA)
- GenericAdapter: fallback
"""

import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from rich.console import Console

from engine.models import DetailLink

console = Console()


# --- URL classification ---

# Pola URL listing/search yang TIDAK boleh jadi opportunity
LISTING_URL_PATTERNS = [
    r"^/loker/?$",
    r"^/loker/industri",
    r"^/loker/lokasi",
    r"^/loker/posisi",
    r"^/loker/tipe",
    r"^/loker/populer",
    r"/find-jobs",
    r"^/job-board",
    r"^/jobs/?$",
    r"^/id/[^/]+-jobs$",           # jobstreet: /id/frontend-developer-internship-jobs
    r"^/id-ID/home",               # kalibrr listing
    r"^/id-ID/job-board",
    r"/search",
    r"/kategori",
    r"/category",
]

# Title listing yang TIDAK boleh jadi opportunity
LISTING_TITLE_PATTERNS = [
    r"explore jobs",
    r"job vacancy.*opportunit",
    r"lowongan kerja di",
    r"find jobs",
    r"job board",
    r"cari lowongan",
    r"loker terbaru",
    r"browse jobs",
]


def detect_platform(url: str) -> str:
    """Deteksi platform dari URL domain."""
    domain = urlparse(url).netloc.lower().replace("www.", "")

    platform_map = {
        "dealls.com": "dealls",
        "glints.com": "glints",
        "jobstreet.co.id": "jobstreet",
        "jobstreet.com": "jobstreet",
        "kalibrr.id": "kalibrr",
        "kalibrr.com": "kalibrr",
        "prosple.com": "prosple",
        "indeed.com": "indeed",
        "linkedin.com": "linkedin",
    }

    for key, platform in platform_map.items():
        if key in domain:
            return platform

    return "generic"


def is_listing_url(url: str) -> bool:
    """Cek apakah URL adalah halaman listing/search, bukan detail."""
    path = urlparse(url).path.rstrip("/")

    for pattern in LISTING_URL_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            return True

    return False


def is_listing_title(title: str) -> bool:
    """Cek apakah title menandakan halaman listing."""
    if not title:
        return False

    title_lower = title.lower()
    for pattern in LISTING_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return True

    return False


def classify_page(url: str, title: str = "") -> str:
    """Klasifikasi halaman: listing | detail | unknown."""
    if is_listing_url(url):
        return "listing"
    if is_listing_title(title):
        return "listing"
    return "detail"


# --- Platform Adapters ---


class PlatformAdapter(ABC):
    """Base adapter untuk extract job detail links dari listing page."""

    platform: str = "generic"

    @abstractmethod
    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        """Extract detail links dari halaman listing. html berisi raw HTML."""
        pass

    def needs_playwright(self) -> bool:
        """Apakah adapter ini butuh Playwright untuk render JS."""
        return False


class DeallsAdapter(PlatformAdapter):
    """Dealls — SSR, detail links di /loker/{slug}~{company}."""

    platform = "dealls"

    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Detail link: /loker/{slug}~{company}
            # Reject: /loker saja, /loker/industri, /loker/lokasi, /loker/posisi, /loker/tipe, /loker/populer
            if not re.match(r"^/loker/[a-z0-9]", href):
                continue
            if re.match(r"^/loker/(industri|lokasi|kategori|posisi|tipe|populer)", href):
                continue
            # Detail links Dealls mengandung ~ sebagai separator slug~company
            if "~" not in href:
                continue

            full_url = urljoin("https://dealls.com", href)
            if full_url in seen:
                continue
            seen.add(full_url)

            # Coba ambil title dari link text
            title = a.get_text(strip=True) or None

            links.append(DetailLink(
                url=full_url,
                title=title,
                source_platform="dealls",
                listing_url=url,
            ))

        return links


class KalibrrAdapter(PlatformAdapter):
    """Kalibrr — SSR, detail links di /id-ID/c/{company}/jobs/{id}/{slug}."""

    platform = "kalibrr"

    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Detail link: /id-ID/c/{company}/jobs/{id}/{slug}
            if not re.search(r"/c/[^/]+/jobs/\d+/", href):
                continue

            full_url = urljoin("https://www.kalibrr.id", href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(strip=True) or None

            links.append(DetailLink(
                url=full_url,
                title=title,
                source_platform="kalibrr",
                listing_url=url,
            ))

        return links


class GlintsAdapter(PlatformAdapter):
    """Glints — SPA, butuh Playwright. Detail links di /opportunities/jobs/."""

    platform = "glints"

    def needs_playwright(self) -> bool:
        return True

    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        """Extract dari HTML yang sudah di-render Playwright."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Detail link Glints: /opportunities/jobs/...
            if "/opportunities/jobs/" not in href:
                continue

            full_url = urljoin("https://glints.com", href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(strip=True) or None

            links.append(DetailLink(
                url=full_url,
                title=title,
                source_platform="glints",
                listing_url=url,
            ))

        return links


class JobstreetAdapter(PlatformAdapter):
    """Jobstreet — SPA, butuh Playwright. Detail links: /id/job/{id} atau /job/{id}."""

    platform = "jobstreet"

    def needs_playwright(self) -> bool:
        return True

    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        """Extract dari HTML yang sudah di-render Playwright."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Jobstreet detail: /id/job/{id} atau /job/{id} atau URL dengan job-id pattern
            if not re.search(r"/job/\d+|/id/job/", href):
                continue

            full_url = urljoin("https://www.jobstreet.co.id", href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(strip=True) or None

            links.append(DetailLink(
                url=full_url,
                title=title,
                source_platform="jobstreet",
                listing_url=url,
            ))

        return links


class GenericAdapter(PlatformAdapter):
    """Fallback adapter — cari links yang terlihat seperti job detail."""

    platform = "generic"

    def extract_detail_links(self, url: str, html: str = "") -> list[DetailLink]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()
        base_domain = urlparse(url).netloc

        # Pola URL yang kemungkinan job detail
        detail_patterns = [
            r"/job/",
            r"/jobs/\d+",
            r"/vacancy/",
            r"/career/",
            r"/position/",
            r"/opening/",
            r"/loker/[a-z0-9]",
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(url, href)

            # Hanya dari domain yang sama
            if urlparse(full_url).netloc != base_domain:
                continue

            # Skip listing URLs
            if is_listing_url(full_url):
                continue

            # Cek apakah match detail pattern
            matched = any(re.search(p, full_url, re.IGNORECASE) for p in detail_patterns)
            if not matched:
                continue

            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(strip=True) or None
            platform = detect_platform(full_url)

            links.append(DetailLink(
                url=full_url,
                title=title,
                source_platform=platform,
                listing_url=url,
            ))

        return links


# --- Adapter Registry ---

ADAPTERS: dict[str, PlatformAdapter] = {
    "dealls": DeallsAdapter(),
    "kalibrr": KalibrrAdapter(),
    "glints": GlintsAdapter(),
    "jobstreet": JobstreetAdapter(),
    "generic": GenericAdapter(),
}


def get_adapter(platform: str) -> PlatformAdapter:
    """Ambil adapter untuk platform tertentu."""
    return ADAPTERS.get(platform, ADAPTERS["generic"])


# --- Playwright helper ---

def fetch_with_playwright(url: str, wait_ms: int = 5000) -> Optional[str]:
    """
    Fetch halaman menggunakan Playwright (headless Chromium).
    Return rendered HTML, atau None jika gagal.
    """
    try:
        from playwright.sync_api import sync_playwright

        console.print(f"  [magenta][PW][/magenta] Rendering: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_ms)

            html = page.content()
            browser.close()

            return html

    except Exception as e:
        console.print(f"  [red][PW ERR][/red] Playwright failed for {url}: {e}")
        return None


# --- Main entry point ---

def extract_detail_links_from_listing(url: str, html: str = "") -> list[DetailLink]:
    """
    Extract job detail links dari satu listing URL.

    1. Deteksi platform dari URL
    2. Pilih adapter yang sesuai
    3. Jika adapter butuh Playwright dan html kosong, render dulu
    4. Parse links

    Return list of DetailLink.
    """
    platform = detect_platform(url)
    adapter = get_adapter(platform)

    console.print(f"  [cyan]Platform:[/cyan] {platform} | Adapter: {adapter.__class__.__name__}")

    # Jika adapter butuh Playwright dan belum ada HTML
    if adapter.needs_playwright() and not html:
        html = fetch_with_playwright(url) or ""

    # Jika belum ada HTML (non-playwright), fetch biasa
    if not html:
        try:
            import requests
            response = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }, timeout=15)
            html = response.text
        except Exception as e:
            console.print(f"  [red]Fetch failed: {e}[/red]")
            return []

    links = adapter.extract_detail_links(url, html)

    if links:
        console.print(f"  [green][OK][/green] Found {len(links)} detail links from {platform}")
    else:
        console.print(f"  [yellow][WARN][/yellow] No detail links found from {platform}")

    return links
