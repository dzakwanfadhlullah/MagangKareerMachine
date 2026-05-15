"""Pipeline — orchestrator 2-stage dengan limits dan early filtering.

Alur:
1. Listing URLs -> fetch listing pages
2. Extract detail links (max per source)
3. Early filter: skip non-internship titles
4. Cap total detail URLs
5. Concurrent fetch detail pages
6. Extract -> Score -> Dedupe -> Save -> Export
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
from engine.extractor import extract_all, TITLE_INTERNSHIP_SIGNALS
from engine.scorer import score_all
from engine.deduper import dedupe_opportunities
from engine.db import (
    save_raw_results,
    save_raw_page,
    save_crawl_queue,
    mark_crawl_done,
    save_opportunity,
    get_existing_urls,
)
from engine.exporter import export_all

console = Console()


def _early_filter_links(links: list[dict]) -> list[dict]:
    """
    Soft filter sebelum fetch.
    Hanya SKIP jika title jelas bukan internship (senior/manager/director).
    Sisanya lolos — extractor internship gate yang menentukan final.
    """
    # Title yang JELAS bukan internship — skip langsung
    NON_INTERN_SIGNALS = [
        "senior", "manager", "director", "head of", "lead ",
        "supervisor", "principal", "vp ", "vice president",
        "chief ", "c-level",
    ]

    filtered = []
    skipped = 0

    for link in links:
        title = (link.get("title") or "").lower()

        # Kalau tidak ada title, loloskan
        if not title:
            filtered.append(link)
            continue

        # Jika title mengandung sinyal intern, pasti lolos
        has_intern = any(s in title for s in TITLE_INTERNSHIP_SIGNALS)
        if has_intern:
            filtered.append(link)
            continue

        # Jika title jelas non-intern, skip
        is_senior = any(s in title for s in NON_INTERN_SIGNALS)
        if is_senior:
            skipped += 1
            continue

        # Sisanya: beri kesempatan (extractor internship gate will decide)
        filtered.append(link)

    if skipped > 0:
        console.print(f"  [dim]Early filter: skipped {skipped} senior/management links[/dim]")

    return filtered


def _cap_links_per_source(links: list[dict], max_per_source: int) -> list[dict]:
    """Batasi jumlah links per source_platform."""
    counts: dict[str, int] = {}
    capped = []

    for link in links:
        platform = link.get("source_platform", "unknown")
        current = counts.get(platform, 0)
        if current < max_per_source:
            capped.append(link)
            counts[platform] = current + 1

    total_before = len(links)
    total_after = len(capped)
    if total_before > total_after:
        console.print(f"  [dim]Capped: {total_before} -> {total_after} (max {max_per_source}/source)[/dim]")

    return capped


def _stage2_process(detail_pages, min_score: int) -> int:
    """Stage 2: Extract -> Score -> Dedupe -> Save."""
    console.print("\n[bold]Extracting opportunities...[/bold]")
    opportunities = extract_all(detail_pages)

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities extracted")
        return 0

    console.print("\n[bold]Scoring...[/bold]")
    opportunities = score_all(opportunities)
    opportunities = [o for o in opportunities if o.score >= min_score]
    console.print(f"  {len(opportunities)} with score >= {min_score}")

    if not opportunities:
        return 0

    console.print("\n[bold]Deduplicating...[/bold]")
    opportunities = dedupe_opportunities(opportunities)

    console.print("\n[bold]Saving...[/bold]")
    saved = 0
    for opp in opportunities:
        if save_opportunity(opp.model_dump()):
            saved += 1

    console.print(f"[green][OK][/green] Saved {saved} opportunities")
    return saved


def run_crawl_sources(
    min_score: int = 40,
    max_sources: int = 7,
    max_per_source: int = 10,
    max_total_detail: int = 30,
    workers: int = 5,
    timeout: int = 10,
) -> int:
    """
    Crawl dari manual sources — 2-stage dengan limits.
    """
    console.rule("[bold cyan]MagangKareer Source Crawl[/bold cyan]")

    # --- Step 1: Load sources ---
    console.print("\n[bold]Step 1:[/bold] Loading sources...")
    raw_results = search_manual_sources()
    if not raw_results:
        console.print("[yellow][WARN][/yellow] No sources")
        return 0

    # Limit sources
    raw_results = raw_results[:max_sources]
    for r in raw_results:
        r.page_type = classify_page(r.url, r.title)
        r.source_platform = detect_platform(r.url)

    save_raw_results([r.model_dump() for r in raw_results])
    console.print(f"  Using {len(raw_results)} sources (max {max_sources})")

    # --- Step 2: Fetch listing pages ---
    console.print(f"\n[bold]Step 2:[/bold] Fetching listings ({workers} workers, {timeout}s timeout)...")
    existing = get_existing_urls()
    pages = fetch_all(raw_results, existing, workers=workers, timeout=timeout)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    for page in pages:
        save_raw_page(page.model_dump())

    # --- Stage 1: Extract detail links ---
    listing_pages = [p for p in pages if p.page_type == "listing"]
    detail_pages = [p for p in pages if p.page_type != "listing"]

    console.print(f"\n[bold]Stage 1:[/bold] Parsing {len(listing_pages)} listings...")

    all_links = []
    for page in listing_pages:
        links = extract_detail_links_from_listing(page.url, page.html_content)
        for link in links:
            all_links.append(link.model_dump())

    if all_links:
        # Cap per source
        all_links = _cap_links_per_source(all_links, max_per_source)

        # Early filter: skip non-internship
        all_links = _early_filter_links(all_links)

        # Cap total
        if len(all_links) > max_total_detail:
            console.print(f"  [dim]Total cap: {len(all_links)} -> {max_total_detail}[/dim]")
            all_links = all_links[:max_total_detail]

        console.print(f"[green][OK][/green] {len(all_links)} detail URLs to fetch")

        saved_queue = save_crawl_queue(all_links)

        # Fetch details — concurrent
        console.print(f"\n[bold]Stage 1b:[/bold] Fetching details ({workers} workers)...")
        detail_urls = [link["url"] for link in all_links]
        existing = get_existing_urls()
        new_pages = fetch_detail_urls(detail_urls, existing, workers=workers, timeout=timeout)

        for page in new_pages:
            save_raw_page(page.model_dump())
            mark_crawl_done(page.url)

        detail_pages.extend(new_pages)
    else:
        console.print("[yellow][WARN][/yellow] No detail links found")

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages")
        return 0

    # --- Stage 2: Extract, Score, Dedupe, Save ---
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process(detail_pages, min_score)

    console.print("\n[bold]Exporting...[/bold]")
    export_all()

    console.rule("[bold green]Done[/bold green]")
    console.print(f"\n Saved: {saved} opportunities")
    return saved


def run_search_pipeline(
    query: str,
    location: str = "Indonesia",
    limit: int = 20,
    min_score: int = 40,
    max_per_source: int = 10,
    max_total_detail: int = 30,
    workers: int = 5,
    timeout: int = 10,
    query_limit: int = 3,
) -> int:
    """Pipeline pencarian lengkap — 2-stage dengan limits."""
    console.rule("[bold cyan]MagangKareer Search Pipeline[/bold cyan]")

    # Step 1: Build queries
    console.print("\n[bold]Step 1:[/bold] Building queries...")
    queries = build_queries_from_raw(query, location)
    queries = queries[:query_limit]
    console.print(f"  Using {len(queries)} queries (max {query_limit})")

    # Step 2: Search
    console.print("\n[bold]Step 2:[/bold] Searching...")
    raw_results = search_all(queries, limit)
    if not raw_results:
        console.print("[yellow][WARN][/yellow] No results")
        return 0

    for r in raw_results:
        r.page_type = classify_page(r.url, r.title)
        r.source_platform = detect_platform(r.url)

    save_raw_results([r.model_dump() for r in raw_results])

    # Step 3: Fetch
    console.print(f"\n[bold]Step 3:[/bold] Fetching ({workers} workers, {timeout}s timeout)...")
    existing = get_existing_urls()
    pages = fetch_all(raw_results, existing, workers=workers, timeout=timeout)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        return 0

    for page in pages:
        save_raw_page(page.model_dump())

    # Stage 1: Extract detail links from listings
    listing_pages = [p for p in pages if p.page_type == "listing"]
    detail_pages = [p for p in pages if p.page_type != "listing"]

    if listing_pages:
        console.print(f"\n[bold]Stage 1:[/bold] Parsing {len(listing_pages)} listings...")
        all_links = []
        for page in listing_pages:
            links = extract_detail_links_from_listing(page.url, page.html_content)
            all_links.extend(link.model_dump() for link in links)

        if all_links:
            all_links = _cap_links_per_source(all_links, max_per_source)
            all_links = _early_filter_links(all_links)
            if len(all_links) > max_total_detail:
                all_links = all_links[:max_total_detail]

            save_crawl_queue(all_links)

            console.print(f"\n[bold]Stage 1b:[/bold] Fetching {len(all_links)} details...")
            detail_urls = [link["url"] for link in all_links]
            existing = get_existing_urls()
            new_pages = fetch_detail_urls(detail_urls, existing, workers=workers, timeout=timeout)

            for page in new_pages:
                save_raw_page(page.model_dump())
                mark_crawl_done(page.url)

            detail_pages.extend(new_pages)

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages")
        return 0

    # Stage 2
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process(detail_pages, min_score)

    console.print("\n[bold]Exporting...[/bold]")
    export_all()

    console.rule("[bold green]Done[/bold green]")
    console.print(f"\n Saved: {saved} opportunities")
    return saved
