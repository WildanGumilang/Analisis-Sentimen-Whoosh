# Guideline Pelabelan ABSA — Konektivitas Transportasi Stasiun Whoosh Tegalluar

Pelabel: pemilik project (manual, di Label Studio). Semua contoh di dokumen ini
**karangan**, bukan kutipan dari data asli.

---

## 1. Langkah per review

1. Baca `text_original`. Pakai `text_translated` hanya sebagai bantuan memahami.
2. Jawab **"Relevan konektivitas?"**:
   - **ya** jika ada minimal satu opini atau pernyataan tentang akses/transportasi
     MENUJU atau DARI stasiun.
   - **tidak** jika sebaliknya. Jangan buat span.
3. Jika **ya**: blok (span) evidence untuk tiap aspek, beri kode aspek, lalu isi untuk tiap span:
   sentimen, issue_tags, ragu (jika tidak yakin), dan catatan (opsional).

## 2. Aturan pelabelan

1. **Hanya opini tentang akses/transportasi menuju atau dari stasiun.** Abaikan kereta,
   kebersihan, toilet, petugas, tiket kereta, makanan, dan fasilitas di dalam stasiun.
2. **Satu review boleh punya beberapa aspek**, masing-masing dengan sentimennya sendiri.
   Aspek yang sama boleh punya lebih dari satu span jika opininya terpisah.
3. **Sentimen:** `positive` / `negative` / `neutral` / `mixed`.
   - Fakta tanpa penilaian → `neutral` ("Ada shuttle ke Pasteur").
   - `mixed` hanya bila SATU aspek dinilai baik sekaligus buruk dalam satu span
     ("parkirnya luas tapi mahal").
4. **Sarkasme dinilai sesuai maksud** ("Hebat, nunggu bus sejam" → negative).
5. **"Mending turun di Padalarang"** → `PADALARANG` positive + `KONEKTIVITAS_UMUM`
   (atau `JARAK_LOKASI` bila alasannya jarak) negative.
6. **Evidence** adalah blok teks sesingkat mungkin yang tetap bermakna, biasanya satu klausa.
   Jangan blok seluruh review jika cukup satu kalimat.
7. **issue_tags** dipilih dari daftar tetap (bisa lebih dari satu). Jika tidak ada yang cocok,
   pilih `lainnya` dan jelaskan di catatan.
8. **Centang "ragu"** jika tidak yakin. Semua label ragu akan dikumpulkan ke
   `data/labels/review_ragu.csv` untuk ditinjau ulang.

Tambahan:
- **Rating bintang tidak boleh menentukan sentimen.** Sentimen hanya ditentukan dari teks.
- Saran ("tolong tambah feeder") → negative, karena menyiratkan kekurangan saat ini.
- Pertanyaan ("ada angkot ke sini?") → neutral.
- Jalan kaki atau eskalator DI DALAM stasiun tidak termasuk. Jalan kaki dari pintu stasiun ke
  titik jemput, halte, atau parkir termasuk (aspek moda tersebut).
- Bahasa Sunda, slang, dan bahasa campur diperlakukan sama. Contoh: "tebih pisan" = jauh sekali,
  "hese" = susah, "heurin" = padat/macet.

## 3. Definisi aspek dan contoh (karangan)

### FEEDER_BUS
Bus feeder/shuttle resmi, DAMRI, TMP, Teman Bus, travel, halte bus.
- "Shuttle ke kota bersih dan AC-nya dingin." → positive · `nyaman`
- "Bus DAMRI-nya penuh, harus nunggu keberangkatan berikutnya." → negative · `penuh`, `waktu_tunggu_lama`
- "Dari halte depan ada TMP ke arah Cibiru." → neutral

### PADALARANG
Pilihan turun di Padalarang, KA Feeder, dan kereta penghubung ke Stasiun Bandung.
- "Lebih enak turun Padalarang, langsung sambung kereta ke Stasiun Bandung." → PADALARANG positive · `terintegrasi_baik`
- "Kereta feeder dari Padalarang sering penuh sesak." → negative · `penuh`
- "Kalau tujuannya Cimahi, turun di Padalarang saja." → neutral

### OJOL
Gojek, Grab, Maxim, inDrive, serta titik jemput dan drop-off ojol.
- "Dapat Grab cepat, kurang dari lima menit." → positive · `mudah_didapat`
- "Titik jemput ojol jauh di luar pagar, harus jalan kaki sepuluh menit." → negative · `titik_jemput_jauh`
- "Pesan GoCar dari sini tarifnya dua kali lipat biasanya." → negative · `tarif_mahal`

### TAKSI
Taksi konvensional dan argo.
- "Taksi resmi tersedia di lobby, pakai argo." → positive · `mudah_didapat`
- "Sopir taksi pasang harga borongan tanpa argo." → negative · `tarif_mahal`, `pungli`
- "Ada antrean taksi di sisi timur." → neutral

### ANGKOT_OJEK_PANGKALAN
Angkot, angkutan umum informal, ojek pangkalan, dan calo.
- "Tidak ada angkot yang lewat depan stasiun." → negative · `tidak_tersedia`
- "Ojek pangkalan memaksa, harganya seenaknya." → negative · `tarif_mahal`, `pungli`
- "Angkot jurusan Gedebage ngetem di ujung jalan." → neutral

### PARKIR
Parkir kendaraan pribadi (kapasitas, tarif, parkir inap, valet) dan antar-jemput pribadi.
- "Parkirannya luas, gampang cari tempat." → positive · `luas`
- "Parkir inap mahal kalau lebih dari dua hari." → negative · `tarif_mahal`
- "Parkirnya luas tapi jauh dari pintu masuk." → mixed · `luas`, `lainnya`

### AKSES_JALAN_MACET
Kemacetan, kondisi jalan, akses tol, dan putar balik.
- "Akses dari gerbang tol dekat dan lancar." → positive
- "Jalan ke stasiun macet total di jam pulang kantor." → negative · `macet`
- "Harus putar balik jauh karena jalannya satu arah." → negative · `akses_jalan_buruk`

### JARAK_LOKASI
Lokasi stasiun relatif terhadap pusat kota atau tujuan.
- "Lokasinya dekat dari rumah saya di Bandung timur." → positive
- "Stasiunnya jauh dari pusat kota, di tengah sawah." → negative · `lokasi_jauh`
- "Keretanya cuma 30 menit, tapi ke kotanya satu jam." → negative · `lokasi_jauh`

### INTEGRASI_JADWAL
Jadwal moda lanjutan, jam operasional, waktu tunggu, sinkronisasi dengan kereta, dan tiket terusan.
- "Jadwal shuttle pas dengan jam kedatangan kereta." → positive · `terintegrasi_baik`
- "Kereta tiba jam sembilan malam, bus terakhir sudah berangkat." → negative · `jadwal_tidak_sinkron`, `jam_operasional_terbatas`
- "Menunggu bus lama sekali, tidak ada informasi jadwal." → negative · `waktu_tunggu_lama`, `informasi_kurang`

  Catatan: kalimat terakhir juga bisa diberi label FEEDER_BUS jika ada opini tentang bus itu sendiri.

### KONEKTIVITAS_UMUM
Penilaian umum tentang akses atau transportasi lanjutan tanpa menyebut moda spesifik.
- "Transportasi lanjutannya masih minim." → negative · `tidak_tersedia`
- "Pulangnya bingung mau naik apa." → negative · `informasi_kurang`
- "Aksesnya sekarang sudah jauh lebih gampang." → positive · `mudah_didapat`

## 4. Kasus tumpang tindih

| Kalimat (karangan) | Label |
|---|---|
| "Mending turun di Padalarang, di sini jauh ke mana-mana" | PADALARANG positive + JARAK_LOKASI negative |
| "Grab mahal karena stasiunnya jauh" | OJOL negative (`tarif_mahal`) + JARAK_LOKASI negative (`lokasi_jauh`) |
| "Bus terakhir jam 8, kereta terakhir jam 9" | INTEGRASI_JADWAL negative (`jadwal_tidak_sinkron`) |
| "Toiletnya bersih, parkirnya luas" | Hanya PARKIR positive. Toilet diabaikan. |
| "Keretanya cepat banget!" | tidak relevan |

## 4b. Konvensi tambahan (v1.1, dari adjudikasi)

| # | Kasus | Keputusan |
|---|---|---|
| R1 | "Dekat X" / letak stasiun yang hanya deskriptif ("dekat GBLA", "di pinggir tol dan sawah") | JARAK_LOKASI **neutral**. Positive hanya jika evaluatif ("ternyata dekat dari rumah"). |
| R2 | Daftar moda yang tersedia ("ada Damri dan taksi") | Satu span **neutral** per moda (evidence boleh sama). Positive jika ada kata penilaian ("gratis", "lengkap"). |
| R3 | "Akses" tanpa moda ("aksesnya susah") | KONEKTIVITAS_UMUM. Jika review yang sama membahas jalan/tol/macet/rute → AKSES_JALAN_MACET. |
| R4 | Fakta bahwa orang lain memilih Padalarang ("penumpang lebih banyak di Padalarang") | PADALARANG neutral, atau tidak relevan bila alasannya bukan konektivitas. Perbandingan eksplisit yang mengunggulkan Padalarang → aturan 5. Perbandingan yang mengunggulkan Tegalluar → PADALARANG negative. |
| R5 | Masalah zona drop-off / antar-jemput pribadi (jalur, bayar parkir saat drop-off, tempat duduk) | PARKIR |
| R6 | "Feeder" yang membandingkan dengan Padalarang (maksudnya KA feeder) | KONEKTIVITAS_UMUM (bukan FEEDER_BUS) |
| R7 | Caption/nama tempat tanpa pernyataan; perbandingan waktu kereta vs travel | tidak relevan |

## 5. Daftar issue_tags

tarif_mahal, tarif_wajar, waktu_tunggu_lama, tidak_tersedia, mudah_didapat,
titik_jemput_jauh, titik_jemput_membingungkan, jam_operasional_terbatas,
jadwal_tidak_sinkron, macet, akses_jalan_buruk, lokasi_jauh, informasi_kurang,
terintegrasi_baik, nyaman, luas, penuh, pungli, konflik_opang, kapasitas_kurang,
tidak_terintegrasi, lainnya (+ catatan).

Tag v1.1:
- `konflik_opang`: ojol dilarang masuk/menjemput atau diintimidasi oleh ojek pangkalan/preman
  (dipakai di OJOL dan/atau ANGKOT_OJEK_PANGKALAN). Tambah `pungli` bila ada pungutan uang.
- `kapasitas_kurang`: parkir sempit/kurang luas (lawan `luas`). `penuh` hanya bila disebut penuh/meluber.
- `tidak_terintegrasi`: moda lanjutan tidak terhubung/tidak terpadu (lawan `terintegrasi_baik`).

## Changelog
- v1 (2026-09-25): versi awal.
- v1.1 (2026-09-26): konvensi R1–R7 (bagian 4b) dari adjudikasi pelabelan Claude; issue_tags baru
  konflik_opang, kapasitas_kurang, tidak_terintegrasi (disetujui peneliti).
