# whoosh-absa

Project ini melakukan Aspect-Based Sentiment Analysis (ABSA) terhadap review Google Maps Stasiun Kereta Cepat
Whoosh **Tegalluar** (Kab. Bandung), khusus opini tentang **konektivitas transportasi
menuju/dari stasiun**. Seluruh project 100% gratis: model open-source yang berjalan lokal di CPU, tanpa API berbayar.
Label ground truth dibuat **manual oleh peneliti** di Label Studio.

## Mulai cepat: menjalankan dashboard dari repo ini

```bash
git clone <url-repo> && cd whoosh-absa
python -m venv .venv
.venv/Scripts/pip install -r requirements-dashboard.txt     # Linux/Mac: .venv/bin/pip
.venv/Scripts/streamlit run app/streamlit_app.py           # buka http://localhost:8501
```

Laporan lengkap ada di `output/Laporan_Konektivitas_Whoosh_Tegalluar.pdf` (dan `.docx`), dan semua tabel
ada di `output/whoosh_absa_hasil.xlsx`.

## Data yang dipublikasikan

Repo ini hanya memuat **hasil olahan** di `data/public/` (dibuat oleh `src/export_public.py`):

| Berkas | Isi |
|---|---|
| `ulasan.csv` | Metadata 1.191 ulasan: listing, bintang, tanggal relatif, bahasa, suka, foto. **Tanpa teks ulasan lengkap** |
| `label.csv` | Label per ulasan × aspek: aspek, sentimen, kutipan bukti, jenis masalah |
| `kutipan.csv` | Label per kutipan (span) |
| `listing.csv` | Lima listing Google Maps: tautan, koordinat, ID tempat, jumlah ulasan terkumpul |

- ID ulasan Google diganti **kode samaran** (`src/anon.py`), karena ID asli bisa dipakai untuk menemukan profil
  penulis ulasan. Nama, foto, dan profil pengulas tidak pernah disimpan.
- Data mentah, teks ulasan lengkap, dan berkas pelabelan (`data/raw`, `data/interim`, `data/labels`,
  `data/processed`) **tidak** dipublikasikan. Untuk menghasilkannya ulang, jalankan pipeline dari Tahap 1.
- Di komputer yang memiliki data lengkap, dashboard otomatis menampilkan "ulasan lengkap". Di versi publik,
  yang tampil hanya kutipannya.
- Teks ulasan berasal dari Google Maps. Repo ini untuk riset non-komersial; lihat bagian Keterbatasan & etika.

## Alur

| Tahap | Script | Output |
|---|---|---|
| 1. Scraping | `src/scrape.py` | `data/raw/<slug>.csv`, `data/raw/all_reviews.csv`, `data/raw/scrape_report.csv` |
| 2. Preprocessing | `src/preprocess.py` | `data/interim/` (bahasa, klausa) |
| 3. Filter kandidat | `src/filter.py` | `data/interim/candidates.csv`, `filtered_out_sample.csv` |
| 4. Baseline | `src/baseline.py` | `data/processed/baseline_labels.csv` |
| 5. Pelabelan | `src/label_prep.py`, `src/claude_label.py` (LLM) / Label Studio, `src/label_merge.py` | `data/labels/tasks_main.json`, `data/processed/final_labels.csv` |
| 6. Evaluasi | `src/evaluate.py` | `output/evaluation.md` |
| 7. Analisis | `src/analyze.py` | `output/figures/`, `output/analysis_report.md`, `output/summary.md` (naratif) |

Konfigurasi ada di `config/`:
- `taxonomy.yaml`: 10 kode aspek dan issue_tags
- `keywords.yaml`: keyword filter
- `guideline.md` dan `guideline_ringkas.md`: aturan pelabelan
- `events.csv`: event untuk garis di grafik tren

## Setup

Project memakai virtualenv lokal `.venv` agar tidak bentrok dengan paket Python global. Semua cache dan model
disimpan di dalam project (drive D:), yaitu `models/` untuk fastText dan HuggingFace.

```bash
python -m venv .venv
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
```

Jalankan semua script dengan `.venv/Scripts/python src/<script>.py`.

Label Studio dipasang di virtualenv **terpisah** (`.venv-ls`) agar dependensinya tidak bentrok:

```bash
python -m venv .venv-ls
.venv-ls/Scripts/pip install -r requirements-labelstudio.txt
annotation\start_labelstudio.bat     # Windows; buka http://localhost:8080
```

`start_labelstudio.bat` menyimpan database anotasi di `.labelstudio/`. **Folder itu jangan dihapus.**

## Tahap 1: scraping

```bash
python src/scrape.py --login      # opsional: login Google sekali (lihat catatan di bawah)
python src/scrape.py --limit 20   # uji coba link pertama -> data/raw/sample/
python src/scrape.py              # semua link (resumable: jalankan ulang bila terputus)
python src/scrape.py --merge-only # gabung ulang CSV per tempat + laporan kelengkapan
```

- Browser tampil secara default (`--headless` untuk menyembunyikan).
- Sesi browser disimpan di `.browser_profile/`. **Jangan dibagikan atau di-commit.**
- Tanpa login, Google Maps kadang menampilkan "tampilan terbatas" (hanya sekitar 5 review, tanpa pilihan
  urutan). Scraper mendeteksi kondisi ini, memberi peringatan, dan tidak menandai tempat sebagai selesai.
- Nama reviewer, foto, dan link profil tidak disimpan (privasi / UU PDP).
- `date_estimated` dihitung dari `date_relative` terhadap `scraped_at`, jadi nilainya perkiraan. Presisinya dicatat
  di `date_precision` (day/week/month/year).

## Tahap 2–4

```bash
.venv/Scripts/python src/preprocess.py             # bahasa + klausa (SaT di-cache; --resegment untuk ulang)
.venv/Scripts/python src/filter.py --explore       # distribusi skor + 20 contoh sekitar ambang
.venv/Scripts/python src/filter.py --threshold 0   # tulis kandidat (ambang margin yang disepakati)
.venv/Scripts/python src/baseline.py               # baseline pembanding (ambang aspek-embedding 0.10)
```

## Tahap 5: pelabelan manual di Label Studio

1. `.venv/Scripts/python src/label_prep.py` membuat `data/labels/tasks_main.json` berisi 673 task dalam
   urutan acak. Asal setiap task (kandidat / filter-out) hanya dicatat di `tasks_main_source.csv`.
2. Jalankan `annotation\start_labelstudio.bat`, buka http://localhost:8080, lalu buat akun lokal.
3. **Create Project**, beri nama misalnya "Whoosh ABSA - utama":
   - *Data Import*: unggah `data/labels/tasks_main.json`.
   - *Labeling Setup* → *Custom template* → *Code*: tempel isi `annotation/labelstudio_config.xml`.
   - *Settings* → *Annotation*: biarkan tanpa prediksi atau pre-annotation (blind labeling).
4. Labeli dengan berpegang pada `config/guideline_ringkas.md`. Label Studio menampilkan task sesuai urutan
   impor (sudah acak).
5. Export: *Export* → format **JSON** → simpan ke `data/labels/export/` (nama file bebas). Export boleh
   dilakukan bertahap; anotasi terbaru per review yang dipakai.
6. `.venv/Scripts/python src/label_merge.py` menghasilkan `data/processed/final_labels.csv`, laporan validasi
   `data/labels/validation_report.md`, dan daftar label ragu `data/labels/review_ragu.csv`.

Setelah pelabelan utama selesai:
- `src/label_prep.py --consistency` membuat 10% task untuk dilabel ulang **beberapa hari kemudian**. Buat
  project baru, lalu export ke `data/labels/export/consistency/`.
- `src/label_prep.py --annotator2` (opsional) membuat 150 task untuk anotator kedua. Export ke
  `data/labels/export/annotator2/`.

### Varian yang dipakai: pelabelan oleh Claude (LLM)

Atas keputusan peneliti (2026-09-26), label utama dibuat oleh Claude, bukan manual:

```bash
.venv/Scripts/python src/claude_label.py prep            # batch pass1 & pass2 (urutan acak berbeda, tanpa rating)
# Claude menulis data/labels/claude/pass{1,2}/batch_XX.out.jsonl
.venv/Scripts/python src/claude_label.py check --pass 1  # validasi skema + evidence substring persis
.venv/Scripts/python src/claude_label.py compare         # kappa pass1 vs pass2 + daftar adjudikasi
# Claude menulis data/labels/claude/adjudicated.jsonl (alasan per item)
.venv/Scripts/python src/claude_label.py finalize        # + retag.jsonl -> data/labels/export/claude_labels.json
.venv/Scripts/python src/label_merge.py
```

**Tidak ada gold manusia.** File di `data/labels/export/llm2/` juga dibuat LLM dan hanya dipakai sebagai
pembanding. Semua hasil harus dibaca sebagai "menurut label LLM".

## Tahap 6–7

```bash
.venv/Scripts/python src/evaluate.py   # output/evaluation.md
.venv/Scripts/python src/analyze.py            # output/analysis_report.md + output/figures/01-04
.venv/Scripts/python src/analyze_extended.py   # E1–E15: output/analysis_extended.md, output/tables/*.csv,
                                               # output/whoosh_absa_hasil.xlsx (satu sheet per tabel), figures/05-08
```

Dokumen naratif di `output/`:
- `summary.md`: ringkasan temuan
- `laporan_wawasan.md`: sintesis kualitatif per tema, peta perjalanan, dan matriks rekomendasi
- `linimasa_kebijakan.md`: 16 peristiwa bersumber (KCIC dan media) yang disilangkan dengan temuan review
  (data mentah di `config/events.csv`)
- `metodologi.md`: bab metode siap adaptasi (desain, data, pelabelan, evaluasi, ancaman validitas,
  pernyataan penggunaan AI, reproduksibilitas)

## Dashboard (Streamlit)

```bash
app\jalankan_dashboard.bat                          # Windows: klik dua kali, lalu buka http://localhost:8501
.venv/Scripts/streamlit run app/streamlit_app.py    # atau langsung dari terminal
```

Halaman: Ringkasan, Aspek & Sentimen, Fenomena Terkini, Detail Tema, Pemicu Ketidakpuasan, Katalog Kutipan,
Konteks Kebijakan, Data & Metode, dan Unduhan. Filter di sidebar (periode, listing, bahasa) berlaku di semua
halaman, dan angkanya dihitung ulang dari `data/processed/final_labels.csv` memakai fungsi yang sama dengan
`src/analyze.py`. Server hanya bisa diakses dari komputer sendiri (`localhost`, lihat `.streamlit/config.toml`).
Berkas: `app/data.py` (data dan statistik), `app/charts.py` (grafik Plotly), `app/streamlit_app.py` (halaman).
Dashboard membaca `data/public/`; setelah label diperbarui, jalankan `src/export_public.py` lalu restart dashboard.

## Pengambilan ulang data (opsional, CLI)

`src/scrape.py --update` mengambil ulasan baru saja (urutan Terbaru, berhenti setelah 20 ulasan lama berturut-turut)
dan mencatat `first_seen`/`seen_after` serta log per run di `data/raw/runs/`. Google kini mewajibkan login
(`src/scrape.py --login`). Fitur ini belum dihubungkan ke dashboard.

## Keterbatasan & etika

- Scraping Google Maps dapat melanggar ToS Google. Project ini hanya untuk riset non-komersial, dengan jeda
  acak 1–3 detik.
- Reviewer Google tidak mewakili seluruh pengguna stasiun.
- Tanggal review bersifat perkiraan: 74% review relevan hanya bertanggal "setahun lalu" atau "2 tahun lalu",
  sehingga tren dibuat per tiga periode relatif, bukan per bulan/kuartal.
- Label dibuat LLM tanpa validasi manusia (lihat `output/evaluation.md`).
