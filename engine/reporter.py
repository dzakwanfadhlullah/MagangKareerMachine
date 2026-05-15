"""Reporter — generate HTML report dari data opportunities."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import Counter

from rich.console import Console

from engine.db import get_all_opportunities, get_opportunity_count

console = Console()

EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")


def generate_report(db_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """
    Generate HTML report berisi ringkasan opportunities.

    Report berisi:
    - Total opportunities
    - Jumlah baru (hari ini)
    - Top 20 by score
    - Distribusi role, lokasi, sumber
    - Timestamp generate
    """
    Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    path = output_path or os.path.join(EXPORT_DIR, "report.html")

    opportunities = get_all_opportunities(db_path)
    total = len(opportunities)
    today = datetime.now().strftime("%Y-%m-%d")

    # Hitung baru hari ini
    new_today = sum(1 for o in opportunities if o.get("first_seen", "")[:10] == today)

    # Top 20
    top20 = opportunities[:20]

    # Distribusi
    role_dist = Counter(o.get("role") or "Unknown" for o in opportunities)
    loc_dist = Counter(o.get("location") or "Unknown" for o in opportunities)
    src_dist = Counter(o.get("source_name") or "Unknown" for o in opportunities)

    # Generate HTML
    html = _build_html(total, new_today, top20, role_dist, loc_dist, src_dist)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    console.print(f"[green][OK][/green] Report generated at {path}")
    return path


def _build_distribution_rows(dist: Counter) -> str:
    """Build table rows dari Counter."""
    rows = ""
    for name, count in dist.most_common(15):
        pct = 0
        total = sum(dist.values())
        if total > 0:
            pct = round(count / total * 100, 1)
        rows += f"""
            <tr>
                <td>{name}</td>
                <td>{count}</td>
                <td>
                    <div style="background:#1e293b;border-radius:4px;overflow:hidden;height:20px;">
                        <div style="background:linear-gradient(90deg,#6366f1,#8b5cf6);height:100%;width:{pct}%;min-width:2px;border-radius:4px;"></div>
                    </div>
                </td>
                <td style="text-align:right;">{pct}%</td>
            </tr>"""
    return rows


def _build_opportunity_rows(opportunities: list[dict]) -> str:
    """Build table rows untuk top opportunities."""
    rows = ""
    for opp in opportunities:
        score = opp.get("score", 0)
        # Warna badge berdasarkan skor
        if score >= 75:
            badge_color = "#22c55e"
        elif score >= 40:
            badge_color = "#eab308"
        else:
            badge_color = "#ef4444"

        title = opp.get("title", "—")[:80]
        company = opp.get("company") or "—"
        role = opp.get("role") or "—"
        location = opp.get("location") or "—"
        work_mode = opp.get("work_mode") or "—"
        source = opp.get("source_name") or "—"
        url = opp.get("source_url") or "#"

        rows += f"""
            <tr>
                <td><span style="background:{badge_color};color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;font-size:13px;">{score}</span></td>
                <td><a href="{url}" target="_blank" style="color:#818cf8;text-decoration:none;">{title}</a></td>
                <td>{company}</td>
                <td>{role}</td>
                <td>{location}</td>
                <td>{work_mode}</td>
                <td>{source}</td>
            </tr>"""
    return rows


def _build_html(total, new_today, top20, role_dist, loc_dist, src_dist) -> str:
    """Build full HTML report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MagangKareer Report</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 24px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            font-size: 28px;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 32px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        }}
        .stat-card .label {{ color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
        .stat-card .value {{ font-size: 32px; font-weight: 700; color: #f1f5f9; margin-top: 4px; }}
        .section {{ margin-bottom: 32px; }}
        .section h2 {{
            font-size: 20px;
            color: #f1f5f9;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #334155;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background: #1e293b;
            color: #94a3b8;
            text-align: left;
            padding: 10px 12px;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #334155;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #1e293b;
        }}
        tr:hover {{ background: #1e293b44; }}
        .footer {{
            text-align: center;
            color: #475569;
            font-size: 12px;
            margin-top: 48px;
            padding-top: 16px;
            border-top: 1px solid #1e293b;
        }}
        .dist-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 24px;
        }}
        .dist-card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        }}
        .dist-card h3 {{ font-size: 16px; color: #e2e8f0; margin-bottom: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 MagangKareer Report</h1>
        <p class="subtitle">Generated: {timestamp}</p>

        <div class="stats">
            <div class="stat-card">
                <div class="label">Total Opportunities</div>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <div class="label">New Today</div>
                <div class="value">{new_today}</div>
            </div>
            <div class="stat-card">
                <div class="label">Top Score</div>
                <div class="value">{top20[0].get('score', 0) if top20 else 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Sources</div>
                <div class="value">{len(src_dist)}</div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 Top 20 Opportunities</h2>
            <div style="overflow-x:auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Score</th>
                            <th>Title</th>
                            <th>Company</th>
                            <th>Role</th>
                            <th>Location</th>
                            <th>Mode</th>
                            <th>Source</th>
                        </tr>
                    </thead>
                    <tbody>
                        {_build_opportunity_rows(top20)}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="section">
            <h2>📊 Distribution</h2>
            <div class="dist-grid">
                <div class="dist-card">
                    <h3>By Role</h3>
                    <table>
                        <thead><tr><th>Role</th><th>Count</th><th>Bar</th><th>%</th></tr></thead>
                        <tbody>{_build_distribution_rows(role_dist)}</tbody>
                    </table>
                </div>
                <div class="dist-card">
                    <h3>By Location</h3>
                    <table>
                        <thead><tr><th>Location</th><th>Count</th><th>Bar</th><th>%</th></tr></thead>
                        <tbody>{_build_distribution_rows(loc_dist)}</tbody>
                    </table>
                </div>
                <div class="dist-card">
                    <h3>By Source</h3>
                    <table>
                        <thead><tr><th>Source</th><th>Count</th><th>Bar</th><th>%</th></tr></thead>
                        <tbody>{_build_distribution_rows(src_dist)}</tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="footer">
            MagangKareer Engine &mdash; {timestamp}
        </div>
    </div>
</body>
</html>"""
