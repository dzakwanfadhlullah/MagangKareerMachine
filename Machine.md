
# `ENGINE_DNA.md`

## 1. Product DNA

**MagangKareer Engine** adalah mesin pencari peluang magang yang berjalan otomatis untuk menemukan, mengambil, membersihkan, menilai, dan menyimpan lowongan magang dari berbagai sumber publik.

Tujuan utama MVP:

```text
User memasukkan keyword role/lokasi
↓
Engine mencari peluang magang dari web/source publik
↓
Engine mengambil detail halaman
↓
Engine mengekstrak metadata lowongan
↓
Engine memberi skor relevansi
↓
Engine menghapus duplikat
↓
Engine menyimpan hasil ke SQLite
↓
Engine menghasilkan CSV/JSON/HTML report
```

Engine ini belum membutuhkan dashboard. Output awal cukup:

```text
data/magangkareer.db
exports/results.csv
exports/results.json
exports/report.html
```

Nanti dashboard setelah login akan membaca data dari database/API ini.

---

## 2. MVP Goal

MVP harus bisa melakukan 5 hal:

```text
1. Search peluang magang berdasarkan keyword
2. Crawl/fetch halaman publik dari URL hasil pencarian
3. Extract metadata lowongan
4. Score dan ranking hasil
5. Export hasil agar bisa dicek tanpa dashboard
```

Contoh command:

```bash
python main.py search --query "frontend intern" --location "Indonesia"
python main.py search --query "data analyst intern" --location "Jakarta"
python main.py search --query "actuarial internship" --location "Indonesia"
python main.py export
python main.py report
```

Output terminal:

```text
[OK] Found 42 raw results
[OK] Fetched 28 pages
[OK] Extracted 17 internship opportunities
[OK] Saved 12 new opportunities
[OK] Exported to exports/results.csv
[OK] Report generated at exports/report.html
```

---

## 3. MVP Scope

### In scope

```text
- Public web search
- Job board public pages
- Career page public pages
- Manual seed URLs
- Basic crawler
- Basic text extraction
- Rule-based metadata extraction
- Rule-based scoring
- SQLite database
- CSV/JSON/HTML export
- CLI interface
```

### Out of scope for MVP

```text
- Login system
- User dashboard
- Payment
- Premium quota
- Browser automation for Instagram/LinkedIn
- Bypass login wall
- Captcha solving
- GPT/OpenAI API
- Full AI recommendation
```

Important principle:

```text
MVP engine must work without paid API.
```

Optional later:

```text
- Ollama local LLM
- FastAPI backend
- Meilisearch
- Supabase
- Telegram alert
- Email alert parser
```

---

## 4. Tech Stack

### Language

```text
Python 3.11+
```

### Core libraries

```text
requests
beautifulsoup4
trafilatura
pandas
pydantic
typer
rich
rapidfuzz
python-dotenv
sqlite-utils optional
```

### Search library

```text
duckduckgo-search / ddgs
```

### Browser rendering

```text
playwright
```

Only use Playwright for public pages that require JavaScript rendering. use Playwright to bypass login, CAPTCHA, or anti-bot protection.

---

## 5. Project Structure

```text
magangkareer-engine/
├── main.py
├── requirements.txt
├── .env.example
├── config/
│   ├── keywords.yml
│   ├── sources.yml
│   └── scoring.yml
├── data/
│   └── magangkareer.db
├── exports/
│   ├── results.csv
│   ├── results.json
│   └── report.html
├── engine/
│   ├── __init__.py
│   ├── cli.py
│   ├── db.py
│   ├── models.py
│   ├── query_builder.py
│   ├── searcher.py
│   ├── fetcher.py
│   ├── extractor.py
│   ├── scorer.py
│   ├── deduper.py
│   ├── exporter.py
│   ├── reporter.py
│   └── pipeline.py
└── tests/
    ├── test_extractor.py
    ├── test_scorer.py
    └── test_deduper.py
```

---

## 6. Data Flow

```text
User Query
  ↓
Query Builder
  ↓
Search Engine / Source Adapter
  ↓
Raw Search Results
  ↓
Fetcher
  ↓
Raw Page Text
  ↓
Extractor
  ↓
Opportunity Object
  ↓
Scorer
  ↓
Deduper
  ↓
SQLite Database
  ↓
CSV / JSON / HTML Report
```

---

## 7. Source Strategy

MVP tidak perlu langsung “crawl semua internet”. Gunakan 3 jalur source.

### Source A — Web search

Input:

```text
frontend intern Indonesia
data analyst internship Jakarta
actuarial internship Indonesia
software engineer intern remote
```

Query expansion:

```text
"{role} intern" "{location}"
"{role} internship" "{location}"
"magang {role}" "{location}"
"{role} intern" "apply"
"{role} internship" "Indonesia"
```

### Source B — Known job boards

Seed source awal:

```text
Jobstreet
Glints
Dealls
Kalibrr
Prosple
Indeed
Company career pages
```

### Source C — Manual seed URLs

User bisa memasukkan URL manual ke:

```text
config/sources.yml
```

Contoh:

```yaml
manual_sources:
  - https://www.jobstreet.co.id/id/frontend-developer-internship-jobs
  - https://www.jobstreet.co.id/id/data-analyst-internship-jobs
  - https://glints.com/id/en/find-jobs/loker-front-end-developer-internship
  - https://dealls.com/loker
```

---

## 8. Configuration Files

### `config/keywords.yml`

```yaml
internship_terms:
  - intern
  - internship
  - magang
  - trainee
  - apprentice

role_keywords:
  frontend:
    - frontend
    - front-end
    - react
    - next.js
    - vue
    - ui engineer

  backend:
    - backend
    - back-end
    - api
    - node.js
    - fastapi
    - spring boot
    - golang

  fullstack:
    - fullstack
    - full-stack
    - full stack

  mobile:
    - mobile
    - android
    - ios
    - flutter
    - kotlin
    - react native

  data_analyst:
    - data analyst
    - analytics
    - dashboard
    - sql
    - excel
    - power bi
    - tableau

  data_engineer:
    - data engineer
    - etl
    - pipeline
    - data warehouse
    - bigquery

  ai_ml:
    - ai engineer
    - machine learning
    - ml engineer
    - llm
    - computer vision
    - nlp

  actuarial:
    - actuarial
    - actuary
    - aktuaria
    - pricing
    - valuation
    - reserving
    - insurance liability

locations:
  - Indonesia
  - Jakarta
  - Bandung
  - Tangerang
  - Remote
  - Hybrid
  - Surabaya
  - Yogyakarta

negative_terms:
  - bootcamp
  - course
  - kelas
  - training berbayar
  - paid class
  - webinar
  - seminar
```

### `config/scoring.yml`

```yaml
score:
  internship_detected: 30
  role_detected: 25
  location_detected: 10
  apply_signal: 10
  deadline_detected: 10
  official_career_source: 10
  remote_bonus: 5
  paid_signal: 5

penalty:
  bootcamp: -40
  course: -35
  expired: -50
  not_internship: -100
```

### `config/sources.yml`

```yaml
search:
  enabled: true
  max_results_per_query: 20

manual_sources:
  - https://www.jobstreet.co.id/id/frontend-developer-internship-jobs
  - https://www.jobstreet.co.id/id/data-analyst-internship-jobs
  - https://www.jobstreet.co.id/id/software-engineer-internship-jobs
  - https://glints.com/id/en/find-jobs/loker-front-end-developer-internship
  - https://glints.com/id/en/find-jobs/loker-data-analyst-internship
  - https://dealls.com/loker
  - https://www.kalibrr.id/id-ID/job-board
```

---

## 9. Database Schema

Use SQLite.

### Table: `raw_results`

Stores search results before fetching.

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

### Table: `raw_pages`

Stores fetched page content.

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

### Table: `opportunities`

Stores final normalized internship opportunities.

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

### Table: `opportunities_fts`

For local search.

```sql
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
);
```

---

## 10. Data Model

Use Pydantic.

```python
from pydantic import BaseModel
from typing import Optional

class RawSearchResult(BaseModel):
    query: str
    title: str
    snippet: Optional[str] = None
    url: str
    source: str = "web"

class RawPage(BaseModel):
    url: str
    title: Optional[str] = None
    text_content: str
    status_code: int

class Opportunity(BaseModel):
    title: str
    company: Optional[str] = None
    role: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
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

## 11. Query Builder

Input:

```text
role = frontend
location = Indonesia
```

Output queries:

```text
"frontend intern" "Indonesia"
"frontend internship" "Indonesia"
"magang frontend" "Indonesia"
"front end developer intern" "Indonesia"
"react intern" "Indonesia"
"next.js intern" "Indonesia"
```

For field-specific examples:

### Tech

```text
frontend intern Indonesia
backend intern Indonesia
fullstack internship Indonesia
mobile developer intern Indonesia
data analyst intern Indonesia
software engineer internship Indonesia
```

### Actuarial

```text
actuarial internship Indonesia
actuary intern Indonesia
magang aktuaria
pricing actuarial intern
valuation actuarial intern
insurance actuarial internship
```

### Finance

```text
finance intern Indonesia
risk analyst intern Indonesia
investment intern Indonesia
banking intern Indonesia
```

---

## 12. Searcher

Searcher responsibility:

```text
- Accept query
- Return list of RawSearchResult
- Do not fetch page detail yet
```

MVP searcher options:

```text
1. Use DDGS / duckduckgo-search
2. Use manual sources
3. Use known job-board search URLs
```

Pseudo-code:

```python
def search_web(query: str, max_results: int = 20) -> list[RawSearchResult]:
    results = []

    # use public search library if available
    # fallback to manual seed URLs

    return results
```

If search engine fails, MVP must still work using `manual_sources`.

---

## 13. Fetcher

Fetcher responsibility:

```text
- Fetch URL
- Extract readable text
- Store raw page
```

Rules:

```text
- Use requests first
- Use trafilatura to extract readable text
- Use BeautifulSoup fallback
- Use Playwright only if necessary
- Timeout max 15 seconds
- Skip binary files
- Skip login pages
- Skip CAPTCHA pages
```

Fetcher must detect bad pages:

```text
- login required
- forbidden
- CAPTCHA
- too short content
- unrelated content
```

Example logic:

```python
if "captcha" in text.lower():
    skip

if "login" in title.lower() and len(text) < 1000:
    skip

if status_code in [401, 403, 429]:
    skip
```

---

## 14. Extractor

Extractor responsibility:

```text
Raw text → structured opportunity
```

MVP uses rules and regex.

### Extract fields

```text
title
company
role
category
location
work_mode
duration
salary
deadline
summary
confidence
```

### Internship detection

Positive signals:

```text
intern
internship
magang
trainee
apprentice
program magang
mahasiswa
fresh graduate
semester akhir
```

Negative signals:

```text
bootcamp
course
kelas
pelatihan berbayar
webinar
seminar
```

### Role detection

Use role keyword mapping from `keywords.yml`.

Example:

```text
If text contains react, next.js, frontend → Frontend Developer
If text contains android, flutter, kotlin → Mobile Developer
If text contains SQL, dashboard, data analysis → Data Analyst
If text contains actuarial, pricing, valuation → Actuarial Intern
```

### Deadline detection

Regex patterns:

```text
19 Mei 2026
30 May 2026
2026-05-19
19/05/2026
Apply before 30 June
Penutupan lamaran: 19 Mei 2026
```

### Work mode detection

```text
Remote → remote
WFH → remote
Hybrid → hybrid
WFO → onsite
On-site → onsite
```

### Salary detection

```text
Rp3.000.000
3-5 juta
IDR 2,000,000
paid internship
unpaid
uang saku
allowance
```

---

## 15. Scoring Engine

Final score range:

```text
0–100
```

Score formula:

```text
score =
  internship_score
+ role_score
+ location_score
+ apply_signal_score
+ deadline_score
+ source_score
+ freshness_score
+ remote_bonus
- noise_penalty
```

### Example scoring

```text
+30 if internship detected
+25 if role detected
+10 if location detected
+10 if apply/lamar signal exists
+10 if deadline detected
+10 if official source/career page
+5 if remote
+5 if paid signal
-40 if bootcamp/course
-50 if expired
```

### Score interpretation

```text
90–100 = very relevant
75–89 = relevant
60–74 = possible
40–59 = weak
0–39 = ignore
```

Only save item if:

```text
score >= 40
```

Only include in premium-worthy result later if:

```text
score >= 70
```

---

## 16. Deduplication

Problem:

```text
Same internship can appear on Jobstreet, LinkedIn, company career page, reposts, etc.
```

MVP dedupe:

```text
1. Normalize URL
2. Normalize title
3. Normalize company
4. Generate canonical_key
```

Canonical key:

```python
canonical_key = hash(
    normalize(company) + "|" +
    normalize(role) + "|" +
    normalize(location) + "|" +
    normalize(title)
)
```

If company is unknown:

```python
canonical_key = hash(normalize(title) + "|" + normalize(source_url_domain))
```

Use `rapidfuzz` for fuzzy title similarity.

If similarity > 90 and role/location close:

```text
Consider duplicate
```

When duplicate found:

```text
- update last_seen
- keep highest score
- optionally store additional source URL later
```

---

## 17. Exporter

The engine must export data after every run.

### CSV export

Path:

```text
exports/results.csv
```

Columns:

```text
id
score
title
company
role
category
location
work_mode
duration
salary
deadline
source_name
source_url
summary
first_seen
last_seen
```

### JSON export

Path:

```text
exports/results.json
```

Use array of opportunity objects.

### HTML report

Path:

```text
exports/report.html
```

Report should include:

```text
- total opportunities
- new opportunities
- top 20 by score
- role distribution
- location distribution
- source distribution
- generated timestamp
```

This makes the engine usable before dashboard exists.

---

## 18. CLI Commands

Use Typer.

### Basic commands

```bash
python main.py init
python main.py search --query "frontend intern" --location "Indonesia"
python main.py crawl-sources
python main.py export
python main.py report
python main.py list
python main.py reset
```

### Command details

#### `init`

Create database and folders.

```bash
python main.py init
```

#### `search`

Run full search pipeline.

```bash
python main.py search --query "data analyst intern" --location "Jakarta" --limit 30
```

Flow:

```text
build queries
search web
save raw results
fetch pages
extract opportunities
score
dedupe
save
export
```

#### `crawl-sources`

Crawl manual source list.

```bash
python main.py crawl-sources
```

#### `list`

Show top results in terminal.

```bash
python main.py list --limit 20
```

#### `export`

Export CSV and JSON.

```bash
python main.py export
```

#### `report`

Generate HTML report.

```bash
python main.py report
```

---

## 19. Minimum Working Example

After implementation, this should work:

```bash
python main.py init
python main.py search --query "frontend intern" --location "Indonesia"
python main.py list
python main.py report
```

Expected terminal output:

```text
Top Opportunities

[92] Frontend Developer Intern — PT Example
     Jakarta / Hybrid
     Source: glints.com
     URL: https://...

[87] Front End Internship — Company ABC
     Remote
     Source: jobstreet.co.id
     URL: https://...
```

Expected files:

```text
data/magangkareer.db
exports/results.csv
exports/results.json
exports/report.html
```

---

## 20. Later Integration with Dashboard

Dashboard does not need to run crawler directly at first.

Dashboard will read from:

```text
SQLite database
or
FastAPI endpoint
```

Future endpoints:

```text
GET /opportunities
GET /opportunities/{id}
GET /search?q=frontend
POST /watchlists
POST /saved-jobs
POST /run-search
```

But for MVP engine, API is optional.

---

## 21. Future Premium Logic

Premium logic should not be built in MVP engine yet, but design should support it.

Future premium features:

```text
- daily watchlist automation
- more searches per day
- unlimited saved jobs
- advanced filters
- deadline alerts
- match score
- CV-based matching
- export
```

Engine should store enough metadata for premium later:

```text
score
source
deadline
role
location
first_seen
last_seen
summary
```

---

## 22. MVP Acceptance Criteria

The MVP is accepted if:

```text
1. `python main.py init` creates DB and folders
2. `python main.py search --query "frontend intern" --location "Indonesia"` runs without crashing
3. Engine stores at least some raw results
4. Engine fetches public pages
5. Engine extracts internship-like opportunities
6. Engine scores opportunities
7. Engine deduplicates by URL/canonical key
8. Engine exports CSV and JSON
9. Engine generates HTML report
10. Engine can run without paid API
```

---

## 23. Development Priority

Build in this order:

```text
1. Database schema
2. CLI setup
3. Manual source crawler
4. Fetcher
5. Extractor
6. Scorer
7. Deduper
8. Exporter
9. HTML report
10. Web search integration
11. Scheduler
12. FastAPI integration
```

Do not build dashboard until engine produces usable data.

---

## 24. Recommended First Build

First sprint target:

```text
A CLI engine that crawls manual sources and produces CSV.
```

Do not start with complex search.

Build this first:

```text
sources.yml
↓
fetcher
↓
extractor
↓
scorer
↓
SQLite
↓
CSV
```

Then add web search.

---

## 25. Product Principle

MagangKareer Engine is not just a scraper.

It is:

```text
Discovery engine
+ Extraction engine
+ Ranking engine
+ Opportunity database
```

The dashboard is only the interface.

The real product value is the engine.
