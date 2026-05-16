"""CLI — command-line interface menggunakan Typer."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from engine.db import (
    init_db,
    get_all_opportunities,
    get_discovery_candidates,
    get_opportunity_count,
    get_rejected_candidates,
    reset_db,
)
from engine.pipeline import run_search_pipeline, run_crawl_sources
from engine.exporter import export_all
from engine.reporter import generate_report
from engine.evaluator import evaluate_dataset, print_eval_report
from engine.research.research_pipeline import run_research_pipeline
from engine.research.profiles import get_research_profile
from engine.searcher import get_crawl_profile
from engine.models import Opportunity

console = Console()
app = typer.Typer(
    name="magangkareer",
    help="MagangKareer Engine -- mesin pencari peluang magang.",
    add_completion=False,
)


@app.command()
def init():
    """Buat database dan folder yang dibutuhkan."""
    console.print("[bold]Initializing MagangKareer Engine...[/bold]")
    init_db()
    console.print("[green]Ready![/green]")


@app.command()
def research(
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Keyword pencarian"),
    location: str = typer.Option("Indonesia", "--location", "-l", help="Lokasi target"),
    target_category: Optional[str] = typer.Option(
        None,
        "--target-category",
        help="Target category/role, e.g. tech, frontend, backend, fullstack, actuarial",
    ),
    profile: str = typer.Option("normal", "--profile", help="Research profile: fast, normal, deep"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score"),
    query_count: Optional[int] = typer.Option(None, "--query-count", help="Override jumlah search queries"),
    max_fetch: Optional[int] = typer.Option(None, "--max-fetch", help="Override jumlah top URLs untuk fetch"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Override concurrent fetch/search workers"),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Override fetch timeout per page"),
    results_per_query: Optional[int] = typer.Option(None, "--results-per-query", help="Override search hits per query"),
):
    """Fast research mode: search-index-first direct URL discovery."""
    if not query and not target_category:
        console.print("[red]Isi --query atau --target-category.[/red]")
        raise typer.Exit(code=1)
    try:
        get_research_profile(profile)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    run_research_pipeline(
        query=query,
        location=location,
        target_category=target_category,
        profile=profile,
        query_count=query_count,
        max_fetch=max_fetch,
        workers=workers,
        timeout=timeout,
        min_score=min_score,
        results_per_query=results_per_query,
    )


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="Keyword pencarian"),
    location: str = typer.Option("Indonesia", "--location", "-l", help="Lokasi target"),
    limit: int = typer.Option(20, "--limit", help="Max results per query"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score"),
    max_per_source: int = typer.Option(10, "--max-per-source", help="Max detail links per platform"),
    max_total_detail: int = typer.Option(30, "--max-total-detail", help="Max total detail pages"),
    workers: int = typer.Option(5, "--workers", help="Concurrent fetch workers (1-8)"),
    timeout: int = typer.Option(10, "--timeout", help="Fetch timeout per page (seconds)"),
    query_limit: int = typer.Option(3, "--query-limit", help="Max search queries"),
    target_category: Optional[str] = typer.Option(
        None,
        "--target-category",
        help="Filter accepted results to a category/role, e.g. actuarial, frontend, data_analyst",
    ),
):
    """Jalankan pipeline pencarian lengkap."""
    workers = min(workers, 8)
    init_db()
    run_search_pipeline(
        query, location, limit, min_score,
        max_per_source=max_per_source,
        max_total_detail=max_total_detail,
        workers=workers,
        timeout=timeout,
        query_limit=query_limit,
        target_category=target_category,
    )


@app.command(name="crawl-sources")
def crawl_sources(
    profile: str = typer.Option("normal", "--profile", help="Crawl profile: quick, normal, deep"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score"),
    max_sources: Optional[int] = typer.Option(None, "--max-sources", help="Override max listing sources"),
    max_per_source: Optional[int] = typer.Option(None, "--max-per-source", help="Override max detail links per platform"),
    max_total_detail: Optional[int] = typer.Option(None, "--max-total-detail", help="Override max total detail pages"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Override concurrent fetch workers (1-8)"),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Override fetch timeout per page (seconds)"),
    target_category: Optional[str] = typer.Option(
        None,
        "--target-category",
        help="Filter accepted results to a category/role, e.g. actuarial, frontend, data_analyst",
    ),
):
    """Crawl dari manual sources di config/sources.yml."""
    try:
        profile_cfg = get_crawl_profile(profile)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    max_sources = max_sources if max_sources is not None else profile_cfg.get("max_sources", 8)
    max_per_source = max_per_source if max_per_source is not None else profile_cfg.get("max_per_source", 10)
    max_total_detail = max_total_detail if max_total_detail is not None else profile_cfg.get("max_total_detail", 60)
    workers = workers if workers is not None else profile_cfg.get("workers", 6)
    timeout = timeout if timeout is not None else profile_cfg.get("timeout", 10)
    workers = min(workers, 8)
    init_db()
    console.print(
        f"[dim]Profile {profile}: sources={max_sources}, per_source={max_per_source}, "
        f"total_detail={max_total_detail}, workers={workers}, timeout={timeout}s[/dim]"
    )
    run_crawl_sources(
        min_score=min_score,
        max_sources=max_sources,
        max_per_source=max_per_source,
        max_total_detail=max_total_detail,
        workers=workers,
        timeout=timeout,
        target_category=target_category,
    )


@app.command(name="list")
def list_opportunities(
    limit: int = typer.Option(20, "--limit", "-n", help="Jumlah result"),
):
    """Tampilkan top opportunities di terminal."""
    opportunities = get_all_opportunities()
    if not opportunities:
        console.print("[yellow]Belum ada data. Jalankan 'search' atau 'crawl-sources' dulu.[/yellow]")
        return

    table = Table(title="Top Opportunities", show_lines=False)
    table.add_column("Score", style="bold", width=6, justify="center")
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Company", max_width=25)
    table.add_column("Role", max_width=20)
    table.add_column("Location", max_width=15)
    table.add_column("Source", style="dim", max_width=20)

    for opp in opportunities[:limit]:
        score = opp.get("score", 0)
        if score >= 75:
            score_style = "bold green"
        elif score >= 40:
            score_style = "bold yellow"
        else:
            score_style = "bold red"

        table.add_row(
            f"[{score_style}]{score}[/{score_style}]",
            (opp.get("title") or "-")[:50],
            (opp.get("company") or "-")[:25],
            (opp.get("role") or "-")[:20],
            (opp.get("location") or "-")[:15],
            (opp.get("source_name") or "-")[:20],
        )

    console.print(table)
    console.print(f"\n[dim]Total in database: {get_opportunity_count()}[/dim]")


@app.command(name="list-rejections")
def list_rejections(
    limit: int = typer.Option(30, "--limit", "-n", help="Jumlah rejected candidates"),
):
    """Tampilkan rejected candidates terbaru untuk audit false negatives."""
    rows = get_rejected_candidates(limit)
    if not rows:
        console.print("[yellow]Belum ada rejected candidates.[/yellow]")
        return

    table = Table(title="Rejected Candidates", show_lines=False)
    table.add_column("Reason", style="yellow", max_width=28)
    table.add_column("Title", style="cyan", max_width=45)
    table.add_column("Platform", max_width=12)
    table.add_column("Intern", justify="right", width=6)
    table.add_column("Role", justify="right", width=6)
    table.add_column("Score", justify="right", width=6)

    for row in rows:
        table.add_row(
            row.get("rejection_reason") or "-",
            (row.get("title") or "-")[:45],
            row.get("source_platform") or "-",
            str(row.get("internship_confidence") or 0),
            str(row.get("role_confidence") or 0),
            str(row.get("score") or 0),
        )

    console.print(table)


@app.command(name="list-discovery")
def list_discovery(
    limit: int = typer.Option(30, "--limit", "-n", help="Jumlah discovery candidates"),
):
    """Tampilkan kandidat detail URL hasil discovery sebelum fetch/filter final."""
    rows = get_discovery_candidates(limit)
    if not rows:
        console.print("[yellow]Belum ada discovery candidates.[/yellow]")
        return

    table = Table(title="Discovery Candidates", show_lines=False)
    table.add_column("Target", style="yellow", max_width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Method", max_width=8)
    table.add_column("Title", style="cyan", max_width=45)
    table.add_column("Platform", max_width=12)

    for row in rows:
        table.add_row(
            row.get("target_category") or "-",
            str(row.get("target_score") or 0),
            row.get("discovery_method") or "-",
            (row.get("title") or row.get("url") or "-")[:45],
            row.get("source_platform") or "-",
        )

    console.print(table)


@app.command()
def export():
    """Ekspor data ke CSV dan JSON."""
    count = get_opportunity_count()
    if count == 0:
        console.print("[yellow]Belum ada data.[/yellow]")
        return
    export_all()


@app.command()
def report():
    """Generate HTML report."""
    count = get_opportunity_count()
    if count == 0:
        console.print("[yellow]Belum ada data.[/yellow]")
        return
    generate_report()


@app.command()
def reset():
    """Reset database (hapus semua data)."""
    confirm = typer.confirm("Yakin ingin menghapus semua data?")
    if confirm:
        reset_db()
        console.print("[green]Database reset.[/green]")
    else:
        console.print("[dim]Dibatalkan.[/dim]")


@app.command(name="validate-results")
def validate_results(
    target_category: Optional[str] = typer.Option(
        None,
        "--target-category",
        help="Require all accepted results to match this category/role",
    ),
):
    """Quality gate -- validasi data di database."""
    import re
    from collections import Counter
    from engine.listing_parser import is_listing_url
    from engine.url_utils import has_tracking_params
    from engine.extractor import (
        load_keywords,
        check_suspicious_role,
        normalize_target_category,
        opportunity_matches_target,
        title_has_seniority_without_internship,
    )

    console.rule("[bold cyan]Quality Gate: Validate Results[/bold cyan]")

    opportunities = get_all_opportunities()
    if not opportunities:
        console.print("[yellow]Belum ada data.[/yellow]")
        return

    config = load_keywords()
    normalized_target = normalize_target_category(target_category)
    total = len(opportunities)
    issues = []
    warnings = []

    # Check 1: Listing/category URLs
    listing_urls = []
    for opp in opportunities:
        url = opp.get("source_url", "")
        detail_url = opp.get("detail_url") or ""
        for candidate_url in [url, detail_url]:
            if candidate_url and is_listing_url(candidate_url):
                listing_urls.append(candidate_url)
                issues.append(f"[LISTING URL] {candidate_url}")

    # Check 1b: Tracking params must never appear in accepted canonical URLs
    tracking_urls = []
    for opp in opportunities:
        for field in ["source_url", "detail_url"]:
            url = opp.get(field) or ""
            if url and has_tracking_params(url):
                tracking_urls.append(url)
                issues.append(f"[TRACKING URL:{field}] {url}")

    # Check 2: Bad titles
    bad_title_patterns = [
        r"explore jobs", r"lowongan kerja populer", r"lowongan kerja full.?time",
        r"lowongan kerja magang", r"lowongan kerja di indonesia",
        r"job vacancy.*opportunit", r"cari lowongan", r"browse jobs", r"find jobs",
    ]
    bad_titles = []
    for opp in opportunities:
        title = (opp.get("title") or "").lower()
        for pattern in bad_title_patterns:
            if re.search(pattern, title):
                bad_titles.append(opp.get("title"))
                issues.append(f"[BAD TITLE] {opp.get('title')}")
                break

    # Check 3: Non-internship (is_internship field OR text check)
    non_intern = []
    for opp in opportunities:
        is_intern = opp.get("is_internship", False)
        if not is_intern:
            # Fallback: text check
            title = (opp.get("title") or "").lower()
            raw = (opp.get("raw_text") or "")[:2000].lower()
            signals = ["intern", "internship", "magang", "trainee", "apprentice"]
            has_signal = any(s in title or s in raw for s in signals)
            if not has_signal:
                non_intern.append(opp.get("title"))
                issues.append(f"[NOT INTERN] {opp.get('title')}")

    # Check 4: Invalid salary
    invalid_salary = []
    salary_contradictions = []
    low_salary_confidence = []
    for opp in opportunities:
        sal = opp.get("salary") or ""
        text = f"{opp.get('title') or ''}\n{opp.get('summary') or ''}\n{opp.get('raw_text') or ''}".lower()
        if sal:
            if len(sal) < 4 or re.match(r"^[A-Z]+,?$", sal, re.IGNORECASE) or len(re.findall(r"\d", sal)) > 15:
                invalid_salary.append(sal)
                issues.append(f"[BAD SALARY] {sal}")
            if "perusahaan tidak menampilkan gaji" in text or "salary not displayed" in text:
                salary_contradictions.append(opp.get("title"))
                warnings.append(f"[SALARY CONTRADICTION] {opp.get('title')}")
            if (opp.get("salary_confidence") or 0) < 60:
                low_salary_confidence.append(opp.get("title"))
                warnings.append(f"[LOW SALARY CONF] {opp.get('title')} | {sal}")

    # Check 5: Invalid duration
    invalid_duration = []
    for opp in opportunities:
        dur = opp.get("duration") or ""
        if dur:
            match = re.search(r"(\d+)", dur)
            if match and int(match.group(1)) > 24:
                invalid_duration.append(dur)
                issues.append(f"[BAD DURATION] {dur}")

    # Check 6: Page type
    non_detail = [o for o in opportunities if o.get("page_type") != "detail"]
    for opp in non_detail:
        issues.append(f"[NON-DETAIL] {opp.get('title')}")

    # Check 6b: Closed/expired pages should never be accepted
    closed_results = []
    closed_patterns = [
        r"\bclosed\b",
        r"\bexpired\b",
        r"\bno longer accepting\b",
        r"\blowongan ditutup\b",
        r"\bditutup\b",
        r"\bkadaluarsa\b",
    ]
    for opp in opportunities:
        text = f"{opp.get('title') or ''}\n{opp.get('summary') or ''}\n{opp.get('raw_text') or ''}".lower()
        if any(re.search(pattern, text) for pattern in closed_patterns):
            closed_results.append(opp.get("title"))
            issues.append(f"[CLOSED ACCEPTED] {opp.get('title')}")

    # Check 7: Role confidence (role set but confidence < 60)
    bad_role_conf = []
    for opp in opportunities:
        role = opp.get("role")
        role_conf = opp.get("role_confidence", 0)
        if role and role_conf < 60:
            bad_role_conf.append(f"{opp.get('title')} | role={role} conf={role_conf}")
            issues.append(f"[LOW ROLE CONF] {opp.get('title')} | role={role} conf={role_conf}")

    # Check 8: Suspicious role with tech/data/actuarial category
    suspicious_cat = []
    for opp in opportunities:
        title = opp.get("title") or ""
        sus = check_suspicious_role(title, config)
        cat = opp.get("category") or ""
        if sus and cat in ("tech", "data", "actuarial"):
            suspicious_cat.append(f"{title} -> {cat}")
            issues.append(f"[SUS ROLE] {title} classified as {cat}")

    # Check 8b: Hard negative terms should never appear in accepted results
    hard_negative_results = []
    hard_negative_terms = config.get("negative_terms", {}).get("hard_reject", [])
    for opp in opportunities:
        text = f"{opp.get('title') or ''}\n{opp.get('summary') or ''}\n{opp.get('raw_text') or ''}".lower()
        for term in hard_negative_terms:
            if term.lower() in text:
                hard_negative_results.append(opp.get("title"))
                issues.append(f"[HARD NEGATIVE] {opp.get('title')} | {term}")
                break

    # Check 8c: Field-level warnings
    wfh_mismatch = []
    metadata_low = []
    for opp in opportunities:
        text = f"{opp.get('title') or ''}\n{opp.get('summary') or ''}".lower()
        if re.search(r"\bwfh\b|\bwork\s+from\s+home\b|\bfull\s+remote\b|\bfully\s+remote\b", text):
            if opp.get("work_mode") != "remote":
                wfh_mismatch.append(opp.get("title"))
                warnings.append(f"[WFH WORK MODE] {opp.get('title')} -> {opp.get('work_mode') or 'null'}")
        missing_fields = [field for field in ["company", "location", "role", "category"] if not opp.get(field)]
        if len(missing_fields) >= 2:
            metadata_low.append(opp.get("title"))
            warnings.append(f"[LOW METADATA] {opp.get('title')} missing {','.join(missing_fields)}")

    platform_counts = Counter(opp.get("source_platform") or "unknown" for opp in opportunities)
    source_diversity_warning = len(platform_counts) == 1 and total > 1
    if source_diversity_warning:
        platform = next(iter(platform_counts))
        warnings.append(f"[SOURCE DIVERSITY] all accepted results from {platform}")

    # Check 9: Targeted result integrity
    out_of_target = []
    target_null_role = []
    target_seniority = []
    if normalized_target:
        for opp in opportunities:
            title = opp.get("title") or ""
            if not opp.get("role") or not opp.get("category"):
                target_null_role.append(title)
                issues.append(f"[TARGET NULL ROLE] {title}")
                continue

            opportunity = Opportunity(**opp)
            if not opportunity_matches_target(opportunity, normalized_target):
                out_of_target.append(f"{title} -> {opp.get('role') or '-'} / {opp.get('category') or '-'}")
                issues.append(f"[OUT OF TARGET:{normalized_target}] {title}")

            if title_has_seniority_without_internship(title):
                target_seniority.append(title)
                issues.append(f"[TARGET SENIORITY] {title}")

    # --- Report ---
    console.print(f"\n[bold]Total opportunities:[/bold] {total}")
    console.print(f"  Listing URLs:     [{'red' if listing_urls else 'green'}]{len(listing_urls)}[/]")
    console.print(f"  Tracking URLs:    [{'red' if tracking_urls else 'green'}]{len(tracking_urls)}[/]")
    console.print(f"  Bad titles:       [{'red' if bad_titles else 'green'}]{len(bad_titles)}[/]")
    console.print(f"  Non-internship:   [{'red' if non_intern else 'green'}]{len(non_intern)}[/]")
    console.print(f"  Invalid salary:   [{'red' if invalid_salary else 'green'}]{len(invalid_salary)}[/]")
    console.print(f"  Salary warnings:  [{'yellow' if salary_contradictions or low_salary_confidence else 'green'}]{len(salary_contradictions) + len(low_salary_confidence)}[/]")
    console.print(f"  Invalid duration: [{'red' if invalid_duration else 'green'}]{len(invalid_duration)}[/]")
    console.print(f"  Non-detail:       [{'red' if non_detail else 'green'}]{len(non_detail)}[/]")
    console.print(f"  Closed accepted:  [{'red' if closed_results else 'green'}]{len(closed_results)}[/]")
    console.print(f"  Low role conf:    [{'red' if bad_role_conf else 'green'}]{len(bad_role_conf)}[/]")
    console.print(f"  Suspicious roles: [{'red' if suspicious_cat else 'green'}]{len(suspicious_cat)}[/]")
    console.print(f"  Hard negatives:   [{'red' if hard_negative_results else 'green'}]{len(hard_negative_results)}[/]")
    console.print(f"  WFH mismatch:     [{'yellow' if wfh_mismatch else 'green'}]{len(wfh_mismatch)}[/]")
    console.print(f"  Low metadata:     [{'yellow' if metadata_low else 'green'}]{len(metadata_low)}[/]")
    console.print(f"  Source diversity: [{'yellow' if source_diversity_warning else 'green'}]{len(platform_counts)} platform(s)[/]")
    if normalized_target:
        console.print(f"  Target:           [bold]{normalized_target}[/bold]")
        console.print(f"  Out of target:    [{'red' if out_of_target else 'green'}]{len(out_of_target)}[/]")
        console.print(f"  Target null role: [{'red' if target_null_role else 'green'}]{len(target_null_role)}[/]")
        console.print(f"  Target seniority: [{'red' if target_seniority else 'green'}]{len(target_seniority)}[/]")

    if issues:
        console.print(f"\n[red][FAIL][/red] {len(issues)} issues:")
        for issue in issues[:25]:
            console.print(f"  {issue}")
        if len(issues) > 25:
            console.print(f"  ... and {len(issues) - 25} more")
        if warnings:
            console.print(f"\n[yellow][WARN][/yellow] {len(warnings)} warnings:")
            for warning in warnings[:25]:
                console.print(f"  {warning}")
            if len(warnings) > 25:
                console.print(f"  ... and {len(warnings) - 25} more")
    else:
        if warnings:
            console.print(f"\n[yellow][PASS WITH WARNINGS][/yellow] {total} opportunities passed hard gates, {len(warnings)} warnings:")
            for warning in warnings[:25]:
                console.print(f"  {warning}")
            if len(warnings) > 25:
                console.print(f"  ... and {len(warnings) - 25} more")
        else:
            console.print(f"\n[green][PASS][/green] All {total} opportunities passed quality gate!")


@app.command(name="eval")
def eval_dataset(
    dataset: str = typer.Option("data/golden_dataset.csv", "--dataset", "-d", help="Path CSV golden dataset"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score counted as saved"),
    target_category: Optional[str] = typer.Option(
        None,
        "--target-category",
        help="Evaluate as targeted search/crawl, e.g. actuarial, frontend, data_analyst",
    ),
    show_errors: int = typer.Option(20, "--show-errors", help="Max error rows to display"),
):
    """Evaluate extractor/scorer against a labeled golden dataset."""
    metrics = evaluate_dataset(dataset, min_score=min_score, target_category=target_category)
    print_eval_report(metrics, show_errors=show_errors)
