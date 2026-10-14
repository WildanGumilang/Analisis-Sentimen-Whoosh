# Ringkasan: Opini Konektivitas Transportasi Stasiun Whoosh Tegalluar

*Analisis aspek-sentimen (ABSA) atas review Google Maps. Data di-scrape 25 September 2026.*

> **Catatan metodologi terpenting.** Label aspek dan sentimen dibuat oleh model bahasa (Claude) melalui
> dua putaran pelabelan independen dan adjudikasi, **tanpa validasi oleh anotator manusia**. Angka-angka
> di bawah menggambarkan pola dalam label tersebut. Lihat bagian *Keterbatasan*.

## Temuan utama

1. **Konektivitas menjadi sumber keluhan yang nyata.** Dari 673 review bertekstual, **234 (35%)**
   membahas akses atau transportasi menuju/dari stasiun. Rating rata-rata review konektivitas adalah
   **3,9 bintang**, dibanding 4,6 untuk review lain dan 4,8 untuk review tanpa teks. Pengunjung umumnya
   puas dengan stasiun dan keretanya, tetapi tidak dengan perjalanan ke dan dari stasiun.

2. **Konflik ojek pangkalan dengan ojek online adalah keluhan paling tajam.** Aspek angkot/ojek
   pangkalan hampir seluruhnya negatif (**96% negatif**, n=24), dan ojol 66% negatif (n=44). Isinya
   konsisten: pengemudi ojol dilarang menjemput atau diintimidasi oleh ojek pangkalan, sehingga
   penumpang terpaksa memakai opang atau berjalan keluar area stasiun. Beberapa review menyebut ada
   pungutan uang. Keluhan ini paling banyak disetujui pembaca: 7 dari 8 review negatif dengan likes
   terbanyak (sampai 17 likes) membahas larangan ojol atau perilaku opang. Kehadirannya juga berasosiasi dengan penurunan
   rating terbesar, yaitu **−1,7 bintang** (OLS, CI 95%: −2,6 s/d −0,8).
   - *Catatan waktu:* semua keluhan opang dan hampir semua keluhan ojol berasal dari periode
     **±2 tahun lalu** (masa awal operasi, ≈ akhir 2023 – awal 2025). Pada periode setelahnya tidak ada lagi
     review yang menyebut opang. Ini *mengisyaratkan* masalah sudah mereda, tetapi bisa juga karena
     review terbaru memang lebih sedikit. Perlu dikonfirmasi di lapangan.

3. **Akses jalan dan kemacetan: negatif dan stabil.** Aspek akses jalan & macet **75% negatif**
   (n=61, net −62). Keluhannya meliputi jalan masuk yang sempit dan melewati permukiman atau sawah, akses
   tol yang belum tersedia atau tidak bisa dipakai, kemacetan di sekitar Gedebage/Cibiru, dan rute yang
   membingungkan sehingga pengunjung tersesat. Persentase negatifnya sama (±74%) pada periode awal dan
   periode terbaru. Keluhan jalan berasosiasi dengan rating −0,9 bintang.

4. **Transportasi umum lanjutan dianggap minim.** Konektivitas umum **78% negatif** (n=49). Keluhan
   yang dominan adalah kurangnya angkutan umum selain bus DAMRI dan taksi, disertai permintaan agar
   tersedia feeder seperti di Padalarang. Sebaliknya, **feeder/bus** (DAMRI, shuttle) cenderung netral
   hingga positif (net +15, n=40). Yang disebut positif: ongkos DAMRI murah (sekitar Rp15 ribu ke pusat kota)
   dan tersedianya shuttle ke Summarecon. Artinya, layanan feeder yang ada dinilai baik, tetapi jumlah dan
   ragamnya dirasa kurang.

5. **Parkir & antar-jemput terbelah.** Sentimennya 51% negatif dan 31% positif (n=65). Pujian datang
   untuk parkir yang luas dan murah atau gratis. Keluhan datang soal parkir tanpa atap yang panas, kapasitas
   kurang saat ramai, tarif, gate yang bermasalah, dan zona drop-off tanpa jalur keluar khusus sehingga
   pengantar tetap harus membayar parkir. Tren negatifnya naik dari 44% (±2 tahun lalu) menjadi 67% (≤ 11
   bulan terakhir), tetapi interval kepercayaannya masih tumpang tindih. Keluhan parkir berasosiasi dengan
   rating −1,3 bintang.

6. **Lokasi jauh dikeluhkan, tetapi tidak menurunkan rating.** Jarak & lokasi 49% negatif (n=73).
   Stasiun dinilai jauh dari pusat kota, dan perjalanan kereta yang singkat tertutup waktu tempuh ke kota.
   Meski begitu, keluhan lokasi **tidak berasosiasi dengan rating lebih rendah** (koefisien +0,2, tidak
   signifikan). Pengulas tampaknya menerima lokasi sebagai kompromi. Porsi negatifnya juga cenderung turun
   (57% → 38%), sejalan dengan berkembangnya kawasan di sekitar stasiun.

7. **Padalarang sebagai pembanding.** Saat Padalarang disebut, nadanya **positif** (net +44, n=18),
   terutama karena KA feeder yang langsung ke Stasiun Bandung dan gratis. Sebagian pengulas menyarankan
   turun di Padalarang saja bila tujuannya pusat kota Bandung.

## Angka ringkas per aspek

| Aspek | n | % negatif | Net sentiment (CI 95%) |
|---|---|---|---|
| Angkot / ojek pangkalan | 24 | 96% | −96 (−99 s/d −75) |
| Akses jalan & macet | 61 | 75% | −62 (−73 s/d −46) |
| Konektivitas umum | 49 | 78% | −59 (−72 s/d −41) |
| Ojol | 44 | 66% | −50 (−65 s/d −30) |
| Jarak & lokasi | 73 | 49% | −22 (−36 s/d −6) |
| Parkir & antar-jemput | 65 | 51% | −20 (−35 s/d −3) |
| Taksi | 16 | 13% | +6 (−20 s/d +32) |
| Feeder / bus | 40 | 13% | +15 (−3 s/d +32) |
| Padalarang (KA feeder) | 18 | 22% | +44 (+12 s/d +66) |
| Integrasi jadwal | 2 | – | terlalu sedikit untuk disimpulkan |

Grafik: `figures/01_sentimen_per_aspek.png`, `02_net_sentiment.png`, `03_tren_negatif.png`,
`04_ols_rating.png`. Angka lengkap: `analysis_report.md`. Evaluasi label: `evaluation.md`.

## Implikasi (untuk dipertimbangkan pengelola)

- **Tertibkan dan pastikan zona penjemputan ojol resmi.** Ini keluhan dengan dampak rating terbesar dan
  paling banyak disetujui pembaca. Data terbaru mengisyaratkan perbaikan, tetapi perlu dikonfirmasi.
- **Perbaiki akses jalan dan penunjuk rute.** Keluhannya tidak berkurang dari waktu ke waktu.
- **Tambah ragam dan frekuensi angkutan lanjutan.** Layanan yang sudah ada (DAMRI, shuttle) dinilai baik,
  tetapi dirasa kurang.
- **Parkir:** tambah peneduh dan kapasitas, serta tata ulang alur drop-off agar pengantar tidak dikenai
  biaya parkir.

## Keterbatasan

1. **Label dibuat LLM tanpa validasi manusia.** Kesepakatan antar-putaran pelabelan sangat tinggi
   (kappa relevansi 0,99; sentimen 0,94), tetapi kedua putaran berasal dari model yang sama, sehingga angka
   itu tidak membuktikan akurasi. File yang semula direncanakan sebagai gold ternyata juga dibuat LLM
   (identik 88/122 dengan label utama), sehingga tidak dipakai sebagai validasi. Sebagai pembanding,
   baseline open-source hanya mencapai F1 aspek 0,61 dan macro-F1 sentimen 0,43 terhadap label ini.
2. **Tanggal hanya perkiraan.** Google hanya menampilkan tanggal relatif, dan 74% review relevan bertanggal
   "setahun lalu" atau "2 tahun lalu". Tren karena itu hanya dibuat dalam tiga periode kasar, dan banyak sel
   periode memiliki n < 10.
3. **Bias pengulas Google.** Pengulas bukan sampel acak pengguna stasiun. Pengalaman ekstrem (sangat puas
   atau sangat kecewa) cenderung lebih sering ditulis. Hanya 35% review bertekstual yang membahas
   konektivitas, sehingga sebagian besar aspek memiliki n < 75.
4. **Cakupan scraping.** Terkumpul 1.191 review dari 5 listing di Google Maps. Jumlah ini sama dengan angka
   yang ditampilkan Google untuk setiap listing (100%), tetapi hanya 673 yang bertekstual. Kelima listing
   berada dalam radius ~200 m (tempat fisik yang sama), dan tidak ditemukan review duplikat antar-listing.
5. **Regresi rating bersifat asosiatif.** Model OLS (R² = 0,22) tidak menunjukkan sebab-akibat. Keluhan
   ojol dan opang sering muncul bersama sehingga efek masing-masing sulit dipisahkan.
6. **Multibahasa.** 87% review berbahasa Indonesia dan 11% Inggris. Bahasa lain (Jepang, Arab, Mandarin,
   Sunda) terlalu sedikit untuk dibandingkan.
