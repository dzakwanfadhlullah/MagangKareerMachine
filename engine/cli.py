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
        console.print("[green]✅ Database reset.[/green]")
    else:
        console.print("[dim]Dibatalkan.[/dim]")
