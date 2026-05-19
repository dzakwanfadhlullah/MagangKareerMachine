# DASHBOARD_SPECS.md

## 1. Ringkasan produk

MagangKareer adalah internship discovery engine dan application tracker untuk membantu user menemukan, menyimpan, dan memantau proses lamaran magang dari berbagai platform publik.

Tujuan utama MagangKareer:

- Menemukan lowongan magang dari job board, career page, dan hasil search publik.
- Membersihkan dan menormalisasi data lowongan menjadi format yang bisa dipakai dashboard.
- Memberi skor relevansi agar user bisa memprioritaskan peluang terbaik.
- Menyediakan workspace untuk menyimpan lowongan dan mencatat progres lamaran.

Manfaat untuk user:

- User tidak perlu mengecek banyak platform satu per satu.
- User bisa melihat lowongan dari berbagai sumber dalam satu dashboard.
- User bisa memfilter berdasarkan role, lokasi, work mode, platform, dan kualitas data.
- User bisa menyimpan lowongan yang menarik dan melacak status lamaran secara manual.

MagangKareer bukan auto-apply tool. Apply tetap diarahkan ke platform asli melalui `source_url` atau `apply_url`. Dashboard tidak mengirim lamaran menggantikan user, tidak bypass login, dan tidak mengisi form otomatis di platform pihak ketiga.

Dashboard berfungsi sebagai:

- Discovery: mencari dan membaca peluang magang.
- Save: menyimpan lowongan yang ingin diikuti.
- Tracking: mencatat status lamaran secara manual.
- Career workspace: tempat user mengelola peluang, catatan, histori, dan prioritas karier.

## 2. Engine capabilities yang sudah ada

Audit berdasarkan kode saat ini:

### Research mode

Sudah ada.

Command:

```bash
python main.py research --query "frontend developer internship" --location "Indonesia"
python main.py research --target-category actuarial --profile normal
```

Kemampuan utama:

- Search-index-first discovery.
- Role-aware query planning.
- Profile `fast`, `normal`, dan `deep`.
- Provider search `auto`, `ddg`, `brave`, `serper`, dan `tavily`.
- Deterministic seed URLs untuk platform inti.
- Ranking direct URL sebelum fetch.
- Page verification sebelum extract.
- Follow-up detail link discovery dari listing page.
- Jobstreet listing-card fallback yang konservatif.
- Metadata run lengkap melalui `run_metadata.json`.

### Crawl-sources mode

Sudah ada.

Command:

```bash
python main.py crawl-sources --profile quick
python main.py crawl-sources --profile normal --target-category actuarial
```

Kemampuan utama:

- Membaca manual/role/tiered sources dari `config/sources.yml`.
- Profile `quick`, `normal`, dan `deep`.
- Adapter platform untuk Dealls, Kalibrr, Glints, Jobstreet, Loker.id, Prosple, Indeed, dan generic fallback.
- Playwright fallback untuk platform SPA.
- Parsing detail links dari DOM, script, dan captured API JSON.
- Per-source cap, total detail cap, concurrent fetch, timeout.
- Target-aware prioritization.
- Source diagnostics di terminal.
- Export JSON/CSV dan run metadata.

### Search mode

Sudah ada.

Command:

```bash
python main.py search --query "frontend intern" --location "Indonesia"
```

Kemampuan utama:

- Query builder dari raw role/lokasi.
- Web search via DDG plus manual sources.
- Listing-to-detail pipeline.
- Extract, score, dedupe, save, export.

### Automate mode

Belum ada sebagai command khusus.

Tidak ditemukan command `automate`, auto-apply, atau automation untuk mengirim lamaran. Ini sesuai positioning produk: user apply di platform asli, lalu update status manual di dashboard.

### Validate-results

Sudah ada.

Command:

```bash
python main.py validate-results
python main.py validate-results --target-category actuarial
```

Gate yang dicek:

- Listing/category URL tidak boleh masuk accepted results.
- Tracking params tidak boleh tersisa di accepted canonical URLs.
- Bad titles.
- Non-internship.
- Invalid salary/duration.
- Non-detail pages.
- Closed/expired accepted results.
- Low role confidence.
- Suspicious role/category.
- Hard negative terms.
- Bad/low confidence company.
- WFH/work mode mismatch.
- Low metadata dan high-score-low-metadata.
- Source diversity warning.
- Target category integrity.

### Validate-dashboard-ready

Sudah ada.

Command:

```bash
python main.py validate-dashboard-ready --min-results 30
```

Gate yang dicek:

- Required dashboard fields.
- Dashboard-safe URL.
- Bad company.
- Valid enum untuk work mode, dashboard quality, extraction depth, dan active status.
- Duplicate source URL.
- Source diversity.
- Non-Glints full-detail coverage.
- Keberadaan schema `user_applications`.

### Export JSON/CSV

Sudah ada.

Command:

```bash
python main.py export
```

Output:

- `exports/results.json`
- `exports/results.csv`
- `exports/run_metadata.json`

Kolom export stabil didefinisikan di `engine/exporter.py`.

### Dashboard-safe export

Sudah ada.

Command:

```bash
python main.py export-dashboard
python main.py export-dashboard --output-dir exports/dashboard
```

Output:

- `opportunities.json`
- `metadata.json`

Export ini sengaja menghilangkan debug/raw fields seperti `raw_text` dan `original_url`.

### Metadata run

Sudah ada.

`run_metadata.json` menyimpan metadata seperti:

- command
- query
- location
- target_category
- profile
- provider
- query_count
- min_score
- worker/timeout
- result_count
- accepted_by_platform
- accepted_full_detail_by_platform
- accepted_partial_by_platform
- rejected_by_platform
- rejection_reasons_by_platform
- source_diversity_warning
- full_detail_source_diversity_warning
- focus_platform_diagnostics

### Accepted dan rejected candidates

Sudah ada.

Accepted results disimpan di tabel `opportunities`.

Rejected candidates disimpan di tabel `rejected_candidates` dengan:

- url
- title
- source_platform
- page_type
- rejection_reason
- internship_confidence
- role_confidence
- score
- text_snippet
- rejected_at

Command audit:

```bash
python main.py list-rejections
python main.py list-discovery
```

### Score dan score_breakdown

Sudah ada.

`score` berada di range 0-100. `score_breakdown` berisi:

- internship_score
- role_match_score
- source_quality_score
- metadata_completeness_score
- active_status_score
- field_confidence_score
- penalty_score
- final_score

### Role/category classification

Sudah ada.

Role yang tersedia antara lain:

- Software Engineering
- Frontend Developer
- Backend Developer
- Fullstack Developer
- Mobile Developer
- Quality Assurance
- IT Support
- Data Analyst
- Business Intelligence
- Data Engineer
- AI/ML Engineer
- Actuarial
- UI/UX Designer
- Product Manager

Category yang tersedia:

- tech
- data
- actuarial
- design
- product

Dashboard-oriented taxonomy juga sudah ada:

- role_family
- role_group
- role_specialization

### Internship gate

Sudah ada.

Extractor memakai multi-tier internship detection:

- Strong title signals: intern, internship, magang, apprentice, co-op.
- Strong description signals.
- Weak plus strong description signals.
- Hard reject untuk negative terms.
- Seniority reject untuk title seperti senior/manager/lead/head tanpa sinyal intern.
- Targeted search memperketat title-level internship signal.

### Target category filtering

Sudah ada.

`--target-category` bisa dipakai di `research`, `search`, `crawl-sources`, `validate-results`, dan `eval`.

Target dinormalisasi melalui alias seperti:

- tech
- frontend
- backend
- fullstack
- software_engineering
- data
- data_analyst
- ai_ml
- actuarial
- ui_ux
- product

### Source platform detection

Sudah ada.

Platform yang dikenali:

- dealls
- glints
- jobstreet
- kalibrr
- lokerid
- prosple
- indeed
- linkedin
- generic

Dashboard label juga tersedia melalui `source_platform_label`.

### Canonical URL

Sudah ada.

`canonicalize_url()` menghapus fragment dan tracking params umum seperti `utm_*`, `fbclid`, `gclid`, `ref`, `source`, dan lain-lain. Jobstreet juga dinormalisasi ke bentuk canonical `/job/{id}`.

`source_url` dan `detail_url` dipakai sebagai URL canonical/detail. `original_url` menyimpan URL sebelum canonicalization jika berbeda.

### Salary normalization

Sudah ada.

Field yang tersedia:

- salary
- salary_raw
- salary_display
- salary_min
- salary_max
- salary_confidence
- salary_status

Normalizer mendukung pola:

- Rp/IDR
- nilai tunggal
- range juta
- paid internship
- unpaid internship
- allowance/stipend

### Company confidence

Sudah ada.

Field:

- company
- company_confidence

Confidence tinggi jika company valid dan muncul di title. Company yang terlihat seperti lokasi, platform name, atau kalimat deskripsi akan ditolak.

### Source diversity metadata

Sudah ada.

Tersedia di run metadata dan dashboard metadata:

- accepted_by_platform
- accepted_full_detail_by_platform
- accepted_partial_by_platform
- source_diversity_warning
- full_detail_source_diversity_warning
- focus_platform_diagnostics untuk research mode

### Rejection reasons

Sudah ada.

Contoh rejection reasons:

- listing_page
- listing_title
- listing_or_category_url
- not_internship:no_signal
- not_internship:hard_reject
- not_internship:target_title_missing_internship
- suspicious_role:{term}
- out_of_scope_target:{target}
- out_of_location:{location}
- score_below_minimum
- closed

## 3. Data fields yang tersedia untuk dashboard

### Field opportunity utama

| Field | Status dashboard | Catatan |
| --- | --- | --- |
| id | User-facing | Identifier opportunity. Di dashboard-safe export dikirim sebagai string. |
| title | User-facing | Judul lowongan. |
| company | User-facing | Bisa null jika tidak terdeteksi. |
| role | User-facing | Role normalized. |
| category | User-facing | tech, data, actuarial, design, product. |
| company_confidence | Admin/debug | Berguna untuk data quality badge atau admin QA. |
| location | User-facing | Bisa null. Jangan dianggap error otomatis. |
| location_area | User-facing | Area normalized seperti jakarta_area, west_java, indonesia. |
| work_mode | User-facing | remote, hybrid, onsite, atau null. |
| duration | User-facing | Durasi magang jika tersedia. |
| salary_display | User-facing | Label salary yang aman ditampilkan. |
| salary_min | Admin/filter advanced | Numeric salary min jika bisa diparse. Belum masuk dashboard-safe export saat ini. |
| salary_max | Admin/filter advanced | Numeric salary max jika bisa diparse. Belum masuk dashboard-safe export saat ini. |
| salary_confidence | Admin/debug | Quality signal untuk salary. |
| deadline | User-facing | Deadline jika tersedia. |
| source_platform | User-facing | Platform source. |
| source_url | User-facing | URL canonical ke platform asli. |
| original_url | Debug/admin-only | URL sebelum canonicalization. Tidak masuk dashboard-safe export. |
| is_internship | Admin/debug | Gate result. Accepted results umumnya true. |
| internship_confidence | Admin/debug | Bisa dipakai internal QA. |
| role_confidence | Admin/debug | Bisa dipakai internal QA dan data quality badge. |
| score | User-facing | Ranking/relevance score. |
| score_breakdown | Admin/debug | Untuk explainability internal, tidak wajib user-facing. |
| page_type | Admin/debug | detail/listing/unknown. Accepted seharusnya detail. |
| extraction_status | Admin/debug | extracted/rejected. |
| summary | User-facing terbatas | Ringkasan detail. Untuk dashboard ringkas gunakan `summary_short`. |
| first_seen | User-facing | Kapan lowongan pertama kali ditemukan. |
| last_seen | User-facing/admin | Dipakai sebagai `last_verified_at` di dashboard-safe export. |

### Field tambahan yang sudah ada dan relevan

| Field | Status dashboard | Catatan |
| --- | --- | --- |
| canonical_key | Debug/admin-only | Dedupe key. Jangan tampilkan ke user. |
| salary | Legacy/user-facing terbatas | Sama/beririsan dengan salary_display. Prefer `salary_display`. |
| salary_raw | Debug/admin-only | Raw salary extraction. |
| salary_status | User-facing | Menjelaskan kenapa salary kosong. |
| location_status | User-facing | Menjelaskan kenapa location kosong. |
| duration_status | User-facing | Menjelaskan kenapa duration kosong. |
| deadline_status | User-facing | Menjelaskan kenapa deadline kosong. |
| location_confidence | Admin/debug | Quality signal. |
| detail_url | Admin/debug | Biasanya sama dengan source_url. |
| source_name | User-facing/admin | Domain source. |
| raw_text | Debug/admin-only | Jangan kirim ke dashboard user. |
| extraction_depth | User-facing | Basis quality badge. |
| verification_level | User-facing | Basis trust indicator. |
| dashboard_quality | User-facing | high, medium, low. |
| active_status | User-facing | active, listed, unknown, closed. |
| role_family | User-facing | Taxonomy tambahan. |
| role_group | User-facing | Taxonomy tambahan. |
| role_specialization | User-facing | Taxonomy tambahan. |
| mixed_employment_signal | User-facing/admin | Warning jika title campur intern/staff/full-time. |
| summary_short | User-facing | Ringkasan aman untuk card/list. |
| source_platform_label | User-facing | Label platform siap tampil. |
| apply_url | User-facing | URL untuk tombol Apply. Fallback ke source_url. |
| display_location | User-facing | Label location siap tampil, termasuk null-state copy. |
| display_salary | User-facing | Label salary siap tampil, termasuk null-state copy. |
| confidence | Admin/debug | Overall extraction confidence. |
| rejection_reason | Debug/admin-only | Biasanya dipakai di rejected candidates. |
| status | Internal | Status opportunity lama/default `new`, bukan application status user. |

### Dashboard-safe export saat ini

`engine/dashboard.py` sudah membatasi field untuk frontend:

- id
- title
- company
- role
- role_family
- role_group
- role_specialization
- category
- location
- location_area
- location_status
- work_mode
- salary_display
- salary_status
- duration
- duration_status
- deadline
- deadline_status
- source_platform
- source_platform_label
- source_url
- apply_url
- score
- dashboard_quality
- extraction_depth
- verification_level
- active_status
- mixed_employment_signal
- display_location
- display_salary
- summary_short
- first_seen
- last_verified_at

## 4. Fitur dashboard yang bisa dibuat dari field sekarang

### Search lowongan

Bisa dibuat dari:

- title
- company
- role
- category
- location
- summary_short
- SQLite FTS `opportunities_fts`

### Filter role

Bisa dibuat dari:

- role
- category
- role_family
- role_group
- role_specialization

### Filter lokasi

Bisa dibuat dari:

- location
- location_area
- display_location
- location_status

### Filter work mode

Bisa dibuat dari:

- work_mode

Value:

- remote
- hybrid
- onsite
- null/unknown

### Filter source platform

Bisa dibuat dari:

- source_platform
- source_platform_label

### Sort by score

Bisa dibuat dari:

- score
- dashboard_quality
- active_status
- first_seen
- last_verified_at

Default yang disarankan:

1. dashboard_quality high ke low
2. active_status active/listed
3. score desc
4. last_verified_at desc

### Saved jobs

Bisa dibuat dari tabel `user_applications` dengan status `saved`.

Catatan: schema sudah ada di `init_db`, tetapi function/API CRUD untuk save/update belum dibuat eksplisit.

### Application tracker

Bisa dibuat dari tabel `user_applications`.

Dashboard bisa menggabungkan:

- opportunity detail dari `opportunities`
- status user dari `user_applications`
- notes
- applied_at
- updated_at

### Detail drawer

Bisa dibuat dari:

- title
- company
- source_platform_label
- role/category
- location/display_location
- work_mode
- duration
- salary_display/display_salary
- deadline
- score
- dashboard_quality
- verification_level
- summary_short atau summary
- apply_url/source_url
- first_seen/last_verified_at

### Apply di platform asli

Bisa dibuat dari:

- apply_url
- source_url

Tombol CTA harus membuka platform asli. Copy yang disarankan: "Apply di platform asli".

### Watchlist keyword

Bisa dibuat sebagai fitur baru di dashboard walaupun schema khusus belum ada.

Untuk MVP, watchlist bisa disimpan sebagai setting user, lalu dipakai untuk memanggil:

- `research --query`
- `research --target-category`
- `crawl-sources --target-category`

Field engine yang mendukung matching:

- title
- role
- category
- role_specialization
- location
- source_platform
- score

### Run metadata/admin panel

Bisa dibuat dari:

- `exports/run_metadata.json`
- `exports/dashboard/metadata.json`

Panel admin bisa menampilkan:

- generated_at
- command terakhir
- result_count
- accepted_by_platform
- accepted_by_dashboard_quality
- accepted_by_extraction_depth
- accepted_full_detail_by_platform
- accepted_partial_by_platform
- source_diversity_warning
- full_detail_source_diversity_warning
- focus_platform_diagnostics

### Data quality badge

Bisa dibuat dari:

- dashboard_quality
- extraction_depth
- verification_level
- active_status
- company_confidence
- role_confidence
- salary_status
- location_status
- duration_status
- deadline_status

Contoh badge:

- High confidence
- Detail verified
- Listing only
- Search index only
- Some fields unavailable

### Source platform badge

Bisa dibuat dari:

- source_platform
- source_platform_label

Contoh:

- Glints
- Jobstreet
- Dealls
- Kalibrr
- LinkedIn indexed result
- Generic career page

## 5. Dashboard quality model

Field ini sudah ada di model dan database:

- extraction_depth
- verification_level
- dashboard_quality
- active_status

### extraction_depth

Value:

- full_detail
- listing_card
- search_snippet

Makna:

- `full_detail`: engine berhasil mengambil halaman detail dan mengekstrak konten dari detail page.
- `listing_card`: data berasal dari listing/card fallback, misalnya Jobstreet fallback ketika detail page anonim tidak bisa dibaca utuh.
- `search_snippet`: data berasal dari hasil search index, misalnya LinkedIn public indexed result.

Penggunaan dashboard:

- Tampilkan badge "Detail verified" untuk `full_detail`.
- Tampilkan badge "Listing card" untuk `listing_card`.
- Tampilkan badge "Search index" untuk `search_snippet`.
- Jangan menyamakan `listing_card` atau `search_snippet` dengan error. Keduanya tetap bisa berguna, tapi trust level lebih rendah.

### verification_level

Value:

- verified_detail
- listed_only
- search_index_only
- unknown

Makna:

- `verified_detail`: halaman detail berhasil diverifikasi.
- `listed_only`: lowongan terlihat di listing, tapi detail penuh terbatas.
- `search_index_only`: ditemukan lewat index publik, detail page belum/kurang diverifikasi.
- `unknown`: level verifikasi tidak pasti.

Penggunaan dashboard:

- Dipakai sebagai tooltip trust.
- Dipakai untuk filter "Tampilkan hanya detail terverifikasi".
- Dipakai untuk mengurutkan hasil yang paling bisa dipercaya.

### dashboard_quality

Value:

- high
- medium
- low

Makna:

- `high`: full detail, core metadata kuat, dan summary cukup.
- `medium`: data cukup untuk ditampilkan tapi tidak sekuat full-detail high confidence.
- `low`: field penting kurang lengkap atau ekstraksi lebih parsial.

Penggunaan dashboard:

- Badge kualitas di card/detail.
- Default sort bisa memprioritaskan high > medium > low.
- Low quality tetap boleh tampil jika user memilih "show all", tapi jangan terlalu dipromosikan.

### active_status

Value:

- active
- listed
- unknown
- closed

Makna:

- `active`: ada sinyal apply/lamar/posted dari detail page.
- `listed`: terlihat di listing, tapi belum tentu detail aktif penuh.
- `unknown`: tidak cukup bukti.
- `closed`: terdeteksi closed/expired. Accepted result seharusnya tidak menyimpan closed.

Penggunaan dashboard:

- Badge status.
- Filter "hide unknown/closed".
- Warning jika status `unknown`.
- Jika suatu saat ada `closed`, jangan tampilkan sebagai peluang utama.

## 6. Missing/null field handling

Salary, location, duration, dan deadline yang null tidak boleh otomatis dianggap false positive.

Alasan:

- Banyak platform memang tidak menampilkan salary.
- Beberapa lowongan tidak menulis durasi.
- Deadline sering tidak dicantumkan.
- Listing-card/search-snippet extraction memang hanya punya data parsial.

Bedakan null state berikut:

### not_provided

Platform/detail page tampaknya memang tidak mencantumkan field tersebut.

Contoh:

- Salary hidden dengan teks "salary not displayed".
- Full-detail page tidak memiliki deadline eksplisit.

### unknown_due_to_partial_extraction

Field kosong karena extraction source tidak penuh.

Contoh:

- `extraction_depth = listing_card`
- `extraction_depth = search_snippet`

Dashboard copy yang disarankan:

- "Belum tersedia"
- "Belum terverifikasi dari detail page"

### extraction_failed

Field seharusnya bisa diekstrak tetapi parser gagal.

Catatan: value ini belum dipakai eksplisit di `field_status()` saat ini, tetapi disarankan untuk V8/future.

### invalid

Field terdeteksi tapi tidak valid atau bertentangan.

Contoh:

- Deadline closed/expired.
- Salary string terlalu pendek/aneh.
- Duration lebih dari batas wajar.

### Field status yang disarankan/didukung

Sudah ada:

- salary_status
- location_status
- duration_status
- deadline_status

Value yang dipakai saat ini:

- provided
- not_provided
- unknown_due_to_partial_extraction
- invalid

Rekomendasi:

- Tambahkan `extraction_failed` untuk membedakan parser failure dari platform yang memang tidak menyediakan data.
- Dashboard harus memakai `display_salary` dan `display_location` untuk copy default, bukan membuat asumsi sendiri dari null.

## 7. Application tracking schema

Schema `user_applications` sudah dibuat di `init_db`.

```sql
CREATE TABLE IF NOT EXISTS user_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    opportunity_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'saved',
    notes TEXT,
    applied_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, opportunity_id),
    FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
)
```

Status yang disarankan:

- saved
- applied
- screening
- interview
- technical_test
- offer
- accepted
- rejected
- withdrawn

Catatan implementasi:

- `saved` berarti user menyimpan lowongan, belum tentu apply.
- `applied_at` diisi saat status pertama kali menjadi `applied` atau lebih jauh.
- `updated_at` harus berubah setiap status/notes berubah.
- Status lamaran ini berbeda dari field `opportunities.status` yang saat ini default `new`.

## 8. API / data contract untuk dashboard

Belum ada FastAPI/backend HTTP di repo saat ini. Namun data contract berikut bisa dibuat langsung dari SQLite dan modul yang sudah ada.

### GET /opportunities

Fungsi:

- Ambil daftar lowongan dashboard-safe.

Query params:

- q
- role
- category
- location_area
- work_mode
- source_platform
- dashboard_quality
- extraction_depth
- active_status
- min_score
- sort
- page
- page_size

Response item disarankan mengikuti `DASHBOARD_SAFE_FIELDS`.

### GET /opportunities/search

Fungsi:

- Full-text search lowongan.

Basis:

- `opportunities_fts`
- fallback LIKE untuk title/company/role/category/location.

### GET /opportunities/{id}

Fungsi:

- Ambil detail satu lowongan.

Response:

- Semua dashboard-safe fields.
- Bisa tambah `summary` untuk detail drawer.
- Jangan kirim `raw_text` ke user-facing client.

### POST /applications/save

Fungsi:

- Save opportunity untuk user.

Body:

```json
{
  "user_id": "user_123",
  "opportunity_id": 1
}
```

Behavior:

- Upsert ke `user_applications`.
- Default status `saved`.

### PATCH /applications/{id}

Fungsi:

- Update application status dan notes.

Body:

```json
{
  "status": "interview",
  "notes": "Interview HR hari Jumat",
  "applied_at": "2026-05-19T10:00:00+07:00"
}
```

### GET /applications

Fungsi:

- Ambil semua aplikasi user.

Query params:

- user_id
- status
- sort

Response:

- application fields
- joined opportunity card fields

### GET /runs/latest

Fungsi:

- Ambil metadata run terakhir.

Sumber:

- `exports/run_metadata.json`
- `exports/dashboard/metadata.json`

### POST /engine/research

Opsional/admin-only.

Fungsi:

- Trigger `research` dari dashboard admin/background worker.

Body:

```json
{
  "query": "frontend developer internship",
  "location": "Indonesia",
  "target_category": "frontend",
  "profile": "normal",
  "min_score": 40
}
```

Catatan:

- Jangan expose bebas ke user tanpa quota/rate limit.
- Untuk MVP user dashboard, engine run bisa tetap manual/cron.

## 9. Dashboard MVP scope

### Overview

Isi:

- Total opportunities.
- Total saved.
- Total applied.
- Status funnel lamaran.
- Latest run metadata.
- Source diversity warning.
- Quality distribution.

### Cari Lowongan

Isi:

- Search bar.
- Filter role/category.
- Filter lokasi/location_area.
- Filter work mode.
- Filter source platform.
- Filter quality.
- Sort by score/latest.
- Result cards.
- Empty/null states yang jelas.

### Detail Drawer

Isi:

- Title, company, platform badge.
- Score dan quality badge.
- Role/category.
- Location, salary, duration, deadline.
- Summary.
- Apply button ke platform asli.
- Save/update tracker action.
- Trust/verification tooltip.

### Saved

Isi:

- Semua application rows dengan status `saved`.
- Quick action: mark as applied, add note, remove/withdraw.

### Lamaran Saya

Isi:

- Kanban/list status:
  - saved
  - applied
  - screening
  - interview
  - technical_test
  - offer
  - accepted
  - rejected
  - withdrawn
- Notes.
- Applied date.
- Last updated.

### Settings

Isi:

- Watchlist keywords.
- Preferred roles/categories.
- Preferred locations.
- Preferred work mode.
- Export/import user data, jika diperlukan.
- Admin/dev panel visibility, jika user adalah admin.

## 10. Risiko dan caveat saat ini

### Glints lebih full-detail

Glints saat ini relatif lebih kuat untuk full-detail extraction karena adapter dan Playwright flow sudah matang. Dashboard boleh memberi trust badge lebih tinggi jika `extraction_depth = full_detail` dan `dashboard_quality = high`, bukan karena nama platform semata.

### Jobstreet sebagian masih listing-card fallback

Jobstreet kadang merender generic search shell untuk direct detail URL pada sesi anonim. Engine punya fallback konservatif dari listing card. Hasil seperti ini harus diberi badge `listing_card` atau `listed_only`.

### LinkedIn sebaiknya diperlakukan sebagai public indexed result

LinkedIn sering terbatas oleh login/indexing. Jika muncul, dashboard sebaiknya menandai sebagai `search_index_only` atau `unknown`, dan tetap mengarahkan apply ke URL asli.

### Dealls/Kalibrr perlu ditingkatkan

Adapter Dealls dan Kalibrr sudah ada, tetapi coverage full-detail non-Glints masih perlu dipantau lewat:

- accepted_full_detail_by_platform
- accepted_partial_by_platform
- focus_platform_diagnostics
- validate-dashboard-ready

### Missing salary/location belum tentu error

Salary/location/duration/deadline kosong bisa berarti:

- platform tidak mencantumkan,
- data hanya listing-card,
- data hanya search-snippet,
- parser belum kuat.

Dashboard harus menampilkan status/copy yang tepat, bukan menyimpulkan lowongan buruk.

### Dashboard perlu quality badge agar user trust

Tanpa quality badge, user bisa menganggap semua hasil punya tingkat verifikasi sama. Ini berisiko menurunkan trust. Minimal tampilkan:

- Platform badge.
- Quality badge.
- Verification badge.
- Last verified date.
- Null-state reason untuk salary/location/duration/deadline.

## 11. Rekomendasi V8 sebelum dashboard final

Checklist sebelum dashboard final:

- [x] `validate-dashboard-ready` command.
- [x] Dashboard-safe export JSON.
- [x] `user_applications` schema.
- [x] Quality tier fields: `extraction_depth`, `verification_level`, `dashboard_quality`, `active_status`.
- [x] Canonical URL dedupe dan tracking-param cleanup.
- [x] Source diversity diagnostics.
- [ ] CRUD/API untuk `user_applications`.
- [ ] Dashboard-safe detail endpoint/function.
- [ ] Watchlist schema.
- [ ] Field status `extraction_failed` untuk salary/location/duration/deadline.
- [ ] Tambahkan `salary_min` dan `salary_max` ke dashboard-safe export jika ingin filter numeric salary di frontend.
- [ ] Tambahkan `company_confidence` dan `role_confidence` ke admin-only dashboard endpoint.
- [ ] Perkuat non-Glints full-detail extraction, terutama Dealls, Kalibrr, dan Jobstreet.
- [ ] Pastikan LinkedIn selalu diberi treatment sebagai indexed/public result, bukan verified detail kecuali benar-benar bisa diverifikasi.
- [ ] Tambahkan API/background worker boundary agar dashboard tidak menjalankan crawl berat secara blocking.
- [ ] Tambahkan dedupe multi-source display jika satu lowongan muncul di beberapa platform.

Rekomendasi urutan teknis:

1. Finalisasi read model dashboard dari `export-dashboard`.
2. Tambahkan repository/function untuk list/search/detail opportunities.
3. Tambahkan CRUD `user_applications`.
4. Buat API minimal atau service layer.
5. Jalankan `validate-dashboard-ready` sebagai gate sebelum data dipakai frontend.
6. Perbaiki adapter non-Glints berdasarkan diagnostics.
7. Baru lanjutkan dashboard UI final.

