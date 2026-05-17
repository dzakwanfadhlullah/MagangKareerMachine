"""Fast research pipeline: search-index-first discovery then core extraction."""

from collections import Counter
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
from engine.fetcher import fetch_all, fetch_detail_urls
from engine.listing_parser import classify_page, detect_platform, extract_detail_links_from_listing
from engine.models import DetailLink, RawPage, RawSearchResult
from engine.research.page_verifier import verify_research_page
from engine.research.profiles import get_research_profile
from engine.research.query_planner import plan_research_queries
from engine.research.search_provider import SearchProvider, search_queries_parallel
from engine.research.url_ranker import rank_research_results, score_research_url
from engine.scorer import score_all
from engine.url_utils import canonicalize_url

console = Console()

FOLLOWUP_PLATFORM_MIN_QUOTA = 3
JOBSTREET_SYNTHETIC_INTERNSHIP_TERMS = ("intern", "internship", "magang", "apprentice", "trainee", "ojt", "pkl")

PLATFORM_QUERY_MARKERS = {
    "dealls": "site:dealls.com",
    "glints": "site:glints.com",
    "kalibrr": "site:kalibrr",
    "jobstreet": "site:jobstreet",
    "prosple": "site:prosple",
    "prosple_id": "site:id.prosple",
    "suitmedia": "site:suitmedia",
    "deloitte": "site:jobs.sea.deloitte",
}

FOCUS_PLATFORMS = ("dealls", "kalibrr", "jobstreet", "prosple")

RESEARCH_SEEDS = {
    "tech": [
        ("dealls", "https://dealls.com/loker/tipe/loker-magang", "Dealls magang listing"),
        ("dealls", "https://dealls.com/loker", "Dealls loker listing"),
        ("kalibrr", "https://www.kalibrr.id/id-ID/home/w/100-internship-or-ojt", "Kalibrr internship OJT listing"),
        ("kalibrr", "https://www.kalibrr.id/id-ID/job-board", "Kalibrr job board"),
        ("prosple", "https://id.prosple.com/lowongan-magang-indonesia", "Prosple internship Indonesia"),
    ],
    "data": [
        ("dealls", "https://dealls.com/loker/tipe/loker-magang", "Dealls magang listing"),
        ("kalibrr", "https://www.kalibrr.id/id-ID/home/w/100-internship-or-ojt", "Kalibrr internship OJT listing"),
        ("prosple", "https://id.prosple.com/lowongan-magang-indonesia", "Prosple internship Indonesia"),
    ],
    "actuarial": [
        ("dealls", "https://dealls.com/loker/tipe/loker-magang", "Dealls magang listing"),
        ("kalibrr", "https://www.kalibrr.id/id-ID/home/w/100-internship-or-ojt", "Kalibrr internship OJT listing"),
        ("prosple", "https://id.prosple.com/lowongan-magang-indonesia", "Prosple internship Indonesia"),
    ],
}


def _platform_counts(items) -> dict[str, int]:
    counter = Counter()
    for item in items:
        if isinstance(item, dict):
            platform = item.get("source_platform")
        else:
            platform = getattr(item, "source_platform", None)
        counter[platform or "unknown"] += 1
    return dict(counter)


def _platforms_from_queries(queries: list[str]) -> list[str]:
    platforms = []
    for query in queries:
        lowered = query.lower()
        for platform, marker in PLATFORM_QUERY_MARKERS.items():
            platform_name = "prosple" if platform == "prosple_id" else platform
            if marker in lowered and platform_name not in platforms:
                platforms.append(platform_name)
    return platforms


def _seed_research_results(
    *,
    query: Optional[str],
    location: str,
    target_category: Optional[str],
) -> list[RawSearchResult]:
    """Add deterministic platform listing seeds so search-index flakiness does not hide core sources."""
    target = normalize_target_category(target_category) or "tech"
    seed_defs = RESEARCH_SEEDS.get(target, RESEARCH_SEEDS["tech"])
    seed_text = " ".join(part for part in [query, target, location, "intern internship magang"] if part)
    return [
        RawSearchResult(
            query=f"seed:{platform}:{target}",
            title=title,
            snippet=seed_text,
            url=url,
            source="seed",
            page_type="listing",
            source_platform=platform,
        )
        for platform, url, title in seed_defs
    ]


def _nested_reason_counts(reason_counter: Counter) -> dict[str, dict[str, int]]:
    nested: dict[str, dict[str, int]] = {}
    for key, count in reason_counter.items():
        platform, reason = key.split("|", 1)
        nested.setdefault(platform, {})[reason] = count
    return nested


def _fetch_failures_by_platform(selected_results: list[RawSearchResult], pages: list[RawPage]) -> dict[str, int]:
    fetched_urls = {page.url for page in pages}
    selected_by_platform = Counter((result.source_platform or detect_platform(result.url) or "unknown") for result in selected_results)
    fetched_by_platform = Counter((page.source_platform or detect_platform(page.url) or "unknown") for page in pages)
    failures = {}
    for platform, selected_count in selected_by_platform.items():
        missing = selected_count - fetched_by_platform.get(platform, 0)
        if missing > 0:
            failures[platform] = missing
    return failures


def _focus_platform_diagnostics(
    *,
    search_results: list[RawSearchResult],
    ranked_results: list[RawSearchResult],
    initial_pages: list[RawPage],
    followup_results: list[RawSearchResult],
    followup_pages: list[RawPage],
    verified_pages: list[RawPage],
    opportunities,
    rejected_counter: Counter,
    rejection_reason_counter: Counter,
    initial_fetch_failures: dict[str, int],
    followup_fetch_failures: dict[str, int],
) -> dict[str, dict]:
    diagnostics = {}
    raw_counts = _platform_counts(search_results)
    selected_counts = _platform_counts(ranked_results)
    initial_counts = _platform_counts(initial_pages)
    followup_selected_counts = _platform_counts(followup_results)
    followup_fetched_counts = _platform_counts(followup_pages)
    verified_counts = _platform_counts(verified_pages)
    accepted_counts = _platform_counts(opportunities)
    reason_counts = _nested_reason_counts(rejection_reason_counter)
    for platform in FOCUS_PLATFORMS:
        diagnostics[platform] = {
            "raw_hits": raw_counts.get(platform, 0),
            "selected_urls": selected_counts.get(platform, 0),
            "initial_fetched": initial_counts.get(platform, 0),
            "initial_fetch_failed": initial_fetch_failures.get(platform, 0),
            "followup_selected": followup_selected_counts.get(platform, 0),
            "followup_fetched": followup_fetched_counts.get(platform, 0),
            "followup_fetch_failed": followup_fetch_failures.get(platform, 0),
            "verified_pages": verified_counts.get(platform, 0),
            "accepted": accepted_counts.get(platform, 0),
            "rejected": rejected_counter.get(platform, 0),
            "rejection_reasons": reason_counts.get(platform, {}),
        }
    return diagnostics


def _select_followup_results_with_quota(
    results: list[RawSearchResult],
    target_category: Optional[str],
    max_urls: int,
) -> list[RawSearchResult]:
    """Rank follow-up detail URLs while preventing one platform from consuming all slots."""
    if max_urls <= 0:
        return []

    grouped: dict[str, list[tuple[int, RawSearchResult]]] = {}
    for result in results:
        score = score_research_url(result, target_category=target_category)
        if score < 0:
            continue
        result.snippet = f"{result.snippet or ''}\nresearch_url_score={score}".strip()
        platform = result.source_platform or detect_platform(result.url) or "unknown"
        grouped.setdefault(platform, []).append((score, result))

    for items in grouped.values():
        items.sort(key=lambda item: item[0], reverse=True)

    if not grouped:
        return []

    platforms = sorted(grouped, key=lambda platform: len(grouped[platform]), reverse=True)
    per_platform_limit = max(FOLLOWUP_PLATFORM_MIN_QUOTA, (max_urls + len(platforms) - 1) // len(platforms))
    selected: list[RawSearchResult] = []
    selected_urls = set()

    made_progress = True
    while len(selected) < max_urls and made_progress:
        made_progress = False
        for platform in platforms:
            platform_selected = sum(1 for item in selected if (item.source_platform or detect_platform(item.url)) == platform)
            if platform_selected >= per_platform_limit:
                continue
            while grouped[platform]:
                _, candidate = grouped[platform].pop(0)
                if candidate.url in selected_urls:
                    continue
                selected.append(candidate)
                selected_urls.add(candidate.url)
                made_progress = True
                break
            if len(selected) >= max_urls:
                break

    for platform in platforms:
        while grouped[platform] and len(selected) < max_urls:
            _, candidate = grouped[platform].pop(0)
            if candidate.url in selected_urls:
                continue
            selected.append(candidate)
            selected_urls.add(candidate.url)

    return selected


def _build_research_metadata(
    *,
    query: Optional[str],
    location: str,
    target_category: Optional[str],
    profile: str,
    min_score: int,
    search_provider: str,
    queries: list[str],
    search_results: list[RawSearchResult],
    ranked_results: list[RawSearchResult],
    initial_pages: list[RawPage],
    followup_discovered_urls: int,
    followup_pages: list[RawPage],
    verified_pages: list[RawPage],
    opportunities,
    rejected_counter: Counter,
    rejection_reason_counter: Counter,
    initial_fetch_failures: dict[str, int],
    followup_results: list[RawSearchResult],
    followup_fetch_failures: dict[str, int],
    synthetic_pages: list[RawPage],
    workers: int,
    timeout: int,
) -> dict:
    accepted_by_platform = Counter(opp.source_platform or "unknown" for opp in opportunities)
    accepted_full_detail_by_platform = Counter(
        opp.source_platform or "unknown"
        for opp in opportunities
        if getattr(opp, "extraction_depth", None) == "full_detail"
    )
    accepted_partial_by_platform = Counter(
        opp.source_platform or "unknown"
        for opp in opportunities
        if getattr(opp, "extraction_depth", None) != "full_detail"
    )
    followup_urls = {page.url for page in followup_pages}
    followup_verified_pages = [
        page for page in verified_pages
        if page.url in followup_urls
    ]
    platforms_with_hits = sorted({
        result.source_platform or "unknown"
        for result in search_results
    })
    platforms_seeded = sorted({
        result.source_platform or "unknown"
        for result in search_results
        if result.source == "seed"
    })
    accepted_platforms = [platform for platform, count in accepted_by_platform.items() if count > 0]

    return {
        "command": "research",
        "search_provider": search_provider,
        "query": query,
        "location": location,
        "target_category": target_category,
        "profile": profile,
        "min_score": min_score,
        "query_count": len(queries),
        "platforms_queried": _platforms_from_queries(queries),
        "platforms_seeded": platforms_seeded,
        "platforms_with_hits": platforms_with_hits,
        "raw_results_by_platform": _platform_counts(search_results),
        "selected_urls_by_platform": _platform_counts(ranked_results),
        "initial_fetched_pages": len(initial_pages),
        "initial_fetched_pages_by_platform": _platform_counts(initial_pages),
        "followup_discovered_urls": followup_discovered_urls,
        "followup_selected_urls": len(followup_results),
        "followup_selected_urls_by_platform": _platform_counts(followup_results),
        "followup_fetched_pages": len(followup_pages),
        "followup_fetched_pages_by_platform": _platform_counts(followup_pages),
        "followup_verified_pages": len(followup_verified_pages),
        "followup_verified_pages_by_platform": _platform_counts(followup_verified_pages),
        "synthetic_verified_pages": len(synthetic_pages),
        "synthetic_verified_pages_by_platform": _platform_counts(synthetic_pages),
        "verified_pages": len(verified_pages),
        "verified_pages_by_platform": _platform_counts(verified_pages),
        "accepted_results": len(opportunities),
        "accepted_by_platform": dict(accepted_by_platform),
        "accepted_full_detail_by_platform": dict(accepted_full_detail_by_platform),
        "accepted_partial_by_platform": dict(accepted_partial_by_platform),
        "rejected_candidates": sum(rejected_counter.values()),
        "rejected_by_platform": dict(rejected_counter),
        "rejection_reasons_by_platform": _nested_reason_counts(rejection_reason_counter),
        "initial_fetch_failed_by_platform": initial_fetch_failures,
        "followup_fetch_failed_by_platform": followup_fetch_failures,
        "source_diversity_warning": len(accepted_platforms) == 1,
        "full_detail_source_diversity_warning": len(accepted_full_detail_by_platform) <= 1 and len(opportunities) > 1,
        "focus_platform_diagnostics": _focus_platform_diagnostics(
            search_results=search_results,
            ranked_results=ranked_results,
            initial_pages=initial_pages,
            followup_results=followup_results,
            followup_pages=followup_pages,
            verified_pages=verified_pages,
            opportunities=opportunities,
            rejected_counter=rejected_counter,
            rejection_reason_counter=rejection_reason_counter,
            initial_fetch_failures=initial_fetch_failures,
            followup_fetch_failures=followup_fetch_failures,
        ),
        "searched_urls": len(search_results),
        "selected_urls": len(ranked_results),
        "fetched_pages": len(initial_pages) + len(followup_pages),
        "workers": workers,
        "timeout": timeout,
    }


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
    ordered = [by_url[url] for url in urls if url in by_url]
    requested = {page.url for page in ordered}
    ordered.extend(page for page in fetched_pages if page.url not in requested)
    return ordered


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


def _save_detail_link_candidates(links: list[DetailLink], target_category: Optional[str]) -> None:
    target = normalize_target_category(target_category)
    candidates = []
    for link in links:
        row = link.model_dump()
        row["target_category"] = target
        row["status"] = "discovered"
        candidates.append(row)
    save_discovery_candidates(candidates)


def _detail_links_to_search_results(links: list[DetailLink]) -> list[RawSearchResult]:
    results = []
    best_by_key: dict[str, DetailLink] = {}

    def detail_key(link: DetailLink) -> str:
        if (link.source_platform or detect_platform(link.url)) == "jobstreet":
            import re
            match = re.search(r"/(?:id/)?job/(\d+)", link.url)
            if match:
                return f"jobstreet:{match.group(1)}"
        return canonicalize_url(link.url)

    def richness(link: DetailLink) -> int:
        return (
            (30 if link.company else 0)
            + (20 if link.title else 0)
            + (10 if link.discovery_method == "card" else 0)
        )

    for link in links:
        key = detail_key(link)
        current = best_by_key.get(key)
        if current is None or richness(link) > richness(current):
            best_by_key[key] = link

    for link in best_by_key.values():
        snippet_parts = ["detail link discovered from research listing"]
        if link.company:
            snippet_parts.append(f"Company: {link.company}")
        results.append(RawSearchResult(
            query=f"listing-followup:{link.listing_url}",
            title=link.title or "",
            snippet="\n".join(snippet_parts),
            url=link.url,
            source=link.discovery_method,
            page_type="detail",
            source_platform=link.source_platform or detect_platform(link.url),
        ))
    return results


def _build_jobstreet_card_fallback_page(result: RawSearchResult) -> Optional[RawPage]:
    """Build a conservative Jobstreet detail page from listing-card metadata.

    Jobstreet sometimes renders a generic search shell for direct detail URLs in
    anonymous Playwright sessions. If the listing card already provides a direct
    detail URL plus an explicit internship title, keep that as a low-scope
    verified page so the normal extractor/filter/scorer still decides.
    """
    if (result.source_platform or detect_platform(result.url)) != "jobstreet":
        return None
    title = (result.title or "").strip()
    title_lower = title.lower()
    if not title or not any(term in title_lower for term in JOBSTREET_SYNTHETIC_INTERNSHIP_TERMS):
        return None
    text = "\n".join(part for part in [
        title,
        result.snippet or "",
        "Source: Jobstreet listing card",
        "Status: active or listed in current search results",
    ] if part).strip()
    return RawPage(
        url=result.url,
        title=title,
        text_content=text,
        html_content="",
        status_code=200,
        page_type="detail",
        source_platform="jobstreet",
        fetch_method="jobstreet-card-fallback",
    )


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
    active_provider = provider
    provider_label = getattr(active_provider, "name", "auto") if active_provider else "auto"

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
        provider=active_provider,
        max_results_per_query=results_per_query,
        workers=workers,
    )
    if not search_results:
        console.print("[yellow][WARN][/yellow] No search results")
        export_all(metadata=_build_research_metadata(
            query=query,
            location=location,
            target_category=target_category,
            profile=profile,
            min_score=min_score,
            search_provider=provider_label,
            queries=queries,
            search_results=[],
            ranked_results=[],
            initial_pages=[],
            followup_discovered_urls=0,
            followup_pages=[],
            verified_pages=[],
            opportunities=[],
            rejected_counter=Counter(),
            rejection_reason_counter=Counter(),
            initial_fetch_failures={},
            followup_results=[],
            followup_fetch_failures={},
            synthetic_pages=[],
            workers=workers,
            timeout=timeout,
        ))
        return 0

    for result in search_results:
        result.page_type = result.page_type if result.page_type in {"listing", "detail"} else classify_page(result.url, result.title)
        result.source_platform = result.source_platform or detect_platform(result.url)
    seed_results = _seed_research_results(query=query, location=location, target_category=target_category)
    seen_search_urls = {result.url for result in search_results}
    for seed in seed_results:
        if seed.url not in seen_search_urls:
            search_results.append(seed)
            seen_search_urls.add(seed.url)
    if seed_results:
        console.print(f"[cyan][INFO][/cyan] Added {len(seed_results)} deterministic platform seed URLs")
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
        export_all(metadata=_build_research_metadata(
            query=query,
            location=location,
            target_category=target_category,
            profile=profile,
            min_score=min_score,
            search_provider=provider_label,
            queries=queries,
            search_results=search_results,
            ranked_results=ranked_results,
            initial_pages=[],
            followup_discovered_urls=0,
            followup_pages=[],
            verified_pages=[],
            opportunities=[],
            rejected_counter=Counter(),
            rejection_reason_counter=Counter(),
            initial_fetch_failures={},
            followup_results=[],
            followup_fetch_failures={},
            synthetic_pages=[],
            workers=workers,
            timeout=timeout,
        ))
        return 0

    console.print(f"\n[bold]Step 4:[/bold] Fetching top URLs ({workers} workers, {timeout}s timeout)...")
    pages = _fetch_or_load_research_results(ranked_results, workers=workers, timeout=timeout)
    initial_fetch_failures = _fetch_failures_by_platform(ranked_results, pages)
    if not pages:
        console.print("[yellow][WARN][/yellow] No pages fetched")
        export_all(metadata=_build_research_metadata(
            query=query,
            location=location,
            target_category=target_category,
            profile=profile,
            min_score=min_score,
            search_provider=provider_label,
            queries=queries,
            search_results=search_results,
            ranked_results=ranked_results,
            initial_pages=[],
            followup_discovered_urls=0,
            followup_pages=[],
            verified_pages=[],
            opportunities=[],
            rejected_counter=Counter(),
            rejection_reason_counter=Counter(),
            initial_fetch_failures=initial_fetch_failures,
            followup_results=[],
            followup_fetch_failures={},
            synthetic_pages=[],
            workers=workers,
            timeout=timeout,
        ))
        return 0

    console.print("\n[bold]Step 5:[/bold] Verifying pages...")
    verified_pages = []
    listing_detail_links: list[DetailLink] = []
    followup_pages: list[RawPage] = []
    followup_results: list[RawSearchResult] = []
    synthetic_pages: list[RawPage] = []
    followup_fetch_failures: dict[str, int] = {}
    rejected_counter: Counter = Counter()
    rejection_reason_counter: Counter = Counter()
    rejected_count = 0
    for page in pages:
        rejection = verify_research_page(page)
        if rejection:
            if rejection.rejection_reason == "listing_or_category_url" and page.html_content:
                listing_detail_links.extend(extract_detail_links_from_listing(page.url, page.html_content))
            if save_rejected_candidate(rejection.model_dump()):
                rejected_count += 1
                rejected_counter[rejection.source_platform or "unknown"] += 1
                rejection_reason_counter[f"{rejection.source_platform or 'unknown'}|{rejection.rejection_reason}"] += 1
            continue
        page.page_type = "detail"
        verified_pages.append(page)
    console.print(f"[green][OK][/green] Verified {len(verified_pages)} detail pages; rejected {rejected_count}")

    if listing_detail_links:
        console.print(
            f"  [cyan][INFO][/cyan] Found {len(listing_detail_links)} follow-up detail links "
            "inside rejected listing pages"
        )
        _save_detail_link_candidates(listing_detail_links, target_category)
        followup_results = _select_followup_results_with_quota(
            _detail_links_to_search_results(listing_detail_links),
            target_category=target_category,
            max_urls=max(max_fetch // 2, max(0, max_fetch - len(pages))),
        )
        if followup_results:
            followup_urls = [result.url for result in followup_results]
            followup_pages = fetch_detail_urls(
                followup_urls,
                existing_urls=get_existing_urls(),
                workers=workers,
                timeout=timeout,
            )
            followup_fetch_failures = _fetch_failures_by_platform(followup_results, followup_pages)
            for page in followup_pages:
                save_raw_page(page.model_dump())
                if page.api_responses:
                    save_raw_api_responses([item.model_dump() for item in page.api_responses])

            followup_by_url = {result.url: result for result in followup_results}
            followup_verified_count = 0
            for page in followup_pages:
                rejection = verify_research_page(page)
                if rejection:
                    result = followup_by_url.get(page.url)
                    fallback_page = (
                        _build_jobstreet_card_fallback_page(result)
                        if result and rejection.rejection_reason == "listing_or_category_url"
                        else None
                    )
                    if fallback_page and not verify_research_page(fallback_page):
                        verified_pages.append(fallback_page)
                        synthetic_pages.append(fallback_page)
                        followup_verified_count += 1
                        continue
                    if save_rejected_candidate(rejection.model_dump()):
                        rejected_count += 1
                        rejected_counter[rejection.source_platform or "unknown"] += 1
                        rejection_reason_counter[f"{rejection.source_platform or 'unknown'}|{rejection.rejection_reason}"] += 1
                    continue
                page.page_type = "detail"
                verified_pages.append(page)
                followup_verified_count += 1
            console.print(f"  [green][OK][/green] Verified {followup_verified_count} follow-up detail pages")
            if synthetic_pages:
                console.print(
                    f"  [yellow][INFO][/yellow] Added {len(synthetic_pages)} Jobstreet card fallback pages"
                )

    console.print("\n[bold]Step 6:[/bold] Extracting and filtering...")
    opportunities, rejections = extract_all_with_rejections(
        verified_pages,
        target_category=target_category,
    )
    saved_rejections = 0
    for rejection in rejections:
        if save_rejected_candidate(rejection.model_dump()):
            saved_rejections += 1
            rejected_counter[rejection.source_platform or "unknown"] += 1
            rejection_reason_counter[f"{rejection.source_platform or 'unknown'}|{rejection.rejection_reason}"] += 1
    if saved_rejections:
        console.print(f"  [dim]Saved {saved_rejections} rejected candidates for audit[/dim]")

    if not opportunities:
        console.print("[yellow][WARN][/yellow] No accepted opportunities")
        export_all(metadata=_build_research_metadata(
            query=query,
            location=location,
            target_category=target_category,
            profile=profile,
            min_score=min_score,
            search_provider=provider_label,
            queries=queries,
            search_results=search_results,
            ranked_results=ranked_results,
            initial_pages=pages,
            followup_discovered_urls=len(listing_detail_links),
            followup_pages=followup_pages,
            verified_pages=verified_pages,
            opportunities=[],
            rejected_counter=rejected_counter,
            rejection_reason_counter=rejection_reason_counter,
            initial_fetch_failures=initial_fetch_failures,
            followup_results=followup_results,
            followup_fetch_failures=followup_fetch_failures,
            synthetic_pages=synthetic_pages,
            workers=workers,
            timeout=timeout,
        ))
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
    export_all(metadata=_build_research_metadata(
        query=query,
        location=location,
        target_category=target_category,
        profile=profile,
        min_score=min_score,
        search_provider=provider_label,
        queries=queries,
        search_results=search_results,
        ranked_results=ranked_results,
        initial_pages=pages,
        followup_discovered_urls=len(listing_detail_links),
        followup_pages=followup_pages,
        verified_pages=verified_pages,
        opportunities=opportunities,
        rejected_counter=rejected_counter,
        rejection_reason_counter=rejection_reason_counter,
        initial_fetch_failures=initial_fetch_failures,
        followup_results=followup_results,
        followup_fetch_failures=followup_fetch_failures,
        synthetic_pages=synthetic_pages,
        workers=workers,
        timeout=timeout,
    ))

    console.rule("[bold green]Done[/bold green]")
    console.print(f"\n Saved: {saved} opportunities")
    return saved
