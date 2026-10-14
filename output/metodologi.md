# Metodologi Penelitian

*Analisis sentimen berbasis aspek (ABSA) terhadap review Google Maps mengenai konektivitas transportasi
menuju dan dari Stasiun Kereta Cepat Whoosh Tegalluar (Tegalluar Summarecon), Kabupaten Bandung.*

Dokumen ini dapat diadaptasi langsung menjadi bab metode. Seluruh angka merujuk pada eksekusi tanggal
25–26 September 2026. Kode dan konfigurasi tersedia di repositori `whoosh-absa/`.

---

## 1. Desain penelitian

Penelitian ini memakai desain **deskriptif-eksploratif dengan metode campuran**:

1. **Kuantitatif:** distribusi sentimen per aspek, uji selisih proporsi dengan interval kepercayaan, dan
   regresi rating.
2. **Kualitatif:** sintesis tematik atas kutipan review, dilengkapi pemodelan topik untuk menemukan tema
   di luar taksonomi.
3. **Triangulasi dokumen:** persilangan temuan dengan linimasa kebijakan dari siaran pers dan media.

Unit analisis utama adalah **pasangan review × aspek**. Unit pendukungnya adalah span (kutipan) dan
review.

Seluruh pipeline memakai **perangkat lunak open-source yang dijalankan lokal di CPU**, tanpa API atau
layanan berbayar untuk pengolahan data. Pelabelan dilakukan oleh model bahasa besar (lihat §5 dan §10).

Alur penelitian:
`scraping → praproses → filter kandidat → baseline → pelabelan → evaluasi → analisis → triangulasi`

---

## 2. Data

### 2.1 Sumber dan cakupan
Data diambil dari review publik Google Maps untuk lima *listing* yang merujuk pada lokasi stasiun:

| # | Nama listing | Review | Total menurut Google |
|---|---|---|---|
| 1 | Stasiun Kereta Cepat Tegalluar | 416 | 416 |
| 2 | Kereta Cepat Whoosh Tegalluar | 663 | 663 |
| 3 | Stasiun KCJB Tegalluar | 17 | 17 |
| 4 | Tegalluar Summarecon | 72 | 72 |
| 5 | Parkir Timur Stasiun Kereta Cepat Tegalluar | 23 | 23 |
| | **Total** | **1.191** | |

Kelima listing memiliki *feature id* Google yang berbeda, tetapi berada dalam radius sekitar 200 m.
Kelengkapan pengambilan data adalah 100% dari angka yang ditampilkan Google untuk setiap listing.

### 2.2 Prosedur pengambilan
- **Alat:** Playwright 1.63 + Chromium, dengan profil browser persisten dan mode tampil (non-headless).
  Tanpa login, Google kadang menampilkan "tampilan terbatas" berisi sekitar 5 review. Kondisi ini dideteksi
  otomatis, dan listing tidak dianggap selesai bila terjadi.
- **Langkah:**
  1. Resolusi *short link* ke URL final.
  2. Pencatatan nama tempat dan koordinat.
  3. Parameter `hl=id`, tab *Ulasan* diurutkan "Terbaru", lalu *scroll* sampai tidak ada review baru
     setelah 3 kali berturut-turut.
  4. Ekspansi teks ("Lainnya").
  5. Bila Google menampilkan terjemahan, teks terjemahan disimpan terlebih dahulu, lalu tombol "Lihat
     versi asli" diklik untuk menyimpan teks asli.
  6. Jeda acak 1–3 detik antar-aksi, dengan penyimpanan bertahap sehingga proses bisa dilanjutkan bila
     terputus (*resumable*).
- **Variabel yang disimpan:** nama dan URL tempat, `review_id`, rating, tanggal relatif, tanggal
  perkiraan beserta presisinya (hari/minggu/bulan/tahun), teks asli, teks terjemahan, likes, balasan
  pemilik, keberadaan foto, dan waktu scraping.
- **Deduplikasi:** berdasarkan `review_id` (0 duplikat). Near-duplicate lintas listing (teks, rating, dan
  tanggal sama, dengan panjang teks ≥ 20 karakter) juga dicek: 0 kasus. Teks generik pendek seperti
  "Bagus" dikecualikan karena kesamaannya kebetulan.

### 2.3 Etika dan privasi
- Nama reviewer, foto profil, dan tautan profil **tidak disimpan**, sesuai UU No. 27/2022 tentang
  Pelindungan Data Pribadi.
- Kutipan dalam laporan diparafrasekan tanpa identitas.
- Scraping dilakukan untuk riset non-komersial dengan beban permintaan rendah. Scraping Google Maps
  berpotensi melanggar Ketentuan Layanan Google, dan hal ini dinyatakan sebagai keterbatasan.

### 2.4 Karakteristik data
- **Review bertekstual:** 673. Sebanyak 518 lainnya hanya berisi rating dan dipakai untuk statistik
  rating saja.
- **Balasan pengelola:** 0 dari 1.191 review.
- **Tanggal:** Google hanya menyediakan tanggal relatif. **74% review relevan** hanya bertanggal
  "setahun lalu" atau "2 tahun lalu" (presisi tahunan).

---

## 3. Praproses

### 3.1 Deteksi bahasa
Deteksi bahasa memakai **ansambel fastText lid.176 dan lingua-py 2.1**:
- Jika kedua detektor sepakat, hasilnya dipakai.
- Jika tidak sepakat, dipilih yang *confidence*-nya lebih tinggi, dan review diberi flag `lang_uncertain`.
- "Melayu" pada teks pendek (≤ 10 kata) dipetakan menjadi Indonesia.

Aturan tambahan diperlukan karena teks slang pendek sering salah dideteksi oleh kedua model (misalnya
"Mantap" terdeteksi sebagai Turki dan "Keren" sebagai Belanda):
1. Teks tanpa huruf diberi label `und`.
2. Teks ≤ 3 kata, atau yang *confidence* kedua detektornya < 0,5, ditentukan dengan leksikon
   Indonesia/slang (setelah huruf berulang dikompres), lalu dengan petunjuk bahasa dari Google bila
   petunjuk itu termasuk kandidat top-3 salah satu detektor.
3. Prediksi "Melayu" diubah menjadi Indonesia bila fastText memprediksi Indonesia atau terdapat penanda
   Indonesia informal (ga, banget, udah, dan sejenisnya).
4. **Heuristik Sunda:** ≥ 2 penanda berbeda (*mah, teh, pisan, euy, atuh, teu, henteu, tebih, abdi, anjeun,
   ieu, eta, kumaha, sae*) dianggap Sunda; 1 penanda diberi flag `code_mixed`.
5. `code_mixed` juga diberikan bila ada campuran leksikon Indonesia–Inggris, campuran aksara Latin dengan
   CJK/Arab, atau probabilitas bahasa kedua ≥ 0,20 pada teks ≥ 5 kata.

**Hasil:** Indonesia 587, Inggris 73, Jepang 5, `und` 3, Arab 2, Jerman 1, Sunda 1, Mandarin 1.
`lang_uncertain` = 203 (sebagian besar teks 1–3 kata); `code_mixed` = 56.

### 3.2 Segmentasi klausa
Segmentasi kalimat memakai **wtpsplit SaT `sat-12l-sm`**. Setiap kalimat lalu dipecah lagi sebelum kata
kontras: *tapi, tetapi, namun, cuma, hanya saja, sayangnya, padahal, walaupun, but, however, although, 但是,
可是, でも, しかし, 하지만, لكن*. Hasilnya **1.736 klausa**, masing-masing dengan offset karakter pada teks
asli.

### 3.3 Normalisasi
Normalisasi ringan dilakukan **hanya untuk pencocokan kata kunci**: NFKC, huruf kecil, dan kompresi huruf
berulang (≥ 3 menjadi 1). Teks asli tidak diubah.

---

## 4. Filter kandidat (orientasi recall)

Sebuah review menjadi kandidat bila memenuhi **salah satu** kriteria berikut:
- **(a) Kata kunci.** Kata kunci aspek dari `config/keywords.yaml` versi v2 (±320 istilah multibahasa)
  cocok di teks asli atau terjemahan. Istilah Latin pendek (≤ 4 karakter) dan istilah ambigu dicocokkan
  sebagai kata utuh, dan kata "jam" sendirian tidak dipakai.
- **(b) Embedding.** Skor embedding **BAAI/bge-m3** per klausa (atau per teks terjemahan), diambil
  nilai maksimumnya, mencapai ambang.
- **(c) Kata akses tidak langsung:** *pulang, pergi, ke kota, dari kota, nyambung, lanjut, transportasi,
  kendaraan, naik apa, dijemput, ngejemput*.

**Skor margin.** Eksplorasi awal menunjukkan similaritas kosinus mentah bge-m3 hampir seragam (±0,6)
untuk semua review stasiun, sehingga tidak membedakan review konektivitas dari pujian umum. Karena itu
dipakai **skor margin**:

`margin = maks sim(klausa, prototipe aspek) − maks sim(klausa, prototipe non-konektivitas)`

- **Prototipe aspek:** deskripsi taksonomi ditambah contoh karangan dari guideline.
- **Prototipe non-konektivitas:** 7 deskripsi, yaitu fasilitas, kebersihan, layanan kereta, petugas,
  tiket, makanan, dan pujian umum.
- **Hasil:** rata-rata margin 0,156 untuk review ber-kata kunci dan 0,021 untuk yang tanpa kata kunci.
- **Ambang:** margin ≥ 0, dipilih peneliti setelah menelaah distribusi skor dan 20 contoh di sekitar
  ambang.

Kata kunci v2 ditambahkan dari review relevan yang terlewat saat eksplorasi, misalnya "pintu tol",
"dijangkau", "gede bage", dan "peradaban".

**Hasil filter:** 531 kandidat dan 142 tidak lolos. Karena yang tidak lolos kurang dari 200, **seluruh
142 dilabeli** untuk mengukur recall.

---

## 5. Skema anotasi dan prosedur pelabelan

### 5.1 Skema
- **Relevansi:** apakah review memuat opini atau pernyataan tentang akses/transportasi **menuju atau
  dari** stasiun. Kereta, fasilitas dalam stasiun, petugas, tiket kereta, dan makanan dikecualikan.
- **Aspek (10 kode):** `FEEDER_BUS, PADALARANG, OJOL, TAKSI, ANGKOT_OJEK_PANGKALAN, PARKIR,
  AKSES_JALAN_MACET, JARAK_LOKASI, INTEGRASI_JADWAL, KONEKTIVITAS_UMUM`.
- **Sentimen per span:** *positive, negative, neutral* (fakta tanpa penilaian), dan *mixed* (satu aspek
  dinilai baik sekaligus buruk). Sarkasme dinilai sesuai maksud, saran perbaikan dianggap negatif, dan
  pertanyaan dianggap netral.
- **Evidence:** span sesingkat mungkin yang tetap bermakna, dan harus berupa **substring persis** teks
  asli.
- **Issue tags:** 22 tag tetap. Tiga di antaranya ditambahkan pada v1.1 atas persetujuan peneliti:
  `konflik_opang`, `kapasitas_kurang`, dan `tidak_terintegrasi`.
- **Penanda ragu dan catatan.**

Aturan lengkap ada di `config/guideline.md` (v1.1), termasuk konvensi R1–R7 hasil adjudikasi, dan versi
ringkasnya di `config/guideline_ringkas.md`.

### 5.2 Prosedur pelabelan
Rencana awal adalah pelabelan manual oleh peneliti di Label Studio 1.23 (konfigurasi di
`annotation/labelstudio_config.xml`). Atas keputusan peneliti, **pelabelan utama dialihkan ke model
bahasa besar** (Claude Opus 5.5, Anthropic, dijalankan melalui Claude Code) dengan prosedur berikut:

1. **Blind input.** Pelabel hanya menerima ID acak, bahasa, teks asli, dan terjemahan. Rating, asal
   filter, dan prediksi baseline **tidak diberikan**.
2. **Dua pass independen.** Pass 1 dan pass 2 masing-masing dikerjakan oleh 3 instans pelabel terpisah
   (konteks terisolasi, 5 batch × 45 review per instans), dengan urutan acak yang berbeda (seed 111 dan
   222). Instans pass 2 dilarang membaca keluaran pass 1.
3. **Validasi otomatis.** Skema, kode aspek, sentimen, dan tag harus valid; evidence harus substring
   persis; tag `lainnya` wajib disertai catatan; setiap review harus dilabel tepat satu kali.
4. **Adjudikasi.** 35 review yang tidak sepakat antar-pass diadjudikasi dengan alasan tertulis per item
   (`data/labels/claude/adjudicated.jsonl`). Review yang sepakat memakai label pass 1.
5. **Retag.** Setelah tiga tag baru disetujui, 51 span dipetakan ulang ke tag baru berdasarkan catatan
   pelabel. Pemetaan ini dicatat terpisah di `retag.jsonl` beserta tag lamanya, sehingga dapat diaudit.

**Hasil:** 673 review berlabel. **234 relevan** (34,8%), dengan 392 pasangan review × aspek, 447 span,
dan 40 span bertanda ragu.

---

## 6. Evaluasi

### 6.1 Konsistensi pelabel (pass 1 vs pass 2, sebelum adjudikasi)
- Kappa Cohen relevansi: **0,987**
- Kappa aspek (ada/tidak): **0,900–1,000** per kode
- Kappa sentimen pada aspek yang sama: **0,942** (373 pasangan)

Karena kedua pass dikerjakan oleh model yang sama, angka ini adalah **reliabilitas intra-model**. Angka
ini tidak dapat disamakan dengan kesepakatan antar-anotator manusia dan bukan ukuran akurasi.

### 6.2 Validasi terhadap manusia: tidak tersedia
Sampel gold stratifikasi sebanyak 122 review disiapkan (`data/labels/tasks_gold.json`, dengan bobot strata
di `gold_source.csv`). **Berkas yang diserahkan sebagai gold ternyata bukan hasil anotasi manusia.**
Indikasinya:
- `lead_time` 0 detik untuk semua anotasi;
- ID anotasi berpola program (`rel0`, `t0r0`);
- 88/122 review identik dengan label utama.

Berkas itu diperlakukan sebagai "pelabel LLM kedua" (kappa relevansi 1,000; kappa sentimen 0,853), dan
**tidak digunakan sebagai validasi**. Peneliti memutuskan melanjutkan tanpa gold manusia. Akibatnya,
**akurasi label tidak terukur secara independen**. Hal ini harus dinyatakan sebagai keterbatasan utama.

### 6.3 Recall filter
Dari 142 review yang tidak lolos filter, **0 relevan** menurut label akhir. Recall filter dengan demikian
100% dan presisinya 44,1%, keduanya terhadap label LLM.

### 6.4 Baseline open-source
Baseline dipakai sebagai pembanding, bukan hasil akhir.
- **Aspek:** kata kunci per klausa, ditambah embedding (aspek terdekat bila margin ≥ 0,10). Ambang 0,10
  ditetapkan **sebelum** label tersedia, kira-kira median margin klausa yang mengandung kata kunci.
- **Sentimen:** `w11wo/indonesian-roberta-base-sentiment-classifier` untuk klausa berbahasa Indonesia,
  dan `cardiffnlp/twitter-xlm-roberta-base-sentiment` untuk bahasa lain.
- **Agregasi per review × aspek:** jika ada positif dan negatif → mixed; jika hanya positif → positive;
  jika hanya negatif → negative; selain itu → neutral.

Hasil terhadap label LLM:

| Metrik | Nilai |
|---|---|
| F1 relevansi | 0,804 |
| F1 aspek micro / macro | 0,606 / 0,590 |
| Macro-F1 sentimen | 0,432 |
| Pair-F1 (aspek + sentimen persis) | 0,339 |

Kesalahan terbesar baseline: 51 dari 196 sentimen negatif diprediksi positif. Analisis sensitivitas ambang
(0; 0,05; 0,10; 0,15) dilaporkan di `output/evaluation.md`.

---

## 7. Analisis

- **Distribusi sentimen per aspek dan net sentiment** (%positif − %negatif). Interval kepercayaan 95%
  memakai **Wilson** untuk proporsi dan **MOVER/Newcombe** untuk selisih, dipotong ke [−100, 100].
  Kovarians multinomial diabaikan, sehingga interval sedikit konservatif.
- **Tren.** Karena presisi tanggal kasar, dipakai tiga periode relatif dari tanggal scraping:
  - ±2 tahun lalu, ≈ Okt 2023 – awal 2025;
  - ±setahun lalu, ≈ 2025;
  - ≤ 11 bulan terakhir.

  Sel dengan n < 10 disembunyikan.
- **Regresi OLS:** rating ~ dummy(aspek × sentimen), untuk dummy dengan ≥ 5 review, n = 673 review
  bertekstual, dengan SE robust **HC3**. R² = 0,224. Hasilnya bersifat asosiatif.
- **Pemodelan topik:** **BERTopic 0.17** dengan embedding
  `paraphrase-multilingual-mpnet-base-v2`; UMAP (n_neighbors = 10, n_components = 5, min_dist = 0,
  seed 42); HDBSCAN (min_cluster_size = 6, min_samples = 3); CountVectorizer (1–2 gram, min_df = 2,
  daftar stopword). Korpusnya 276 evidence unik (KONEKTIVITAS_UMUM ditambah semua evidence negatif), dan
  menghasilkan 14 topik.
- **Analisis turunan (E1–E15, `analyze_extended.py`):**
  - jumlah absolut sentimen per tingkat analisis;
  - Pareto keluhan;
  - matriks aspek × issue tag;
  - matriks prioritas (volume × net sentiment × dampak rating univariat);
  - kookurensi aspek;
  - rating per aspek × sentimen, dan komposisi review bintang 1–2;
  - segmen listing dan bahasa;
  - pergeseran topik per periode;
  - moda yang dibahas;
  - deteksi permintaan perbaikan (berbasis kata kunci; perkiraan);
  - kata/frasa keluhan;
  - foto dan likes (net sentiment berbobot likes + 1);
  - balasan pengelola;
  - katalog kutipan.
- **Sintesis kualitatif** (`output/laporan_wawasan.md`): seluruh 447 kutipan dibaca dan dikelompokkan
  per tema, dengan fokus pada masalah spesifik, pujian, perubahan waktu, rekomendasi, dan tingkat
  keyakinan.

## 8. Triangulasi dengan linimasa kebijakan

Sebanyak 16 peristiwa bertanggal (Sep 2023 – Apr 2026) dihimpun dari siaran pers KCIC dan media
nasional (`config/events.csv`, `output/linimasa_kebijakan.md`). Topiknya adalah akses tol, tarif dan
kapasitas parkir, rute dan tarif DAMRI, KA Feeder Padalarang, area pick-up transportasi online, insiden
opang, dan penggantian nama stasiun.

Peristiwa disilangkan dengan periode review sebagai **kecocokan temporal**, bukan bukti kausal.
Triangulasi ini mengoreksi satu tafsiran. Parkir "gratis" yang dipuji pengulas kemungkinan hanya berlaku
selama masa uji coba, karena parkir sudah berbayar dengan tarif maksimal sejak paling lambat Januari 2024.

---

## 9. Ancaman validitas dan keterbatasan

| Aspek validitas | Ancaman | Mitigasi / status |
|---|---|---|
| Validitas konstruk | Label dibuat LLM tanpa validasi manusia | Dua pass independen, validasi otomatis, adjudikasi tertulis. **Belum ada** gold manusia (lihat §6.2) |
| Reliabilitas | Kappa intra-model tinggi tetapi tidak setara antar-manusia | Dilaporkan terbuka; disarankan validasi manusia 100–120 review oleh 2 anotator |
| Validitas eksternal | Pengulas Google tidak mewakili seluruh penumpang (bias kelas menengah, digital, dan pengalaman ekstrem) | Dinyatakan sebagai keterbatasan; triangulasi dokumen |
| Validitas temporal | Tanggal relatif, 74% berpresisi tahunan | Analisis per 3 periode kasar; saran scraping berkala |
| Validitas statistik | n per aspek kecil (2–73) | CI dilaporkan; sel n < 10 disembunyikan |
| Validitas inferensial | Regresi OLS bersifat asosiatif; keluhan ojol dan opang berkolinearitas | Tidak ada klaim kausal |
| Cakupan | Satu platform, satu stasiun, tanpa pembanding | Disarankan perbandingan dengan Halim, Padalarang, dan Karawang |
| Kepatuhan | Potensi pelanggaran ToS Google | Non-komersial, beban rendah, data pribadi tidak disimpan |

## 10. Pernyataan penggunaan AI

Model bahasa besar (Claude, Anthropic) digunakan untuk:
- membangun kode pipeline;
- **melabeli seluruh data** (aspek, sentimen, evidence, issue tags);
- adjudikasi;
- sintesis kualitatif;
- penelusuran linimasa kebijakan.

Keputusan metodologis diambil oleh peneliti, antara lain metode skor filter, ambang, tag baru, dan
keputusan melanjutkan tanpa gold manusia. Sebuah berkas yang semula direncanakan sebagai gold manusia
teridentifikasi sebagai keluaran LLM dan tidak dipakai untuk validasi. Pernyataan ini perlu dicantumkan
sesuai kebijakan integritas akademik institusi atau jurnal.

## 11. Reproduksibilitas

**Lingkungan:** Python 3.11.0, dengan virtualenv `.venv`:

| Paket | Versi |
|---|---|
| torch | 2.14.0+cpu |
| transformers | 5.17.0 |
| sentence-transformers | 6.1.0 |
| wtpsplit | 2.2.2 |
| lingua-language-detector | 2.1.1 |
| fasttext-wheel | 0.9.2 (model `lid.176.bin`) |
| bertopic | 0.17.4 |
| umap-learn | 0.5.12 |
| hdbscan | 0.8.44 |
| statsmodels | 0.15.0 |
| scikit-learn | 1.9.1 |
| pandas | 3.0.6 |
| matplotlib | 3.11.2 |
| playwright | 1.63.0 |

Label Studio 1.23.1 dipasang di virtualenv terpisah (`.venv-ls`).

**Perintah (dari root project):**
```
.venv/Scripts/python src/scrape.py
.venv/Scripts/python src/preprocess.py
.venv/Scripts/python src/filter.py --explore
.venv/Scripts/python src/filter.py --threshold 0
.venv/Scripts/python src/baseline.py
.venv/Scripts/python src/label_prep.py
.venv/Scripts/python src/claude_label.py prep|check|compare|finalize
.venv/Scripts/python src/label_merge.py
.venv/Scripts/python src/evaluate.py
.venv/Scripts/python src/analyze.py
.venv/Scripts/python src/analyze_extended.py
```

**Seed:**

| Kegunaan | Seed |
|---|---|
| Urutan task | 20260926 |
| Batch pelabelan pass 1 / pass 2 | 111 / 222 |
| UMAP | 42 |
| Sampel filter-out | 42 |

Hasil scraping **tidak dapat direproduksi persis**, karena review Google berubah dari waktu ke waktu.
Data mentah hasil scraping 25 September 2026 disimpan di `data/raw/`.
