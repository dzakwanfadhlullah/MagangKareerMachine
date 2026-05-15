"""Pipeline — orchestrator yang merangkai seluruh alur engine."""

from pathlib import Path
from typing import Optional

from rich.console import Console

from engine.query_builder import build_queries, build_queries_from_raw
from engine.searcher import search_all, search_manual_sources
from engine.fetcher import fetch_all
from engine.extractor import extract_all
from engine.scorer import score_all
from engine.deduper import dedupe_opportunities
from engine.db import (
    save_raw_results,
    save_raw_page,
    save_opportunity,
    get_existing_urls,
    get_all_opportunities,
)
from engine.exporter import export_all
from engine.reporter import generate_report

console = Console()


def run_search_pipeline(
    query: str,
    location: str = "Indonesia",
    limit: int = 20,
    min_score: int = 40,
) -> int:
    """
    Jalankan pipeline pencarian lengkap:
    1. Build queries
    2. Search (web + manual)
    3. Fetch pages
    4. Extract opportunities
    5. Score
    6. Dedupe
    7. Save ke database
    8. Export

    Return jumlah opportunity yang disimpan.
    """
    console.rule("[bold cyan]MagangKareer Search Pipeline[/bold cyan]")

    # Step 1: Build queries
    console.print("\n[bold]Step 1:[/bold] Building queries...")
    queries = build_queries_from_raw(query, location)
    console.print(f"  Generated {len(queries)} search queries")

    # Step 2: Search
    console.print("\n[bold]Step 2:[/bold] Searching...")
    raw_results = search_all(queries, limit)

    if not raw_results:
        console.print("[yellow][WARN][/yellow] No results found")
        return 0

    # Simpan raw results ke DB
    raw_dicts = [r.model_dump() for r in raw_results]
    save_raw_results(raw_dicts)
    console.print(f"[green][OK][/green] Saved {len(raw_results)} raw results")

    # Step 3: Fetch pages
    console.print("\n[bold]Step 3:[/bold] Fetching pages...")
    existing_urls = get_existing_urls()
    pages = fetch_all(raw_results, existing_urls)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    # Simpan raw pages ke DB
    for page in pages:
        save_raw_page(page.model_dump())

    # Step 4: Extract opportunities
    console.print("\n[bold]Step 4:[/bold] Extracting opportunities...")
    opportunities = extract_all(pages)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities extracted")
        return 0

    # Step 5: Score
    console.print("\n[bold]Step 5:[/bold] Scoring...")
    opportunities = score_all(opportunities)

    # Filter by minimum score
    opportunities = [o for o in opportunities if o.score >= min_score]
    console.print(f"  {len(opportunities)} opportunities with score >= {min_score}")

    # Step 6: Dedupe
    console.print("\n[bold]Step 6:[/bold] Deduplicating...")
    opportunities = dedupe_opportunities(opportunities)

    # Step 7: Save to database
    console.print("\n[bold]Step 7:[/bold] Saving to database...")
    saved = 0
    for opp in opportunities:
        opp_dict = opp.model_dump()
        if save_opportunity(opp_dict):
            saved += 1
    console.print(f"[green][OK][/green] Saved {saved} new opportunities")

    # Step 8: Export
    console.print("\n[bold]Step 8:[/bold] Exporting...")
    export_all()

    console.rule("[bold green]Pipeline Complete[/bold green]")
    console.print(f"\n✅ Total saved: {saved} opportunities")

    return saved


def run_crawl_sources(min_score: int = 40) -> int:
    """
    Crawl hanya dari manual sources di sources.yml.
    Tanpa web search.
    """
    console.rule("[bold cyan]MagangKareer Source Crawl[/bold cyan]")

    # Step 1: Load manual sources
    console.print("\n[bold]Step 1:[/bold] Loading manual sources...")
    raw_results = search_manual_sources()

    if not raw_results:
        console.print("[yellow][WARN][/yellow] No manual sources configured")
        return 0

    raw_dicts = [r.model_dump() for r in raw_results]
    save_raw_results(raw_dicts)

    # Step 2: Fetch
    console.print("\n[bold]Step 2:[/bold] Fetching pages...")
    existing_urls = get_existing_urls()
    pages = fetch_all(raw_results, existing_urls)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    for page in pages:
        save_raw_page(page.model_dump())

    # Step 3: Extract
    console.print("\n[bold]Step 3:[/bold] Extracting opportunities...")
    opportunities = extract_all(pages)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities extracted")
        return 0

    # Step 4: Score
    console.print("\n[bold]Step 4:[/bold] Scoring...")
    opportunities = score_all(opportunities)
    opportunities = [o for o in opportunities if o.score >= min_score]

    # Step 5: Dedupe
    console.print("\n[bold]Step 5:[/bold] Deduplicating...")
    opportunities = dedupe_opportunities(opportunities)

    # Step 6: Save
    console.print("\n[bold]Step 6:[/bold] Saving...")
    saved = 0
    for opp in opportunities:
        opp_dict = opp.model_dump()
        if save_opportunity(opp_dict):
            saved += 1

    # Step 7: Export
    console.print("\n[bold]Step 7:[/bold] Exporting...")
    export_all()

    console.rule("[bold green]Crawl Complete[/bold green]")
    console.print(f"\n✅ Total saved: {saved} opportunities")

    return saved
