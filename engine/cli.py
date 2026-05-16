"""CLI — command-line interface menggunakan Typer."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from engine.db import init_db, get_all_opportunities, get_opportunity_count, reset_db
from engine.pipeline import run_search_pipeline, run_crawl_sources
from engine.exporter import export_all
from engine.reporter import generate_report
from engine.evaluator import evaluate_dataset, print_eval_report

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
    )


@app.command(name="crawl-sources")
def crawl_sources(
    min_score: int = typer.Option(40, "--min-score", help="Minimum score"),
    max_sources: int = typer.Option(7, "--max-sources", help="Max listing sources to crawl"),
    max_per_source: int = typer.Option(10, "--max-per-source", help="Max detail links per platform"),
    max_total_detail: int = typer.Option(30, "--max-total-detail", help="Max total detail pages"),
    workers: int = typer.Option(5, "--workers", help="Concurrent fetch workers (1-8)"),
    timeout: int = typer.Option(10, "--timeout", help="Fetch timeout per page (seconds)"),
):
    """Crawl dari manual sources di config/sources.yml."""
    workers = min(workers, 8)
    init_db()
    run_crawl_sources(
        min_score=min_score,
        max_sources=max_sources,
        max_per_source=max_per_source,
        max_total_detail=max_total_detail,
        workers=workers,
        timeout=timeout,
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
def validate_results():
    """Quality gate -- validasi data di database."""
    import re
    from engine.listing_parser import is_listing_url
    from engine.extractor import load_keywords, check_suspicious_role

    console.rule("[bold cyan]Quality Gate: Validate Results[/bold cyan]")

    opportunities = get_all_opportunities()
    if not opportunities:
        console.print("[yellow]Belum ada data.[/yellow]")
        return

    config = load_keywords()
    total = len(opportunities)
    issues = []

    # Check 1: Listing/category URLs
    listing_urls = []
    for opp in opportunities:
        url = opp.get("source_url", "")
        if is_listing_url(url):
            listing_urls.append(url)
            issues.append(f"[LISTING URL] {url}")

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
    for opp in opportunities:
        sal = opp.get("salary") or ""
        if sal:
            if len(sal) < 4 or re.match(r"^[A-Z]+,?$", sal, re.IGNORECASE) or len(re.findall(r"\d", sal)) > 15:
                invalid_salary.append(sal)
                issues.append(f"[BAD SALARY] {sal}")

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

    # --- Report ---
    console.print(f"\n[bold]Total opportunities:[/bold] {total}")
    console.print(f"  Listing URLs:     [{'red' if listing_urls else 'green'}]{len(listing_urls)}[/]")
    console.print(f"  Bad titles:       [{'red' if bad_titles else 'green'}]{len(bad_titles)}[/]")
    console.print(f"  Non-internship:   [{'red' if non_intern else 'green'}]{len(non_intern)}[/]")
    console.print(f"  Invalid salary:   [{'red' if invalid_salary else 'green'}]{len(invalid_salary)}[/]")
    console.print(f"  Invalid duration: [{'red' if invalid_duration else 'green'}]{len(invalid_duration)}[/]")
    console.print(f"  Non-detail:       [{'red' if non_detail else 'green'}]{len(non_detail)}[/]")
    console.print(f"  Low role conf:    [{'red' if bad_role_conf else 'green'}]{len(bad_role_conf)}[/]")
    console.print(f"  Suspicious roles: [{'red' if suspicious_cat else 'green'}]{len(suspicious_cat)}[/]")

    if issues:
        console.print(f"\n[red][FAIL][/red] {len(issues)} issues:")
        for issue in issues[:25]:
            console.print(f"  {issue}")
        if len(issues) > 25:
            console.print(f"  ... and {len(issues) - 25} more")
    else:
        console.print(f"\n[green][PASS][/green] All {total} opportunities passed quality gate!")


@app.command(name="eval")
def eval_dataset(
    dataset: str = typer.Option("data/golden_dataset.csv", "--dataset", "-d", help="Path CSV golden dataset"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score counted as saved"),
    show_errors: int = typer.Option(20, "--show-errors", help="Max error rows to display"),
):
    """Evaluate extractor/scorer against a labeled golden dataset."""
    metrics = evaluate_dataset(dataset, min_score=min_score)
    print_eval_report(metrics, show_errors=show_errors)
