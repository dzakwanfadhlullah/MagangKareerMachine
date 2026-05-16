"""Fast research pipeline: search-index-first discovery then core extraction."""

from typing import Optional

from rich.console import Console

from engine.db import (
    get_existing_urls,
    get_raw_pages_by_urls,
    init_db,
    save_discovery_candidates,
    save_opportunity,
    save_raw_api_responses,
    save_raw_page,
    save_raw_results,
    save_rejected_candidate,
)
from engine.deduper import dedupe_opportunities
from engine.exporter import export_all
from engine.extractor import (
    extract_all_with_rejections,
    normalize_target_category,
)
from engine.fetcher import fetch_all
from engine.listing_parser import classify_page, detect_platform
from engine.models import DetailLink, RawPage
from engine.research.page_verifier import verify_research_page
from engine.research.profiles import get_research_profile
from engine.research.query_planner import plan_research_queries
from engine.research.search_provider import SearchProvider, search_queries_parallel
from engine.research.url_ranker import rank_research_results, score_research_url
from engine.scorer import score_all

console = Console()


def _raw_page_from_dict(row: dict) -> RawPage:
    return RawPage(
        url=row["url"],
        title=row.get("title"),
        text_content=row.get("text_content") or "",
        html_content=row.get("html_content") or "",
        status_code=row.get("status_code") or 200,
        page_type=row.get("page_type") or "unknown",
        source_platform=row.get("source_platform"),
        fetch_method="cached",
    )


def _fetch_or_load_research_results(results, workers: int, timeout: int) -> list[RawPage]:
    urls = [result.url for result in results]
    existing = get_existing_urls()
    cached_rows = get_raw_pages_by_urls([url for url in urls if url in existing])
    cached_pages = [_raw_page_from_dict(row) for row in cached_rows]
    if cached_pages:
        console.print(f"  [dim]Loaded {len(cached_pages)} cached research pages[/dim]")

    fetched_pages = fetch_all(results, existing, workers=workers, timeout=timeout)
    for page in fetched_pages:
        save_raw_page(page.model_dump())
        if page.api_responses:
            save_raw_api_responses([item.model_dump() for item in page.api_responses])

    by_url = {page.url: page for page in cached_pages}
    by_url.update({page.url: page for page in fetched_pages})
    return [by_url[url] for url in urls if url in by_url]


def _save_research_candidates(results, target_category: Optional[str]) -> None:
    target = normalize_target_category(target_category)
    candidates = []
    for result in results:
        link = DetailLink(
            url=result.url,
            title=result.title,
            source_platform=result.source_platform or detect_platform(result.url),
            listing_url=f"research:{result.query}",
            discovery_method="search",
            target_score=score_research_url(result, target_category=target),
        )
        row = link.model_dump()
        row["target_category"] = target
        row["status"] = "discovered"
        candidates.append(row)
    save_discovery_candidates(candidates)


def run_research_pipeline(
    query: Optional[str] = None,
    location: str = "Indonesia",
    target_category: Optional[str] = None,
    profile: str = "normal",
    query_count: Optional[int] = None,
    max_fetch: Optional[int] = None,
    workers: Optional[int] = None,
    timeout: Optional[int] = None,
    min_score: int = 40,
    results_per_query: Optional[int] = None,
    provider: Optional[SearchProvider] = None,
) -> int:
    """Run fast research mode and save accepted opportunities."""
    profile_cfg = get_research_profile(profile)
    query_count = query_count if query_count is not None else profile_cfg["query_count"]
    max_fetch = max_fetch if max_fetch is not None else profile_cfg["max_fetch"]
    workers = min(workers if workers is not None else profile_cfg["workers"], 12)
    timeout = timeout if timeout is not None else profile_cfg["timeout"]
    results_per_query = results_per_query if results_per_query is not None else profile_cfg["results_per_query"]

    console.rule("[bold cyan]MagangKareer Fast Research[/bold cyan]")
    init_db()

    console.print("\n[bold]Step 1:[/bold] Planning queries...")
    queries = plan_research_queries(
        query=query,
        location=location,
        target_category=target_category,
        query_count=query_count,
    )
    console.print(f"[green][OK][/green] Generated {len(queries)} research queries")

    console.print("\n[bold]Step 2:[/bold] Searching index...")
    search_results = search_queries_parallel(
        queries,
        provider=provider,
        max_results_per_query=results_per_query,
        workers=workers,
    )
    if not search_results:
        console.print("[yellow][WARN][/yellow] No search results")
        export_all(metadata={
            "command": "research",
            "query": query,
            "location": location,
            "target_category": target_category,
            "profile": profile,
            "result_count": 0,
        })
        return 0

    for result in search_results:
        result.page_type = result.page_type if result.page_type in {"listing", "detail"} else classify_page(result.url, result.title)
        result.source_platform = result.source_platform or detect_platform(result.url)
    save_raw_results([result.model_dump() for result in search_results])

    console.print("\n[bold]Step 3:[/bold] Ranking direct URLs...")
    ranked_results = rank_research_results(
        search_results,
        target_category=target_category,
        max_urls=max_fetch,
    )
    _save_research_candidates(ranked_results, target_category)
    console.print(f"[green][OK][/green] Selected {len(ranked_results)} URLs to verify (max {max_fetch})")

    if not ranked_results:
        console.print("[yellow][WARN][/yellow] No URLs survived research ranking")
        export_all(metadata={
            "command": "research",
            "query": query,
            "location": location,
            "target_category": target_category,
            "profile": profile,
            "result_count": 0,
        })
        return 0

    console.print(f"\n[bold]Step 4:[/bold] Fetching top URLs ({workers} workers, {timeout}s timeout)...")
    pages = _fetch_or_load_research_results(ranked_results, workers=workers, timeout=timeout)
    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    console.print("\n[bold]Step 5:[/bold] Verifying pages...")
    verified_pages = []
    rejected_count = 0
    for page in pages:
        rejection = verify_research_page(page)
        if rejection:
            if save_rejected_candidate(rejection.model_dump()):
                rejected_count += 1
            continue
        page.page_type = "detail"
        verified_pages.append(page)
    console.print(f"[green][OK][/green] Verified {len(verified_pages)} detail pages; rejected {rejected_count}")

    console.print("\n[bold]Step 6:[/bold] Extracting and filtering...")
    opportunities, rejections = extract_all_with_rejections(
        verified_pages,
        target_category=target_category,
    )
    saved_rejections = 0
    for rejection in rejections:
        if save_rejected_candidate(rejection.model_dump()):
            saved_rejections += 1
    if saved_rejections:
        console.print(f"  [dim]Saved {saved_rejections} rejected candidates for audit[/dim]")

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No accepted opportunities")
        export_all(metadata={
            "command": "research",
            "query": query,
            "location": location,
            "target_category": target_category,
            "profile": profile,
            "query_count": len(queries),
            "searched_urls": len(search_results),
            "fetched_pages": len(pages),
            "verified_pages": len(verified_pages),
        })
        return 0

    console.print("\n[bold]Step 7:[/bold] Scoring, deduping, saving...")
    opportunities = score_all(opportunities)
    opportunities = [opp for opp in opportunities if opp.score >= min_score]
    opportunities = dedupe_opportunities(opportunities)

    saved = 0
    for opp in opportunities:
        if save_opportunity(opp.model_dump()):
            saved += 1

    console.print(f"[green][OK][/green] Saved {saved} opportunities")
    console.print("\n[bold]Exporting...[/bold]")
    export_all(metadata={
        "command": "research",
        "query": query,
        "location": location,
        "target_category": target_category,
        "profile": profile,
        "min_score": min_score,
        "query_count": len(queries),
        "searched_urls": len(search_results),
        "selected_urls": len(ranked_results),
        "fetched_pages": len(pages),
        "verified_pages": len(verified_pages),
        "workers": workers,
        "timeout": timeout,
    })

    console.rule("[bold green]Done[/bold green]")
    console.print(f"\n Saved: {saved} opportunities")
    return saved
