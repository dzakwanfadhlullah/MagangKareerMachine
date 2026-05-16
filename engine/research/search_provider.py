"""Parallel search providers for fast research mode."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Protocol

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


def search_queries_parallel(
    queries: list[str],
    provider: SearchProvider | None = None,
    max_results_per_query: int = 10,
    workers: int = 8,
) -> list[RawSearchResult]:
    """Run search queries concurrently and return deduped results."""
    active_provider = provider or DuckDuckGoProvider()
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
