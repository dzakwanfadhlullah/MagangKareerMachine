"""Deduper — hapus duplikat opportunity berdasarkan canonical key dan fuzzy matching."""

import hashlib
import re
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console

from engine.models import Opportunity
from engine.url_utils import canonicalize_url

console = Console()


def normalize_text(text: str) -> str:
    """Normalisasi teks untuk perbandingan: lowercase, strip, hapus karakter spesial."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)  # Hapus karakter non-alphanumeric
    text = re.sub(r"\s+", " ", text)  # Normalize whitespace
    return text


def get_domain(url: str) -> str:
    """Ambil domain dari URL."""
    try:
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return ""


def generate_canonical_key(opp: Opportunity) -> str:
    """
    Generate canonical key untuk deduplikasi.

    Strategi:
    - Jika company diketahui: hash(company|role|location|title)
    - Jika company tidak diketahui: hash(title|domain)
    """
    if opp.company:
        raw = "|".join([
            normalize_text(opp.company),
            normalize_text(opp.role or ""),
            normalize_text(opp.location or ""),
            normalize_text(opp.title),
        ])
    else:
        domain = get_domain(opp.source_url)
        raw = "|".join([
            normalize_text(opp.title),
            domain,
        ])

    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def fuzzy_is_duplicate(opp1: Opportunity, opp2: Opportunity, threshold: int = 90) -> bool:
    """
    Cek apakah dua opportunity adalah duplikat menggunakan fuzzy matching.
    Return True jika similarity > threshold.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        # Fallback ke exact match jika rapidfuzz tidak tersedia
        return normalize_text(opp1.title) == normalize_text(opp2.title)

    # Compare titles
    title_sim = fuzz.ratio(normalize_text(opp1.title), normalize_text(opp2.title))

    if title_sim > threshold:
        # Cek juga role dan location untuk konfirmasi
        role_match = normalize_text(opp1.role or "") == normalize_text(opp2.role or "")
        loc_match = normalize_text(opp1.location or "") == normalize_text(opp2.location or "")

        # Jika title sangat mirip DAN (role atau location cocok), itu duplikat
        if role_match or loc_match or title_sim > 95:
            return True

    return False


def dedupe_opportunities(opportunities: list[Opportunity]) -> list[Opportunity]:
    """
    Deduplikasi daftar opportunities.

    Strategi:
    1. Generate canonical_key untuk setiap opportunity
    2. Group by canonical_key (exact match)
    3. Cek fuzzy similarity untuk yang tersisa
    4. Simpan yang skor tertinggi

    Return list tanpa duplikat.
    """
    if not opportunities:
        return []

    url_map: dict[str, Opportunity] = {}
    no_url: list[Opportunity] = []
    for opp in opportunities:
        if opp.source_url:
            opp.source_url = canonicalize_url(opp.source_url)
            if opp.detail_url:
                opp.detail_url = canonicalize_url(opp.detail_url)
            if opp.source_url not in url_map or opp.score > url_map[opp.source_url].score:
                url_map[opp.source_url] = opp
        else:
            no_url.append(opp)
    opportunities = list(url_map.values()) + no_url

    # Step 1: Assign canonical keys
    for opp in opportunities:
        opp.canonical_key = generate_canonical_key(opp)

    # Step 2: Group by canonical_key — simpan skor tertinggi
    key_map: dict[str, Opportunity] = {}
    for opp in opportunities:
        key = opp.canonical_key
        if key not in key_map or opp.score > key_map[key].score:
            key_map[key] = opp

    unique = list(key_map.values())

    # Step 3: Fuzzy dedupe antar hasil yang tersisa
    final = []
    for opp in unique:
        is_dup = False
        for existing in final:
            if fuzzy_is_duplicate(opp, existing):
                # Simpan yang skor tertinggi
                if opp.score > existing.score:
                    final.remove(existing)
                    final.append(opp)
                is_dup = True
                break
        if not is_dup:
            final.append(opp)

    removed = len(opportunities) - len(final)
    if removed > 0:
        console.print(f"[green][OK][/green] Removed {removed} duplicates, {len(final)} unique opportunities")
    else:
        console.print(f"[green][OK][/green] No duplicates found, {len(final)} opportunities")

    return final
