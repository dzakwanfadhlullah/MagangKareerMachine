# Rancangan MVP Engine — MagangKareer

> Dokumen acuan coding untuk membangun engine MagangKareer.
> Fokus: **engine only**, bukan dashboard.

---

## 1. Ringkasan Produk

MagangKareer Engine adalah mesin pencari peluang magang yang:

1. Mencari lowongan dari web publik dan seed URL
2. Mengambil konten halaman
3. Mengekstrak metadata lowongan secara rule-based
4. Memberi skor relevansi
5. Menghapus duplikat
6. Menyimpan ke SQLite
7. Mengekspor CSV/JSON/HTML report

**Tanpa** dashboard, login, payment, atau API berbayar.

---

## 2. Alur Pipeline

```
User Input (query + location)
       │
       ▼
┌──────────────┐
│ Query Builder │  Ekspansi keyword → beberapa search query
└──────┬───────┘
       ▼
┌──────────────┐
│   Searcher   │  DDGS / manual sources → list[RawSearchResult]
└──────┬───────┘
       ▼
┌──────────────┐
│   Fetcher    │  requests + trafilatura → list[RawPage]
└──────┬───────┘
       ▼
┌──────────────┐
│  Extractor   │  Regex + rules → list[Opportunity]
└──────┬───────┘
       ▼
┌──────────────┐
│   Scorer     │  Hitung skor 0–100
└──────┬───────┘
       ▼
┌──────────────┐
│   Deduper    │  canonical_key + rapidfuzz → hapus duplikat
└──────┬───────┘
       ▼
┌──────────────┐
│   Database   │  SQLite: raw_results, raw_pages, opportunities
└──────┬───────┘
       ▼
┌──────────────┐
│  Exporter    │  CSV + JSON
│  Reporter    │  HTML report
└──────────────┘
```

---

## 3. Tech Stack

| Komponen      | Library                        |
| ------------- | ------------------------------ |
| Bahasa        | Python 3.11+                   |
| CLI           | `typer` + `rich`           |
| HTTP          | `requests`                   |
| Parsing HTML  | `beautifulsoup4`             |
| Teks bersih   | `trafilatura`                |
| JS rendering  | `playwright` (opsional)      |
| Search engine | `duckduckgo-search`          |
| Data model    | `pydantic`                   |
| Data tabular  | `pandas`                     |
| Fuzzy match   | `rapidfuzz`                  |
| Konfigurasi   | `pyyaml` + `python-dotenv` |
| Database      | `sqlite3` (built-in)         |

---

## 4. Struktur Folder

```
magangkareer-engine/
├── main.py                  # Entry point CLI
├── requirements.txt
├── .env.example
├── config/
│   ├── keywords.yml         # Daftar keyword role, lokasi, sinyal
│   ├── sources.yml          # Manual seed URLs + setting search
│   └── scoring.yml          # Bobot skor dan penalti
├── data/
│   └── magangkareer.db      # SQLite database
├── exports/
│   ├── results.csv
│   ├── results.json
│   └── report.html
├── engine/
│   ├── __init__.py
│   ├── cli.py               # Definisi command Typer
│   ├── db.py                # Koneksi + CRUD SQLite
│   ├── models.py            # Pydantic models
│   ├── query_builder.py     # Ekspansi query
│   ├── searcher.py          # Search web + manual sources
│   ├── fetcher.py           # Fetch + extract teks halaman
│   ├── extractor.py         # Metadata extraction (rule-based)
│   ├── scorer.py            # Scoring engine
│   ├── deduper.py           # Deduplikasi
│   ├── exporter.py          # Export CSV/JSON
│   ├── reporter.py          # Generate HTML report
│   └── pipeline.py          # Orchestrator seluruh alur
└── tests/
    ├── test_extractor.py
    ├── test_scorer.py
    └── test_deduper.py
```

---

## 5. Data Model (Pydantic)

### RawSearchResult

```python
class RawSearchResult(BaseModel):
    query: str
    title: str
    snippet: Optional[str] = None
    url: str
    source: str = "web"
```

### RawPage

```python
class RawPage(BaseModel):
    url: str
    title: Optional[str] = None
    text_content: str
    status_code: int
```

### Opportunity

```python
class Opportunity(BaseModel):
    title: str
    company: Optional[str] = None
    role: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None      # remote | hybrid | onsite
    duration: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[str] = None
    source_url: str
    source_name: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    score: int = 0
    confidence: int = 0
```

---

## 6. Database Schema (SQLite)

### Tabel `raw_results`

Menyimpan hasil pencarian mentah sebelum fetch.

```sql
CREATE TABLE IF NOT EXISTS raw_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    title TEXT,
    snippet TEXT,
    url TEXT UNIQUE,
    source TEXT,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Tabel `raw_pages`

Menyimpan konten halaman yang sudah di-fetch.

```sql
CREATE TABLE IF NOT EXISTS raw_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    title TEXT,
    text_content TEXT,
    status_code INTEGER,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Tabel `opportunities`

Menyimpan lowongan final yang sudah dinormalisasi.

```sql
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT UNIQUE,
    title TEXT,
    company TEXT,
    role TEXT,
    category TEXT,
    location TEXT,
    work_mode TEXT,
    duration TEXT,
    salary TEXT,
    deadline TEXT,
    source_url TEXT,
    source_name TEXT,
    raw_text TEXT,
    summary TEXT,
    score INTEGER,
    confidence INTEGER,
    status TEXT DEFAULT 'new',
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Tabel `opportunities_fts`

Full-text search lokal.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS opportunities_fts
USING fts5(
    title, company, role, category, location, raw_text,
    content='opportunities', content_rowid='id'
);
```

---

## 7. Spesifikasi Per Modul

### 7.1 Query Builder (`query_builder.py`)

**Input:** `role` + `location`
**Output:** List query string untuk searcher

Logika:

- Baca `keywords.yml` → ambil sinonim role
- Kombinasi dengan `internship_terms` (intern, internship, magang, trainee)
- Gabung dengan lokasi

Contoh output untuk `role=frontend, location=Indonesia`:

```
"frontend intern" "Indonesia"
"frontend internship" "Indonesia"
"magang frontend" "Indonesia"
"react intern" "Indonesia"
```

### 7.2 Searcher (`searcher.py`)

**Input:** List query string
**Output:** `list[RawSearchResult]`

Strategi:

1. **DDGS** — Cari via `duckduckgo-search`, max 20 result/query
2. **Manual sources** — Baca `sources.yml`, generate RawSearchResult dari seed URL
3. **Fallback** — Jika DDGS gagal, tetap jalan pakai manual sources saja

Simpan semua hasil ke tabel `raw_results`.

### 7.3 Fetcher (`fetcher.py`)

**Input:** `list[RawSearchResult]`
**Output:** `list[RawPage]`

Aturan:

- Gunakan `requests` + `trafilatura` untuk ekstrak teks bersih
- Fallback ke `BeautifulSoup` jika trafilatura gagal
- Playwright hanya untuk halaman yang butuh JS rendering
- Timeout: 15 detik
- Skip jika: login page, CAPTCHA, 401/403/429, konten < 200 karakter, file binary

Simpan semua halaman ke tabel `raw_pages`.

### 7.4 Extractor (`extractor.py`)

**Input:** `RawPage`
**Output:** `Opportunity | None`

Ekstraksi rule-based:

| Field      | Metode                                               |
| ---------- | ---------------------------------------------------- |
| title      | Dari `<title>` atau heading pertama                |
| company    | Regex: "at {company}", "— {company}", "PT ..."      |
| role       | Cocokkan keyword dari `keywords.yml`               |
| category   | Map dari role → kategori (tech, finance, actuarial) |
| location   | Regex: nama kota/provinsi Indonesia                  |
| work_mode  | Deteksi: remote/WFH/hybrid/WFO/on-site               |
| duration   | Regex: "3 bulan", "6 months", dll                    |
| salary     | Regex: "Rp", "juta", "IDR", "allowance", "unpaid"    |
| deadline   | Regex: berbagai format tanggal ID/EN                 |
| confidence | 0–100 berdasarkan berapa field terisi               |

Filter:

- **Positif:** intern, internship, magang, trainee, mahasiswa
- **Negatif:** bootcamp, course, kelas, webinar → skip/penalti

### 7.5 Scorer (`scorer.py`)

**Input:** `Opportunity`
**Output:** `Opportunity` dengan field `score` terisi

Formula (berdasarkan `scoring.yml`):

| Sinyal                   | Poin |
| ------------------------ | ---- |
| Internship terdeteksi    | +30  |
| Role terdeteksi          | +25  |
| Lokasi terdeteksi        | +10  |
| Sinyal "apply/lamar"     | +10  |
| Deadline terdeteksi      | +10  |
| Sumber resmi/career page | +10  |
| Remote                   | +5   |
| Ada info gaji/paid       | +5   |
| Bootcamp/course          | −40 |
| Expired                  | −50 |

**Skor 0–100.** Clamp ke [0, 100].

Threshold:

- `score >= 40` → simpan ke database
- `score < 40` → abaikan

### 7.6 Deduper (`deduper.py`)

**Input:** `list[Opportunity]`
**Output:** `list[Opportunity]` tanpa duplikat

Strategi:

1. Normalisasi: lowercase, strip whitespace, hapus karakter spesial
2. Generate `canonical_key`:
   - Jika company diketahui: `hash(company|role|location|title)`
   - Jika company tidak diketahui: `hash(title|domain_url)`
3. Cek fuzzy similarity dengan `rapidfuzz` (threshold > 90%)
4. Jika duplikat: update `last_seen`, simpan skor tertinggi

### 7.7 Exporter (`exporter.py`)

Ekspor dari tabel `opportunities` ke:

- **CSV** → `exports/results.csv`
- **JSON** → `exports/results.json`

Kolom: id, score, title, company, role, category, location, work_mode, duration, salary, deadline, source_name, source_url, summary, first_seen, last_seen.

Urutkan berdasarkan `score DESC`.

### 7.8 Reporter (`reporter.py`)

Generate `exports/report.html` berisi:

- Total lowongan tersimpan
- Jumlah lowongan baru (hari ini)
- Top 20 berdasarkan skor
- Distribusi role
- Distribusi lokasi
- Distribusi sumber
- Timestamp generate

HTML statis sederhana, bisa dibuka di browser tanpa server.

### 7.9 Pipeline (`pipeline.py`)

Orchestrator yang merangkai semua modul:

```python
def run_search(query: str, location: str, limit: int = 20):
    queries = build_queries(query, location)
    raw_results = search(queries, limit)
    save_raw_results(raw_results)

    pages = fetch(raw_results)
    save_raw_pages(pages)

    opportunities = extract(pages)
    opportunities = score(opportunities)
    opportunities = dedupe(opportunities)

    save_opportunities(opportunities)  # filter score >= 40

    export_csv()
    export_json()
    generate_report()
```

---

## 8. CLI Commands

| Command           | Fungsi                                       |
| ----------------- | -------------------------------------------- |
| `init`          | Buat database + folder data/exports          |
| `search`        | Jalankan pipeline penuh (query + location)   |
| `crawl-sources` | Crawl dari manual sources di `sources.yml` |
| `list`          | Tampilkan top result di terminal             |
| `export`        | Ekspor CSV + JSON                            |
| `report`        | Generate HTML report                         |
| `reset`         | Hapus semua data (reset database)            |

Contoh penggunaan:

```bash
python main.py init
python main.py search --query "frontend intern" --location "Indonesia"
python main.py search --query "actuarial internship" --location "Indonesia"
python main.py list --limit 20
python main.py export
python main.py report
```

---

## 9. Urutan Build (Sprint Plan)

### Sprint 1 — Fondasi + Crawl Manual

```
[1] Database schema + db.py
[2] Pydantic models
[3] CLI skeleton (typer)
[4] Config files (keywords.yml, sources.yml, scoring.yml)
[5] Fetcher — fetch manual sources
[6] Extractor — rule-based
[7] Scorer
[8] Deduper
[9] Simpan ke SQLite
[10] Export CSV
```

Target: `python main.py crawl-sources` → menghasilkan `results.csv`

### Sprint 2 — Web Search + Report

```
[11] Query builder
[12] Searcher (DDGS integration)
[13] Pipeline orchestrator
[14] JSON export
[15] HTML report
```

Target: `python main.py search --query "..." --location "..."` → full pipeline

### Sprint 3 — Polish

```
[16] Rich terminal output
[17] Error handling & retry
[18] Basic tests
[19] Playwright fallback untuk halaman JS-heavy
```

---

## 10. Acceptance Criteria

MVP diterima jika:

1. `python main.py init` → membuat DB + folder
2. `python main.py search --query "frontend intern" --location "Indonesia"` → berjalan tanpa crash
3. Engine menyimpan raw results ke DB
4. Engine fetch halaman publik
5. Engine mengekstrak opportunity
6. Engine memberi skor
7. Engine deduplikasi berdasarkan canonical key
8. Engine mengekspor CSV dan JSON
9. Engine generate HTML report
10. Engine berjalan **tanpa API berbayar**

---

## 11. Output yang Dihasilkan

```
data/magangkareer.db       ← SQLite database
exports/results.csv        ← Semua opportunity, urut skor
exports/results.json       ← Format JSON
exports/report.html        ← Ringkasan visual
```

---

## 12. Catatan Penting

- **Tidak membangun** dashboard, login, payment, atau fitur premium.
- **Tidak menggunakan** GPT/OpenAI API atau API berbayar lainnya.
- Bisa Bypass login wall, CAPTCHA, atau anti-bot.
- Engine harus berjalan dengan **sumber publik saja**.
- Desain database sudah menyimpan metadata cukup untuk fitur premium di masa depan.
