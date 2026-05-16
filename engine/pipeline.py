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
from rich.table import Table

from engine.models import RawPage
from engine.query_builder import build_queries_from_raw
from engine.searcher import search_all, search_manual_sources
from engine.fetcher import fetch_all, fetch_detail_urls
from engine.listing_parser import (
    extract_detail_links_from_listing,
    classify_page,
    detect_platform,
)
from engine.extractor import (
    TOP_LEVEL_CATEGORIES,
    ROLE_CATEGORY,
    ROLE_DISPLAY,
    TITLE_INTERNSHIP_SIGNALS,
    build_rejected_candidate,
    extract_all_with_rejections,
    load_keywords,
    normalize_target_category,
)
from engine.scorer import score_all
from engine.deduper import dedupe_opportunities
from engine.db import (
    save_raw_results,
    save_raw_page,
    save_crawl_queue,
    mark_crawl_done,
    save_opportunity,
    save_rejected_candidate,
    get_existing_urls,
    get_raw_pages_by_urls,
)
from engine.exporter import export_all

console = Console()


def _init_source_diagnostics(raw_results) -> dict[str, dict]:
    diagnostics = {}
    for result in raw_results:
        diagnostics[result.url] = {
            "name": result.title.replace("Manual source: ", ""),
            "platform": result.source_platform or detect_platform(result.url),
            "fetched": "no",
            "rendered": "-",
            "links": 0,
            "detail_ok": 0,
            "saved": 0,
            "rejected": 0,
        }
    return diagnostics


def _print_source_diagnostics(diagnostics: dict[str, dict]) -> None:
    if not diagnostics:
        return

    table = Table(title="Source Diagnostics", show_lines=False)
    table.add_column("Source", max_width=34)
    table.add_column("Platform", max_width=12)
    table.add_column("Fetched", justify="center", width=8)
    table.add_column("Rendered", justify="center", width=8)
    table.add_column("Links", justify="right", width=6)
    table.add_column("Details", justify="right", width=7)
    table.add_column("Saved", justify="right", width=6)
    table.add_column("Reject", justify="right", width=6)

    for item in diagnostics.values():
        table.add_row(
            item["name"][:34],
            item["platform"] or "-",
            item["fetched"],
            item["rendered"],
            str(item["links"]),
            str(item["detail_ok"]),
            str(item["saved"]),
            str(item["rejected"]),
        )

    console.print(table)


def _raw_page_from_dict(row: dict, force_page_type: Optional[str] = None) -> RawPage:
    """Build RawPage from cached DB row."""
    return RawPage(
        url=row["url"],
        title=row.get("title"),
        text_content=row.get("text_content") or "",
        html_content=row.get("html_content") or "",
        status_code=row.get("status_code") or 200,
        page_type=force_page_type or row.get("page_type") or "unknown",
        source_platform=row.get("source_platform"),
        fetch_method="cached",
    )


def _fetch_or_load_results(raw_results, workers: int, timeout: int) -> list[RawPage]:
    """Fetch uncached search/listing URLs and load cached pages for the rest."""
    urls = [result.url for result in raw_results]
    existing = get_existing_urls()
    cached_rows = get_raw_pages_by_urls([url for url in urls if url in existing])
    cached_pages = [_raw_page_from_dict(row) for row in cached_rows]
    if cached_pages:
        console.print(f"  [dim]Loaded {len(cached_pages)} cached pages[/dim]")

    fetched_pages = fetch_all(raw_results, existing, workers=workers, timeout=timeout)
    for page in fetched_pages:
        save_raw_page(page.model_dump())

    by_url = {page.url: page for page in cached_pages}
    by_url.update({page.url: page for page in fetched_pages})
    return [by_url[url] for url in urls if url in by_url]


def _fetch_or_load_detail_urls(urls: list[str], workers: int, timeout: int) -> list[RawPage]:
    """Fetch uncached detail URLs and load cached detail pages for the rest."""
    existing = get_existing_urls()
    cached_rows = get_raw_pages_by_urls([url for url in urls if url in existing])
    cached_pages = [_raw_page_from_dict(row, force_page_type="detail") for row in cached_rows]
    if cached_pages:
        console.print(f"  [dim]Loaded {len(cached_pages)} cached detail pages[/dim]")

    fetched_pages = fetch_detail_urls(urls, existing, workers=workers, timeout=timeout)
    for page in fetched_pages:
        save_raw_page(page.model_dump())

    by_url = {page.url: page for page in cached_pages}
    by_url.update({page.url: page for page in fetched_pages})
    pages = [by_url[url] for url in urls if url in by_url]
    for page in pages:
        mark_crawl_done(page.url)
    return pages


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


def _target_link_score(link: dict, target_category: Optional[str], config: Optional[dict] = None) -> int:
    """Score listing-card links for target-aware fetch priority before caps."""
    target = normalize_target_category(target_category)
    if not target:
        return 0

    config = config or load_keywords()
    text = f"{link.get('title') or ''} {link.get('url') or ''}".lower()
    if not text.strip():
        return 0

    role_keywords = config.get("role_keywords", {})
    candidate_role_keys: list[str] = []
    if target in TOP_LEVEL_CATEGORIES:
        for role_key, display in ROLE_DISPLAY.items():
            if ROLE_CATEGORY.get(display) == target:
                candidate_role_keys.append(role_key)
    else:
        candidate_role_keys.append(target)

    score = 0
    for role_key in candidate_role_keys:
        role_cfg = role_keywords.get(role_key, {})
        if not isinstance(role_cfg, dict):
            continue
        for strong in role_cfg.get("strong_titles", []):
            strong_text = str(strong).lower()
            if strong_text and strong_text in text:
                score += 100
        for supporting in role_cfg.get("supporting_skills", []):
            supporting_text = str(supporting).lower()
            if supporting_text and supporting_text in text:
                score += 15

    if target in text:
        score += 25
    return score


def _prioritize_target_links(links: list[dict], target_category: Optional[str]) -> list[dict]:
    """Move likely target-relevant links before caps without dropping others."""
    if not target_category or not links:
        return links

    config = load_keywords()
    indexed = [
        (_target_link_score(link, target_category, config), index, link)
        for index, link in enumerate(links)
    ]
    indexed.sort(key=lambda item: (-item[0], item[1]))
    top_matches = sum(1 for score, _, _ in indexed if score > 0)
    if top_matches:
        console.print(f"  [dim]Target priority: moved {top_matches} likely {normalize_target_category(target_category)} links up[/dim]")
    return [link for _, _, link in indexed]


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


def _stage2_process(
    detail_pages,
    min_score: int,
    target_category: Optional[str] = None,
    diagnostics: Optional[dict[str, dict]] = None,
    detail_source_map: Optional[dict[str, str]] = None,
) -> int:
    """Stage 2: Extract -> Score -> Dedupe -> Save."""
    console.print("\n[bold]Extracting opportunities...[/bold]")
    opportunities, rejections = extract_all_with_rejections(
        detail_pages,
        target_category=target_category,
    )

    saved_rejections = 0
    for rejection in rejections:
        if save_rejected_candidate(rejection.model_dump()):
            saved_rejections += 1
            if diagnostics is not None and detail_source_map is not None:
                source_url = detail_source_map.get(rejection.url)
                if source_url in diagnostics:
                    diagnostics[source_url]["rejected"] += 1
    if saved_rejections:
        console.print(f"  [dim]Saved {saved_rejections} rejected candidates for audit[/dim]")

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No opportunities extracted")
        return 0

    console.print("\n[bold]Scoring...[/bold]")
    opportunities = score_all(opportunities)
    low_score = [o for o in opportunities if o.score < min_score]
    for opp in low_score:
        rejection = build_rejected_candidate(
            page=RawPage(
                url=opp.source_url,
                title=opp.title,
                text_content=opp.raw_text or "",
                html_content="",
                status_code=200,
                page_type=opp.page_type,
                source_platform=opp.source_platform,
            ),
            reason="score_below_minimum",
            title=opp.title,
            text=opp.raw_text,
            internship_confidence=opp.internship_confidence,
            role_confidence=opp.role_confidence,
            score=opp.score,
        )
        save_rejected_candidate(rejection.model_dump())
        if diagnostics is not None and detail_source_map is not None:
            source_url = detail_source_map.get(opp.source_url)
            if source_url in diagnostics:
                diagnostics[source_url]["rejected"] += 1

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
            if diagnostics is not None and detail_source_map is not None:
                source_url = detail_source_map.get(opp.source_url)
                if source_url in diagnostics:
                    diagnostics[source_url]["saved"] += 1

    console.print(f"[green][OK][/green] Saved {saved} opportunities")
    return saved


def run_crawl_sources(
    min_score: int = 40,
    max_sources: int = 8,
    max_per_source: int = 10,
    max_total_detail: int = 60,
    workers: int = 6,
    timeout: int = 10,
    target_category: Optional[str] = None,
) -> int:
    """
    Crawl dari manual sources — 2-stage dengan limits.
    """
    console.rule("[bold cyan]MagangKareer Source Crawl[/bold cyan]")

    # --- Step 1: Load sources ---
    console.print("\n[bold]Step 1:[/bold] Loading sources...")
    raw_results = search_manual_sources(target_category=target_category)
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
    diagnostics = _init_source_diagnostics(raw_results)
    detail_source_map: dict[str, str] = {}

    # --- Step 2: Fetch listing pages ---
    console.print(f"\n[bold]Step 2:[/bold] Fetching listings ({workers} workers, {timeout}s timeout)...")
    pages = _fetch_or_load_results(raw_results, workers=workers, timeout=timeout)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched or cached")
        _print_source_diagnostics(diagnostics)
        return 0

    for page in pages:
        if page.url in diagnostics:
            diagnostics[page.url]["fetched"] = "ok"
            diagnostics[page.url]["rendered"] = "yes" if page.fetch_method == "playwright" else page.fetch_method or "-"

    # --- Stage 1: Extract detail links ---
    listing_pages = [p for p in pages if p.page_type == "listing"]
    detail_pages = [p for p in pages if p.page_type != "listing"]

    console.print(f"\n[bold]Stage 1:[/bold] Parsing {len(listing_pages)} listings...")

    all_links = []
    for page in listing_pages:
        links = extract_detail_links_from_listing(page.url, page.html_content)
        if page.url in diagnostics:
            diagnostics[page.url]["links"] = len(links)
        for link in links:
            link_data = link.model_dump()
            detail_source_map[link_data["url"]] = page.url
            all_links.append(link_data)

    if all_links:
        # Prioritize target-relevant cards before per-source and total caps.
        all_links = _prioritize_target_links(all_links, target_category)

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
        new_pages = _fetch_or_load_detail_urls(detail_urls, workers=workers, timeout=timeout)
        for page in new_pages:
            source_url = detail_source_map.get(page.url)
            if source_url in diagnostics:
                diagnostics[source_url]["detail_ok"] += 1

        detail_pages.extend(new_pages)
    else:
        console.print("[yellow][WARN][/yellow] No detail links found")

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages")
        _print_source_diagnostics(diagnostics)
        return 0

    # --- Stage 2: Extract, Score, Dedupe, Save ---
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process(
        detail_pages,
        min_score,
        target_category=target_category,
        diagnostics=diagnostics,
        detail_source_map=detail_source_map,
    )
    _print_source_diagnostics(diagnostics)

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
    target_category: Optional[str] = None,
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
    raw_results = search_all(queries, limit, target_category=target_category)
    if not raw_results:
        console.print("[yellow][WARN][/yellow] No results")
        return 0

    for r in raw_results:
        r.page_type = classify_page(r.url, r.title)
        r.source_platform = detect_platform(r.url)

    save_raw_results([r.model_dump() for r in raw_results])

    # Step 3: Fetch
    console.print(f"\n[bold]Step 3:[/bold] Fetching ({workers} workers, {timeout}s timeout)...")
    pages = _fetch_or_load_results(raw_results, workers=workers, timeout=timeout)

    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched or cached")
        return 0

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
            all_links = _prioritize_target_links(all_links, target_category)
            all_links = _cap_links_per_source(all_links, max_per_source)
            all_links = _early_filter_links(all_links)
            if len(all_links) > max_total_detail:
                all_links = all_links[:max_total_detail]

            save_crawl_queue(all_links)

            console.print(f"\n[bold]Stage 1b:[/bold] Fetching {len(all_links)} details...")
            detail_urls = [link["url"] for link in all_links]
            new_pages = _fetch_or_load_detail_urls(detail_urls, workers=workers, timeout=timeout)

            detail_pages.extend(new_pages)

    if not detail_pages:
        console.print("[yellow][WARN][/yellow] No detail pages")
        return 0

    # Stage 2
    console.print(f"\n[bold]Stage 2:[/bold] Processing {len(detail_pages)} detail pages...")
    saved = _stage2_process(detail_pages, min_score, target_category=target_category)

    console.print("\n[bold]Exporting...[/bold]")
    export_all()

    console.rule("[bold green]Done[/bold green]")
    console.print(f"\n Saved: {saved} opportunities")
    return saved
