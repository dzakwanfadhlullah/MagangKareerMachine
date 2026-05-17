"""Database module — SQLite CRUD untuk MagangKareer Engine."""

import sqlite3
import os
import json
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

DEFAULT_DB_PATH = "data/magangkareer.db"


def get_db_path() -> str:
    """Ambil path database dari env atau default."""
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Buat koneksi SQLite."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Buat database dan semua tabel yang dibutuhkan."""
    path = db_path or get_db_path()

    # Buat folder jika belum ada
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path("exports").mkdir(parents=True, exist_ok=True)

    conn = get_connection(path)
    cursor = conn.cursor()

    # Tabel raw_results — hasil pencarian mentah
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            title TEXT,
            snippet TEXT,
            url TEXT UNIQUE,
            source TEXT,
            page_type TEXT DEFAULT 'unknown',
            source_platform TEXT,
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabel raw_pages — konten halaman yang sudah di-fetch
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            text_content TEXT,
            html_content TEXT,
            status_code INTEGER,
            page_type TEXT DEFAULT 'unknown',
            source_platform TEXT,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabel crawl_queue — link detail yang diekstrak dari listing pages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            company TEXT,
            source_platform TEXT,
            listing_url TEXT,
            discovery_method TEXT DEFAULT 'dom',
            target_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovery_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            company TEXT,
            source_platform TEXT,
            listing_url TEXT,
            discovery_method TEXT DEFAULT 'unknown',
            target_category TEXT,
            target_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'discovered',
            rejection_reason TEXT,
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url, listing_url, target_category)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_api_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_url TEXT,
            response_url TEXT,
            source_platform TEXT,
            status_code INTEGER DEFAULT 0,
            content_type TEXT,
            body TEXT,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(listing_url, response_url)
        )
    """)

    # Tabel opportunities — lowongan final (hanya dari detail pages)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_key TEXT UNIQUE,
            title TEXT,
            company TEXT,
            company_confidence INTEGER DEFAULT 0,
            role TEXT,
            category TEXT,
            location TEXT,
            work_mode TEXT,
            duration TEXT,
            salary TEXT,
            salary_raw TEXT,
            salary_display TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            salary_confidence INTEGER DEFAULT 0,
            deadline TEXT,
            source_url TEXT,
            detail_url TEXT,
            original_url TEXT,
            source_name TEXT,
            source_platform TEXT,
            raw_text TEXT,
            summary TEXT,
            score INTEGER,
            score_breakdown TEXT,
            confidence INTEGER,
            is_internship INTEGER DEFAULT 0,
            internship_confidence INTEGER DEFAULT 0,
            role_confidence INTEGER DEFAULT 0,
            location_area TEXT,
            page_type TEXT DEFAULT 'detail',
            extraction_status TEXT DEFAULT 'extracted',
            rejection_reason TEXT,
            status TEXT DEFAULT 'new',
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rejected_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            source_platform TEXT,
            page_type TEXT DEFAULT 'detail',
            rejection_reason TEXT,
            internship_confidence INTEGER DEFAULT 0,
            role_confidence INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            text_snippet TEXT,
            rejected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url, rejection_reason)
        )
    """)

    # FTS5 untuk full-text search lokal
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS opportunities_fts
        USING fts5(
            title,
            company,
            role,
            category,
            location,
            raw_text,
            content='opportunities',
            content_rowid='id'
        )
    """)

    _ensure_column(cursor, "crawl_queue", "discovery_method", "TEXT DEFAULT 'dom'")
    _ensure_column(cursor, "crawl_queue", "target_score", "INTEGER DEFAULT 0")
    _ensure_column(cursor, "opportunities", "salary_confidence", "INTEGER DEFAULT 0")
    _ensure_column(cursor, "opportunities", "original_url", "TEXT")
    _ensure_column(cursor, "opportunities", "company_confidence", "INTEGER DEFAULT 0")
    _ensure_column(cursor, "opportunities", "salary_raw", "TEXT")
    _ensure_column(cursor, "opportunities", "salary_display", "TEXT")
    _ensure_column(cursor, "opportunities", "salary_min", "INTEGER")
    _ensure_column(cursor, "opportunities", "salary_max", "INTEGER")
    _ensure_column(cursor, "opportunities", "score_breakdown", "TEXT")

    conn.commit()
    conn.close()
    console.print("[green][OK][/green] Database initialized")


# --- CRUD Operations ---


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Add a column to an existing SQLite table if missing."""
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def save_raw_results(results: list[dict], db_path: Optional[str] = None) -> int:
    """Simpan raw search results ke database. Return jumlah yang disimpan."""
    conn = get_connection(db_path)
    saved = 0
    for r in results:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO raw_results
                (query, title, snippet, url, source, page_type, source_platform)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["query"], r["title"], r.get("snippet"), r["url"],
                    r.get("source", "web"), r.get("page_type", "unknown"),
                    r.get("source_platform"),
                ),
            )
            saved += conn.total_changes
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return saved


def save_raw_page(page: dict, db_path: Optional[str] = None) -> bool:
    """Simpan raw page ke database. Return True jika berhasil."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO raw_pages
            (url, title, text_content, html_content, status_code, page_type, source_platform)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                page["url"], page.get("title"), page["text_content"],
                page.get("html_content", ""), page["status_code"],
                page.get("page_type", "unknown"), page.get("source_platform"),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_raw_pages_by_urls(urls: list[str], db_path: Optional[str] = None) -> list[dict]:
    """Ambil raw_pages berdasarkan daftar URL, mempertahankan urutan input."""
    if not urls:
        return []

    unique_urls = list(dict.fromkeys(urls))
    placeholders = ",".join("?" for _ in unique_urls)
    conn = get_connection(db_path)
    rows = conn.execute(
        f"SELECT * FROM raw_pages WHERE url IN ({placeholders})",
        unique_urls,
    ).fetchall()
    conn.close()

    by_url = {row["url"]: dict(row) for row in rows}
    return [by_url[url] for url in unique_urls if url in by_url]


def save_crawl_queue(links: list[dict], db_path: Optional[str] = None) -> int:
    """Simpan detail links ke crawl queue. Return jumlah yang disimpan."""
    conn = get_connection(db_path)
    saved = 0
    for link in links:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO crawl_queue
                (url, title, company, source_platform, listing_url, discovery_method, target_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    link["url"], link.get("title"), link.get("company"),
                    link.get("source_platform"), link.get("listing_url"),
                    link.get("discovery_method", "dom"), link.get("target_score", 0),
                ),
            )
            saved += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return saved


def save_discovery_candidates(candidates: list[dict], db_path: Optional[str] = None) -> int:
    """Simpan kandidat discovery untuk audit target coverage."""
    conn = get_connection(db_path)
    saved = 0
    for candidate in candidates:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO discovery_candidates
                (url, title, company, source_platform, listing_url, discovery_method,
                 target_category, target_score, status, rejection_reason, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    candidate["url"],
                    candidate.get("title"),
                    candidate.get("company"),
                    candidate.get("source_platform"),
                    candidate.get("listing_url"),
                    candidate.get("discovery_method", "unknown"),
                    candidate.get("target_category"),
                    candidate.get("target_score", 0),
                    candidate.get("status", "discovered"),
                    candidate.get("rejection_reason"),
                ),
            )
            saved += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return saved


def save_raw_api_responses(responses: list[dict], db_path: Optional[str] = None) -> int:
    """Simpan captured API/XHR JSON responses untuk replay/debug parser."""
    conn = get_connection(db_path)
    saved = 0
    for response in responses:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO raw_api_responses
                (listing_url, response_url, source_platform, status_code, content_type, body, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    response["listing_url"],
                    response["response_url"],
                    response.get("source_platform"),
                    response.get("status_code", 0),
                    response.get("content_type"),
                    response.get("body", ""),
                ),
            )
            saved += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return saved


def get_discovery_candidates(limit: int = 50, db_path: Optional[str] = None) -> list[dict]:
    """Ambil kandidat discovery terbaru."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT * FROM discovery_candidates
        ORDER BY discovered_at DESC
        LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_pending_crawl_queue(db_path: Optional[str] = None) -> list[dict]:
    """Ambil semua URL pending dari crawl queue."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM crawl_queue WHERE status = 'pending'"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_crawl_done(url: str, db_path: Optional[str] = None) -> None:
    """Tandai URL di crawl queue sebagai done."""
    conn = get_connection(db_path)
    conn.execute("UPDATE crawl_queue SET status = 'done' WHERE url = ?", (url,))
    conn.commit()
    conn.close()


def save_opportunity(opp: dict, db_path: Optional[str] = None) -> bool:
    """Simpan atau update opportunity ke database."""
    conn = get_connection(db_path)
    try:
        # Cek apakah sudah ada berdasarkan canonical_key
        existing = conn.execute(
            "SELECT id, score FROM opportunities WHERE canonical_key = ?",
            (opp["canonical_key"],),
        ).fetchone()

        if existing:
            # Update last_seen dan simpan skor tertinggi
            new_score = max(existing["score"] or 0, opp.get("score", 0))
            conn.execute(
                "UPDATE opportunities SET last_seen = CURRENT_TIMESTAMP, score = ? WHERE id = ?",
                (new_score, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO opportunities
                (canonical_key, title, company, company_confidence, role, category, location, location_area, work_mode,
                 duration, salary, salary_raw, salary_display, salary_min, salary_max, salary_confidence,
                 deadline, source_url, detail_url, original_url, source_name,
                 source_platform, raw_text, summary, score, score_breakdown, confidence,
                 is_internship, internship_confidence, role_confidence,
                 page_type, extraction_status, rejection_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    opp["canonical_key"],
                    opp["title"],
                    opp.get("company"),
                    opp.get("company_confidence", 0),
                    opp.get("role"),
                    opp.get("category"),
                    opp.get("location"),
                    opp.get("location_area"),
                    opp.get("work_mode"),
                    opp.get("duration"),
                    opp.get("salary"),
                    opp.get("salary_raw"),
                    opp.get("salary_display"),
                    opp.get("salary_min"),
                    opp.get("salary_max"),
                    opp.get("salary_confidence", 0),
                    opp.get("deadline"),
                    opp["source_url"],
                    opp.get("detail_url"),
                    opp.get("original_url"),
                    opp.get("source_name"),
                    opp.get("source_platform"),
                    opp.get("raw_text"),
                    opp.get("summary"),
                    opp.get("score", 0),
                    json.dumps(opp.get("score_breakdown"), ensure_ascii=False) if opp.get("score_breakdown") else None,
                    opp.get("confidence", 0),
                    1 if opp.get("is_internship") else 0,
                    opp.get("internship_confidence", 0),
                    opp.get("role_confidence", 0),
                    opp.get("page_type", "detail"),
                    opp.get("extraction_status", "extracted"),
                    opp.get("rejection_reason"),
                ),
            )
            # Update FTS index
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO opportunities_fts (rowid, title, company, role, category, location, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    opp["title"],
                    opp.get("company"),
                    opp.get("role"),
                    opp.get("category"),
                    opp.get("location"),
                    opp.get("raw_text"),
                ),
            )

        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def save_rejected_candidate(candidate: dict, db_path: Optional[str] = None) -> bool:
    """Simpan rejected candidate untuk audit false negatives."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO rejected_candidates
            (url, title, source_platform, page_type, rejection_reason,
             internship_confidence, role_confidence, score, text_snippet, rejected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                candidate["url"],
                candidate.get("title"),
                candidate.get("source_platform"),
                candidate.get("page_type", "detail"),
                candidate["rejection_reason"],
                candidate.get("internship_confidence", 0),
                candidate.get("role_confidence", 0),
                candidate.get("score", 0),
                candidate.get("text_snippet"),
            ),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_rejected_candidates(limit: int = 50, db_path: Optional[str] = None) -> list[dict]:
    """Ambil rejected candidates terbaru untuk audit."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT * FROM rejected_candidates
        ORDER BY rejected_at DESC
        LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_opportunities(db_path: Optional[str] = None) -> list[dict]:
    """Ambil semua opportunities, urut berdasarkan score DESC."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM opportunities ORDER BY score DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_opportunity_count(db_path: Optional[str] = None) -> int:
    """Hitung jumlah opportunities di database."""
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    conn.close()
    return count


def get_existing_urls(db_path: Optional[str] = None) -> set[str]:
    """Ambil semua URL yang sudah ada di raw_pages."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT url FROM raw_pages").fetchall()
    conn.close()
    return {row["url"] for row in rows}


def get_existing_canonical_keys(db_path: Optional[str] = None) -> set[str]:
    """Ambil semua canonical_key yang sudah ada."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT canonical_key FROM opportunities").fetchall()
    conn.close()
    return {row["canonical_key"] for row in rows}


def reset_db(db_path: Optional[str] = None) -> None:
    """Hapus semua data dari database."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM raw_results")
    conn.execute("DELETE FROM raw_pages")
    conn.execute("DELETE FROM crawl_queue")
    conn.execute("DELETE FROM opportunities")
    conn.execute("DELETE FROM rejected_candidates")
    conn.execute("DELETE FROM discovery_candidates")
    conn.execute("DELETE FROM raw_api_responses")
    conn.execute("DELETE FROM opportunities_fts")
    conn.commit()
    conn.close()
    console.print("[yellow][OK][/yellow] Database reset")
