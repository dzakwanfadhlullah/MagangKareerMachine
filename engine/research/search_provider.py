"""Parallel search providers for fast research mode."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from typing import Protocol

import requests
from rich.console import Console

from engine.models import RawSearchResult
from engine.research.result_normalizer import dedupe_results, normalize_search_hit

console = Console()


class SearchProvider(Protocol):
    """Interface for swappable search-index providers."""

    name: str

    def search(self, query: str, max_results: int) -> list[RawSearchResult]:
        """Search one query and return normalized results."""
        ...


class DuckDuckGoProvider:
    """DuckDuckGo Search provider using duckduckgo_search/DDGS."""

    name = "ddgs"
    backends = ("auto", "html", "lite")

    def _ddgs_class(self):
        try:
            from ddgs import DDGS  # type: ignore
            return DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore
                return DDGS
            except ImportError:
                return None

    def search(self, query: str, max_results: int) -> list[RawSearchResult]:
        ddgs_class = self._ddgs_class()
        if ddgs_class is None:
            console.print("[yellow][WARN][/yellow] ddgs/duckduckgo-search not installed, skipping web search")
            return []

        hits = []
        errors = []
        for backend in self.backends:
            try:
                hits = ddgs_class().text(
                    query,
                    region="id-id",
                    safesearch="moderate",
                    backend=backend,
                    max_results=max_results,
                )
                if hits:
                    break
            except Exception as e:
                errors.append(f"{backend}: {e}")
                time.sleep(0.25)

        if not hits and errors:
            console.print(f"  [red][ERR][/red] Search failed for '{query}': {' | '.join(errors[:2])}")

        results = []
        for hit in hits:
            result = normalize_search_hit(hit, query=query, source=self.name)
            if result:
                results.append(result)
        return results


class BraveSearchProvider:
    """Brave Search API provider. Requires BRAVE_SEARCH_API_KEY."""

    name = "brave"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")

    def search(self, query: str, max_results: int) -> list[RawSearchResult]:
        if not self.api_key:
            console.print("  [yellow][WARN][/yellow] BRAVE_SEARCH_API_KEY missing, skipping Brave")
            return []
        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                params={"q": query, "count": min(max_results, 20), "country": "id"},
                timeout=15,
            )
            response.raise_for_status()
            hits = response.json().get("web", {}).get("results", [])
        except Exception as e:
            console.print(f"  [red][ERR][/red] Brave search failed for '{query}': {e}")
            return []

        results = []
        for hit in hits:
            result = normalize_search_hit(
                {"title": hit.get("title"), "snippet": hit.get("description"), "url": hit.get("url")},
                query=query,
                source=self.name,
            )
            if result:
                results.append(result)
        return results


class SerperSearchProvider:
    """Serper Google Search API provider. Requires SERPER_API_KEY."""

    name = "serper"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")

    def search(self, query: str, max_results: int) -> list[RawSearchResult]:
        if not self.api_key:
            console.print("  [yellow][WARN][/yellow] SERPER_API_KEY missing, skipping Serper")
            return []
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"q": query, "num": min(max_results, 20), "gl": "id"},
                timeout=15,
            )
            response.raise_for_status()
            hits = response.json().get("organic", [])
        except Exception as e:
            console.print(f"  [red][ERR][/red] Serper search failed for '{query}': {e}")
            return []

        results = []
        for hit in hits:
            result = normalize_search_hit(
                {"title": hit.get("title"), "snippet": hit.get("snippet"), "url": hit.get("link")},
                query=query,
                source=self.name,
            )
            if result:
                results.append(result)
        return results


class TavilySearchProvider:
    """Tavily Search API provider. Requires TAVILY_API_KEY."""

    name = "tavily"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

    def search(self, query: str, max_results: int) -> list[RawSearchResult]:
        if not self.api_key:
            console.print("  [yellow][WARN][/yellow] TAVILY_API_KEY missing, skipping Tavily")
            return []
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": min(max_results, 20),
                    "search_depth": "basic",
                },
                timeout=15,
            )
            response.raise_for_status()
            hits = response.json().get("results", [])
        except Exception as e:
            console.print(f"  [red][ERR][/red] Tavily search failed for '{query}': {e}")
            return []

        results = []
        for hit in hits:
            result = normalize_search_hit(
                {"title": hit.get("title"), "snippet": hit.get("content"), "url": hit.get("url")},
                query=query,
                source=self.name,
            )
            if result:
                results.append(result)
        return results


def get_search_provider(provider_name: str = "auto") -> SearchProvider:
    """Choose a search provider by CLI/env name, falling back safely to DDG."""
    requested = (provider_name or os.getenv("SEARCH_PROVIDER") or "auto").strip().lower()
    if requested in {"ddg", "ddgs", "duckduckgo"}:
        return DuckDuckGoProvider()
    if requested == "brave":
        provider = BraveSearchProvider()
        return provider if provider.api_key else DuckDuckGoProvider()
    if requested == "serper":
        provider = SerperSearchProvider()
        return provider if provider.api_key else DuckDuckGoProvider()
    if requested == "tavily":
        provider = TavilySearchProvider()
        return provider if provider.api_key else DuckDuckGoProvider()

    for provider_cls, env_key in [
        (BraveSearchProvider, "BRAVE_SEARCH_API_KEY"),
        (SerperSearchProvider, "SERPER_API_KEY"),
        (TavilySearchProvider, "TAVILY_API_KEY"),
    ]:
        if os.getenv(env_key):
            return provider_cls()
    return DuckDuckGoProvider()


def search_queries_parallel(
    queries: list[str],
    provider: SearchProvider | None = None,
    max_results_per_query: int = 10,
    workers: int = 8,
) -> list[RawSearchResult]:
    """Run search queries concurrently and return deduped results."""
    active_provider = provider or get_search_provider("auto")
    if not queries:
        return []

    console.print(
        f"[bold]Searching index:[/bold] {len(queries)} queries, "
        f"provider={active_provider.name}, workers={workers}"
    )
    results: list[RawSearchResult] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(active_provider.search, query, max_results_per_query): query
            for query in queries
        }
        for future in as_completed(future_map):
            query = future_map[future]
            try:
                query_results = future.result()
                results.extend(query_results)
                console.print(f"  [dim]{len(query_results)} hits: {query[:80]}[/dim]")
            except Exception as e:
                console.print(f"  [red][ERR][/red] Search worker failed for '{query}': {e}")

    deduped = dedupe_results(results)
    console.print(f"[green][OK][/green] Search results: {len(results)} raw -> {len(deduped)} unique URLs")
    return deduped
