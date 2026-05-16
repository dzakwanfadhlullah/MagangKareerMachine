"""Searcher — cari peluang magang dari web dan manual sources."""

import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from rich.console import Console

from engine.extractor import normalize_target_category
from engine.models import RawSearchResult

console = Console()

SOURCES_PATH = Path("config/sources.yml")


def load_sources(config_path: Optional[Path] = None) -> dict:
    """Load sources config dari YAML."""
    path = config_path or SOURCES_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_crawl_profiles(config_path: Optional[Path] = None) -> dict:
    """Load crawl profile presets from sources config."""
    config = load_sources(config_path)
    return config.get("crawl_profiles", {})


def get_crawl_profile(profile: str, config_path: Optional[Path] = None) -> dict:
    """Return a named crawl profile, raising a friendly error if missing."""
    profiles = load_crawl_profiles(config_path)
    if profile not in profiles:
        available = ", ".join(sorted(profiles)) or "-"
        raise ValueError(f"Unknown crawl profile '{profile}'. Available: {available}")
    return profiles[profile]


def iter_manual_source_entries(config: dict, target_category: Optional[str] = None) -> list[dict]:
    """
    Flatten manual source config.

    Supports role-specific sources, the legacy manual_sources list, and the
    tiered sources format. Role-specific entries are prepended for targeted
    crawls/searches.
    """
    entries: list[dict] = []
    seen_urls: set[str] = set()

    def add_entry(item: dict, tier: str) -> None:
        if not isinstance(item, dict) or not item.get("url"):
            return
        url = item["url"]
        if url in seen_urls:
            return
        seen_urls.add(url)
        copied = dict(item)
        copied["tier"] = tier
        entries.append(copied)

    target = normalize_target_category(target_category)
    role_sources = config.get("role_sources", {})
    if target and isinstance(role_sources, dict):
        for item in role_sources.get(target, []) or []:
            add_entry(item, f"role:{target}")

    legacy_urls = config.get("manual_sources", [])
    for url in legacy_urls:
        domain = urlparse(url).netloc
        add_entry({
            "name": f"manual_{domain}",
            "platform": None,
            "type": "listing",
            "url": url,
        }, "legacy")

    tiered = config.get("sources", {})
    if isinstance(tiered, dict):
        for tier_name in sorted(tiered):
            tier_entries = tiered.get(tier_name) or []
            for item in tier_entries:
                add_entry(item, tier_name)

    return entries


def search_web(queries: list[str], max_results: int = 20) -> list[RawSearchResult]:
    """
    Cari di web menggunakan DuckDuckGo Search.
    Fallback ke empty list jika gagal.
    """
    results = []

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        console.print("[yellow][WARN][/yellow] duckduckgo-search not installed, skipping web search")
        return results

    ddgs = DDGS()

    for query in queries:
        try:
            console.print(f"  [dim]Searching: {query}[/dim]")
            hits = ddgs.text(query, max_results=max_results)

            for hit in hits:
                result = RawSearchResult(
                    query=query,
                    title=hit.get("title", ""),
                    snippet=hit.get("body", ""),
                    url=hit.get("href", ""),
                    source="ddgs",
                )
                # Skip jika URL kosong
                if result.url:
                    results.append(result)

            # Rate limiting — jeda antar query
            time.sleep(1.5)

        except Exception as e:
            console.print(f"  [red][ERR][/red] Search failed for '{query}': {e}")
            continue

    # Dedupe by URL
    seen_urls = set()
    unique = []
    for r in results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique.append(r)

    return unique


def search_manual_sources(
    config_path: Optional[Path] = None,
    target_category: Optional[str] = None,
) -> list[RawSearchResult]:
    """
    Generate RawSearchResult dari manual seed URLs di sources.yml.
    """
    config = load_sources(config_path)
    manual_sources = iter_manual_source_entries(config, target_category=target_category)
    results = []

    for item in manual_sources:
        url = item["url"]
        domain = urlparse(url).netloc
        name = item.get("name") or domain
        platform = item.get("platform")
        tier = item.get("tier") or "manual"
        result = RawSearchResult(
            query=f"manual_source:{tier}",
            title=f"Manual source: {name}",
            snippet=f"{tier} | {platform or domain}",
            url=url,
            source="manual",
            page_type=item.get("type") or "listing",
            source_platform=platform,
        )
        results.append(result)

    return results


def search_all(
    queries: list[str],
    max_results: int = 20,
    config_path: Optional[Path] = None,
    target_category: Optional[str] = None,
) -> list[RawSearchResult]:
    """
    Jalankan semua strategi pencarian:
    1. Web search (DDGS)
    2. Manual sources

    Return combined results, deduplicated by URL.
    """
    config = load_sources(config_path)
    all_results = []

    # Web search jika enabled
    if config.get("search", {}).get("enabled", True):
        limit = config.get("search", {}).get("max_results_per_query", max_results)
        web_results = search_web(queries, limit)
        all_results.extend(web_results)
        console.print(f"[green][OK][/green] Found {len(web_results)} results from web search")

    # Manual sources
    manual_results = search_manual_sources(config_path, target_category=target_category)
    all_results.extend(manual_results)
    console.print(f"[green][OK][/green] Found {len(manual_results)} manual sources")

    # Final dedupe by URL
    seen_urls = set()
    unique = []
    for r in all_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique.append(r)

    console.print(f"[green][OK][/green] Total unique results: {len(unique)}")
    return unique
