"""Pipeline — orchestrator 2-stage: listing crawl -> detail crawl.

Alur baru:
1. Listing URLs (dari sources.yml atau search)
2. Fetch listing pages
3. Extract detail links dari listing (per-platform adapter)
4. Enqueue detail URLs ke crawl_queue
5. Fetch detail pages
6. Extract opportunity metadata (hanya dari detail pages)
7. Score
8. Dedupe
9. Save ke database
10. Export
"""

from typing import Optional

from rich.console import Console

from engine.query_builder import build_queries_from_raw
from engine.searcher import search_all, search_manual_sources
from engine.fetcher import fetch_all, fetch_detail_urls
from engine.listing_parser import (
    extract_detail_links_from_listing,
    classify_page,
    detect_platform,
)
from engine.extractor import extract_all
from engine.scorer import score_all
from engine.deduper import dedupe_opportunities
from engine.db import (
    save_raw_results,
    save_raw_page,
    save_crawl_queue,
    get_pending_crawl_queue,
    mark_crawl_done,
    save_opportunity,
    get_existing_urls,
)
from engine.exporter import export_all

console = Console()


def _stage1_extract_detail_links(pages) -> list[dict]:
    """
    Stage 1: Dari listing pages, extract detail links.
    Return list of detail link dicts untuk crawl_queue.
    """
    all_links = []

    for page in pages:
        if page.page_type != "listing":
            # Bukan listing — mungkin langsung detail page
            continue

        console.print(f"  [cyan]Parsing listing:[/cyan] {page.url}")
        links = extract_detail_links_from_listing(page.url, page.html_content)

        for link in links:
            all_links.append(link.model_dump())

    return all_links


def _stage2_process_details(detail_pages, min_score: int) -> int:
    """
    Stage 2: Extract, score, dedupe, save dari detail pages.
    Return jumlah opportunity tersimpan.
    """
    # Extract opportunities (otomatis skip listing pages)
    console.print("\n[bold]Extracting opportunities...[/bold]")
    opportunities = extract_all(detail_pages)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities extracted from detail pages")
        return 0

    # Score
    console.print("\n[bold]Scoring...[/bold]")
    opportunities = score_all(opportunities)

    # Filter by minimum score
    opportunities = [o for o in opportunities if o.score >= min_score]
    console.print(f"  {len(opportunities)} opportunities with score >= {min_score}")

    if not opportunities:
        return 0

    # Dedupe
    console.print("\n[bold]Deduplicating...[/bold]")
    opportunities = dedupe_opportunities(opportunities)

    # Save to database
    console.print("\n[bold]Saving to database...[/bold]")
    saved = 0
    for opp in opportunities:
        opp_dict = opp.model_dump()
        if save_opportunity(opp_dict):
            saved += 1

    console.print(f"[green][OK][/green] Saved {saved} opportunities")
    return saved


def run_search_pipeline(
    query: str,
    location: str = "Indonesia",
    limit: int = 20,
    min_score: int = 40,
) -> int:
    """
    Pipeline pencarian lengkap (2-stage):

    Stage 1: Search -> fetch listing/detail -> extract detail links
    Stage 2: Fetch detail pages -> extract -> score -> dedupe -> save
    """
    console.rule("[bold cyan]MagangKareer Search Pipeline[/bold cyan]")

    # === STEP 1: Build queries & search ===
    console.print("\n[bold]Step 1:[/bold] Building queries...")
    queries = build_queries_from_raw(query, location)
    console.print(f"  Generated {len(queries)} search queries")

    console.print("\n[bold]Step 2:[/bold] Searching...")
    raw_results = search_all(queries, limit)

    if not raw_results:
        console.print("[yellow][WARN][/yellow] No results found")
        return 0

    # Classify page types dan set platform
    for r in raw_results:
        r.page_type = classify_page(r.url, r.title)
        r.source_platform = detect_platform(r.url)

    raw_dicts = [r.model_dump() for r in raw_results]
    save_raw_results(raw_dicts)
    console.print(f"[green][OK][/green] Saved {len(raw_results)} raw results")

    # === STEP 2: Fetch all pages ===
    console.print("\n[bold]Step 3:[/bold] Fetching pages...")
    existing_urls = get_existing_urls()
    pages = fetch_all(raw_results, existing_urls)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    for page in pages:
        save_raw_page(page.model_dump())

    # === STAGE 1: Extract detail links dari listing pages ===
    listing_pages = [p for p in pages if p.page_type == "listing"]
    detail_pages = [p for p in pages if p.page_type != "listing"]

    if listing_pages:
        console.print(f"\n[bold]Stage 1:[/bold] Extracting detail links from {len(listing_pages)} listing pages...")
        detail_links = _stage1_extract_detail_links(listing_pages)

        if detail_links:
            saved_queue = save_crawl_queue(detail_links)
            console.print(f"[green][OK][/green] Enqueued {saved_queue} detail URLs")

            # Fetch detail pages dari queue
            console.print("\n[bold]Stage 1b:[/bold] Fetching detail pages from queue...")
            detail_urls = [link["url"] for link in detail_links]
            existing = get_existing_urls()
            new_detail_pages = fetch_detail_urls(detail_urls, existing)

            for page in new_detail_pages:
                save_raw_page(page.model_dump())
                mark_crawl_done(page.url)

            detail_pages.extend(new_detail_pages)
        else:
            console.print("[yellow][WARN][/yellow] No detail links extracted from listings")

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages to process")
        return 0

    # === STAGE 2: Extract, score, dedupe, save ===
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process_details(detail_pages, min_score)

    # Export
    console.print("\n[bold]Exporting...[/bold]")
    export_all()

    console.rule("[bold green]Pipeline Complete[/bold green]")
    console.print(f"\n Total saved: {saved} opportunities")

    return saved


def run_crawl_sources(min_score: int = 40) -> int:
    """
    Crawl dari manual sources di sources.yml.
    2-stage: listing -> detail links -> fetch detail -> extract.
    """
    console.rule("[bold cyan]MagangKareer Source Crawl (2-Stage)[/bold cyan]")

    # === STEP 1: Load manual sources ===
    console.print("\n[bold]Step 1:[/bold] Loading manual sources...")
    raw_results = search_manual_sources()

    if not raw_results:
        console.print("[yellow][WARN][/yellow] No manual sources configured")
        return 0

    # Classify page types
    for r in raw_results:
        r.page_type = classify_page(r.url, r.title)
        r.source_platform = detect_platform(r.url)

    raw_dicts = [r.model_dump() for r in raw_results]
    save_raw_results(raw_dicts)

    # === STEP 2: Fetch listing pages ===
    console.print("\n[bold]Step 2:[/bold] Fetching listing pages...")
    existing_urls = get_existing_urls()
    pages = fetch_all(raw_results, existing_urls)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    for page in pages:
        save_raw_page(page.model_dump())

    # === STAGE 1: Extract detail links ===
    listing_pages = [p for p in pages if p.page_type == "listing"]
    detail_pages = [p for p in pages if p.page_type != "listing"]

    console.print(f"\n[bold]Stage 1:[/bold] Parsing {len(listing_pages)} listing pages, "
                  f"{len(detail_pages)} direct detail pages...")

    if listing_pages:
        detail_links = _stage1_extract_detail_links(listing_pages)

        if detail_links:
            saved_queue = save_crawl_queue(detail_links)
            console.print(f"[green][OK][/green] Enqueued {saved_queue} detail URLs")

            # Fetch detail pages
            console.print("\n[bold]Stage 1b:[/bold] Fetching detail pages...")
            detail_urls = [link["url"] for link in detail_links]
            existing = get_existing_urls()
            new_detail_pages = fetch_detail_urls(detail_urls, existing)

            for page in new_detail_pages:
                save_raw_page(page.model_dump())
                mark_crawl_done(page.url)

            detail_pages.extend(new_detail_pages)
        else:
            console.print("[yellow][WARN][/yellow] No detail links from listing pages")

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages to process")
        return 0

    # === STAGE 2: Extract, score, dedupe, save ===
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process_details(detail_pages, min_score)

    # Export
    console.print("\n[bold]Exporting...[/bold]")
    export_all()

    console.rule("[bold green]Crawl Complete[/bold green]")
    console.print(f"\n Total saved: {saved} opportunities")

    return saved
