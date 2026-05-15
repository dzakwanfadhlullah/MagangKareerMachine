"""Searcher — cari peluang magang dari web dan manual sources."""

import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from rich.console import Console

from engine.models import RawSearchResult

console = Console()

SOURCES_PATH = Path("config/sources.yml")


def load_sources(config_path: Optional[Path] = None) -> dict:
    """Load sources config dari YAML."""
    path = config_path or SOURCES_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def search_manual_sources(config_path: Optional[Path] = None) -> list[RawSearchResult]:
    """
    Generate RawSearchResult dari manual seed URLs di sources.yml.
    """
    config = load_sources(config_path)
    manual_urls = config.get("manual_sources", [])
    results = []

    for url in manual_urls:
        domain = urlparse(url).netloc
        result = RawSearchResult(
            query="manual_source",
            title=f"Manual source: {domain}",
            snippet=None,
            url=url,
            source="manual",
        )
        results.append(result)

    return results


def search_all(
    queries: list[str],
    max_results: int = 20,
    config_path: Optional[Path] = None,
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
    manual_results = search_manual_sources(config_path)
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
