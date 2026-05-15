"""CLI — command-line interface menggunakan Typer."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from engine.db import init_db, get_all_opportunities, get_opportunity_count, reset_db
from engine.pipeline import run_search_pipeline, run_crawl_sources
from engine.exporter import export_all
from engine.reporter import generate_report

console = Console()
app = typer.Typer(
    name="magangkareer",
    help="🎯 MagangKareer Engine — mesin pencari peluang magang.",
    add_completion=False,
)


@app.command()
def init():
    """Buat database dan folder yang dibutuhkan."""
    console.print("[bold]Initializing MagangKareer Engine...[/bold]")
    init_db()
    console.print("[green]✅ Ready![/green]")


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="Keyword pencarian (e.g., 'frontend intern')"),
    location: str = typer.Option("Indonesia", "--location", "-l", help="Lokasi target"),
    limit: int = typer.Option(20, "--limit", help="Max results per query"),
    min_score: int = typer.Option(40, "--min-score", help="Minimum score untuk disimpan"),
):
    """Jalankan pipeline pencarian lengkap."""
    init_db()
    run_search_pipeline(query, location, limit, min_score)


@app.command(name="crawl-sources")
def crawl_sources(
    min_score: int = typer.Option(40, "--min-score", help="Minimum score untuk disimpan"),
):
    """Crawl dari manual sources di config/sources.yml."""
    init_db()
    run_crawl_sources(min_score)


@app.command(name="list")
def list_opportunities(
    limit: int = typer.Option(20, "--limit", "-n", help="Jumlah result yang ditampilkan"),
):
    """Tampilkan top opportunities di terminal."""
    opportunities = get_all_opportunities()

    if not opportunities:
        console.print("[yellow]Belum ada data. Jalankan 'search' atau 'crawl-sources' dulu.[/yellow]")
        return

    table = Table(title="🎯 Top Opportunities", show_lines=False)
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
            (opp.get("title") or "—")[:50],
            (opp.get("company") or "—")[:25],
            (opp.get("role") or "—")[:20],
            (opp.get("location") or "—")[:15],
            (opp.get("source_name") or "—")[:20],
        )

    console.print(table)
    console.print(f"\n[dim]Total in database: {get_opportunity_count()}[/dim]")


@app.command()
def export():
    """Ekspor data ke CSV dan JSON."""
    count = get_opportunity_count()
    if count == 0:
        console.print("[yellow]Belum ada data untuk diekspor.[/yellow]")
        return
    export_all()


@app.command()
def report():
    """Generate HTML report."""
    count = get_opportunity_count()
    if count == 0:
        console.print("[yellow]Belum ada data untuk report.[/yellow]")
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
    """Quality gate — validasi data di database dan export."""
    import re
    import json
    from engine.listing_parser import is_listing_url, is_listing_title, LISTING_URL_PATTERNS

    console.rule("[bold cyan]Quality Gate: Validate Results[/bold cyan]")

    opportunities = get_all_opportunities()
    if not opportunities:
        console.print("[yellow]Belum ada data.[/yellow]")
        return

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
        r"explore jobs",
        r"lowongan kerja populer",
        r"lowongan kerja full.?time",
        r"lowongan kerja magang",
        r"lowongan kerja di indonesia",
        r"job vacancy.*opportunit",
        r"cari lowongan",
        r"browse jobs",
        r"find jobs",
    ]
    bad_titles = []
    for opp in opportunities:
        title = (opp.get("title") or "").lower()
        for pattern in bad_title_patterns:
            if re.search(pattern, title):
                bad_titles.append(opp.get("title"))
                issues.append(f"[BAD TITLE] {opp.get('title')}")
                break

    # Check 3: Non-internship (title check)
    intern_signals = ["intern", "internship", "magang", "trainee", "apprentice"]
    non_intern = []
    for opp in opportunities:
        title = (opp.get("title") or "").lower()
        raw = (opp.get("raw_text") or "")[:2000].lower()
        has_signal = any(s in title or s in raw for s in intern_signals)
        if not has_signal:
            non_intern.append(opp.get("title"))
            issues.append(f"[NOT INTERN] {opp.get('title')}")

    # Check 4: Invalid salary
    invalid_salary = []
    for opp in opportunities:
        sal = opp.get("salary") or ""
        if sal:
            # Reject: terlalu pendek, hanya huruf, angka gabungan aneh
            if len(sal) < 4:
                invalid_salary.append(sal)
                issues.append(f"[BAD SALARY] {sal}")
            elif re.match(r"^[A-Z]+,?$", sal, re.IGNORECASE):
                invalid_salary.append(sal)
                issues.append(f"[BAD SALARY] {sal}")
            elif len(re.findall(r"\d", sal)) > 15:
                invalid_salary.append(sal)
                issues.append(f"[BAD SALARY] {sal}")

    # Check 5: Invalid duration
    invalid_duration = []
    for opp in opportunities:
        dur = opp.get("duration") or ""
        if dur:
            match = re.search(r"(\d+)", dur)
            if match:
                num = int(match.group(1))
                if num > 24:
                    invalid_duration.append(dur)
                    issues.append(f"[BAD DURATION] {dur}")

    # Check 6: Page type
    non_detail = [o for o in opportunities if o.get("page_type") != "detail"]
    for opp in non_detail:
        issues.append(f"[NON-DETAIL] page_type={opp.get('page_type')} | {opp.get('title')}")

    # --- Print Report ---
    console.print(f"\n[bold]Total opportunities:[/bold] {total}")
    console.print(f"  Listing URLs: [{'red' if listing_urls else 'green'}]{len(listing_urls)}[/]")
    console.print(f"  Bad titles: [{'red' if bad_titles else 'green'}]{len(bad_titles)}[/]")
    console.print(f"  Non-internship: [{'red' if non_intern else 'green'}]{len(non_intern)}[/]")
    console.print(f"  Invalid salary: [{'red' if invalid_salary else 'green'}]{len(invalid_salary)}[/]")
    console.print(f"  Invalid duration: [{'red' if invalid_duration else 'green'}]{len(invalid_duration)}[/]")
    console.print(f"  Non-detail pages: [{'red' if non_detail else 'green'}]{len(non_detail)}[/]")

    if issues:
        console.print(f"\n[red][FAIL][/red] {len(issues)} quality issues found:")
        for issue in issues[:20]:
            console.print(f"  {issue}")
        if len(issues) > 20:
            console.print(f"  ... and {len(issues) - 20} more")
    else:
        console.print(f"\n[green][PASS][/green] All {total} opportunities passed quality gate!")

