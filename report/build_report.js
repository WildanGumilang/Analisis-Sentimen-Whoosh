// Membangun laporan Word: output/Laporan_Konektivitas_Whoosh_Tegalluar.docx
// Jalankan: npm install docx@9 && node report/build_report.js
const fs = require("fs");
const path = require("path");
// Cari paket docx: terpasang di project (npm install docx) atau di lokasi cache lokal.
let D;
try { D = require("docx"); } catch (e) { D = require("D:/wg/.cache/docxgen/node_modules/docx"); }
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, AlignmentType, HeadingLevel, LevelFormat, PageBreak, Header, Footer,
  PageNumber, TableLayoutType, VerticalAlign, ExternalHyperlink,
} = D;

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "output", "figures");
const OUT = path.join(ROOT, "output", "Laporan_Konektivitas_Whoosh_Tegalluar.docx");

// ------------------------------------------------------------------ gaya
const NAVY = "104281", BIRU = "2A78D6", MERAH = "E34948", ABU = "52514E", GARIS = "D9D8D3";
const FONT = "Calibri";
const LEBAR = 9360; // lebar isi (DXA): A4 11906 - margin 2x1273
let nomorGambar = 0, nomorTabel = 0, instansiList = 0;

// Teks sederhana dengan **tebal**, *miring*, dan tautan [[teks|url]]
function runs(teks, opsi = {}) {
  const hasil = [];
  const pola = /(\[\[[^\]|]+\|[^\]]+\]\]|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let terakhir = 0, m;
  while ((m = pola.exec(teks)) !== null) {
    if (m.index > terakhir) hasil.push(new TextRun({ text: teks.slice(terakhir, m.index), ...opsi }));
    const t = m[0];
    if (t.startsWith("[[")) {
      const [label, url] = t.slice(2, -2).split("|");
      hasil.push(new ExternalHyperlink({ link: url, children: [new TextRun({ text: label, ...opsi, color: BIRU, underline: {} })] }));
    } else if (t.startsWith("**")) hasil.push(new TextRun({ text: t.slice(2, -2), bold: true, ...opsi }));
    else hasil.push(new TextRun({ text: t.slice(1, -1), italics: true, ...opsi }));
    terakhir = m.index + t.length;
  }
  if (terakhir < teks.length) hasil.push(new TextRun({ text: teks.slice(terakhir), ...opsi }));
  return hasil;
}
const P = (teks, o = {}) => new Paragraph({ children: runs(teks, o.run || {}), spacing: { after: 140, line: 300 },
  alignment: o.align || AlignmentType.JUSTIFIED, ...(o.para || {}) });
const H1 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_1, pageBreakBefore: true });
const H2 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_2 });
const H3 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_3 });
const kosong = () => new Paragraph({ text: "", spacing: { after: 60 } });

function bullets(daftar) {
  return daftar.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "bul", level: 0 },
    spacing: { after: 80, line: 290 } }));
}
function bernomor(daftar) {
  instansiList += 1;
  return daftar.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "num", level: 0, instance: instansiList },
    spacing: { after: 100, line: 290 } }));
}
// Kutipan: versi dirapikan (parafrase) + teks asli persis dari ulasan (bila ada)
function kutipan(teks, keterangan, asli) {
  const garis = { left: { style: BorderStyle.SINGLE, size: 18, color: "B7D3F6", space: 10 } };
  const isi = [new TextRun({ text: `“${teks}”`, italics: true, color: "333333" })];
  if (keterangan) isi.push(new TextRun({ text: `  (${keterangan})`, color: "7A7974", size: 18 }));
  const par = [new Paragraph({ children: isi, indent: { left: 400, right: 300 }, keepNext: !!asli,
    spacing: { before: 60, after: asli ? 20 : 100, line: 290 }, border: garis })];
  if (asli) par.push(new Paragraph({ indent: { left: 400, right: 300 }, spacing: { after: 110, line: 270 }, border: garis,
    children: [new TextRun({ text: "Teks asli: ", size: 17, color: "7A7974", bold: true }),
      new TextRun({ text: `“${asli}”`, size: 17, color: "5A5955" })] }));
  return par;
}
// Kotak sorotan: jenis "kini" (biru), "konteks" (kuning), "catatan" (abu)
function kotak(jenis, judul, isiParagraf) {
  const warna = { kini: ["EAF2FC", BIRU], konteks: ["FDF5E3", "EDA100"], catatan: ["F3F2EF", "8F8E88"] }[jenis];
  const par = [new Paragraph({ children: [new TextRun({ text: judul, bold: true, color: warna[1] === "EDA100" ? "8A5A00" : NAVY })],
    spacing: { after: 80 } })];
  for (const t of isiParagraf) {
    if (Array.isArray(t)) t.forEach((b) => par.push(new Paragraph({ children: runs(b), numbering: { reference: "bul", level: 0 },
      spacing: { after: 60, line: 280 } })));
    else par.push(new Paragraph({ children: runs(t), spacing: { after: 80, line: 285 } }));
  }
  return new Table({
    width: { size: LEBAR, type: WidthType.DXA }, columnWidths: [LEBAR], layout: TableLayoutType.FIXED,
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      width: { size: LEBAR, type: WidthType.DXA }, children: par,
      shading: { type: ShadingType.CLEAR, color: "auto", fill: warna[0] },
      margins: { top: 140, bottom: 120, left: 220, right: 220 },
      borders: { left: { style: BorderStyle.SINGLE, size: 24, color: warna[1] }, top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" } },
    })] })],
  });
}
// Kartu angka kunci
function kartuAngka(items) {
  const w = Math.floor(LEBAR / items.length);
  const sel = items.map(([angka, label]) => new TableCell({
    width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: { type: ShadingType.CLEAR, color: "auto", fill: "F4F8FD" },
    margins: { top: 160, bottom: 160, left: 120, right: 120 },
    borders: { top: { style: BorderStyle.SINGLE, size: 18, color: BIRU }, bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      left: { style: BorderStyle.SINGLE, size: 12, color: "FFFFFF" }, right: { style: BorderStyle.SINGLE, size: 12, color: "FFFFFF" } },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: angka, bold: true, size: 40, color: NAVY })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 }, children: [new TextRun({ text: label, size: 18, color: ABU })] }),
    ],
  }));
  return new Table({ width: { size: w * items.length, type: WidthType.DXA }, columnWidths: items.map(() => w),
    layout: TableLayoutType.FIXED, rows: [new TableRow({ children: sel })] });
}
// Tabel data
function tabel(judul, header, baris, lebarKolom, catatan) {
  nomorTabel += 1;
  const total = lebarKolom.reduce((a, b) => a + b, 0);
  const skala = LEBAR / total;
  const lk = lebarKolom.map((x) => Math.floor(x * skala));
  const selBorder = { top: { style: BorderStyle.SINGLE, size: 4, color: GARIS }, bottom: { style: BorderStyle.SINGLE, size: 4, color: GARIS },
    left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" } };
  const rows = [new TableRow({ tableHeader: true, children: header.map((h, i) => new TableCell({
    width: { size: lk[i], type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, color: "auto", fill: NAVY },
    margins: { top: 80, bottom: 80, left: 100, right: 100 }, borders: selBorder, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF", size: 19 })] })] })) })];
  baris.forEach((r, bi) => rows.push(new TableRow({ cantSplit: true, children: r.map((c, i) => new TableCell({
    width: { size: lk[i], type: WidthType.DXA }, borders: selBorder,
    shading: { type: ShadingType.CLEAR, color: "auto", fill: bi % 2 ? "F7F9FC" : "FFFFFF" },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: runs(String(c), { size: 19 }) })] })) })));
  const out = [new Paragraph({ keepNext: true, spacing: { before: 160, after: 80 }, children: [
    new TextRun({ text: `Tabel ${nomorTabel}. `, bold: true, color: NAVY, size: 19 }), new TextRun({ text: judul, size: 19, color: NAVY })] }),
  new Table({ width: { size: lk.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: lk, layout: TableLayoutType.FIXED, rows })];
  if (catatan) out.push(new Paragraph({ spacing: { before: 60, after: 160 }, children: runs(catatan, { size: 17, color: "7A7974", italics: true }) }));
  else out.push(kosong());
  return out;
}
// Gambar dengan keterangan
const UKURAN = {
  "01_sentimen_per_aspek.png": [1200, 690], "02_net_sentiment.png": [1125, 660], "03_tren_negatif.png": [1350, 780],
  "04_ols_rating.png": [1125, 852], "05_pareto_keluhan.png": [1200, 630], "06_heatmap_aspek_tag.png": [1650, 720],
  "07_matriks_prioritas.png": [1275, 810], "08_kookurensi_aspek.png": [1125, 930], "09_fokus_terkini.png": [1200, 720],
};
function gambar(file, keterangan, lebarPx = 600) {
  nomorGambar += 1;
  const [w, h] = UKURAN[file];
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 }, children: [new ImageRun({
      type: "png", data: fs.readFileSync(path.join(FIG, file)), transformation: { width: lebarPx, height: Math.round(lebarPx * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
      new TextRun({ text: `Gambar ${nomorGambar}. `, bold: true, size: 18, color: NAVY }), ...runs(keterangan, { size: 18, color: ABU })] }),
  ];
}

// ------------------------------------------------------------------ ISI
const isi = [];
const tambah = (...x) => x.flat().forEach((e) => isi.push(e));

// ---------- Sampul
tambah(
  new Paragraph({ spacing: { before: 2600 }, children: [new TextRun({ text: "LAPORAN ANALISIS ULASAN PENGGUNA", bold: true, color: BIRU, size: 22 })] }),
  new Paragraph({ spacing: { before: 200, after: 200 }, children: [new TextRun({ text: "Konektivitas Transportasi Stasiun Whoosh Tegalluar", bold: true, size: 56, color: NAVY })] }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: "Apa yang dialami penumpang saat menuju dan meninggalkan stasiun, menurut 1.191 ulasan Google Maps", size: 28, color: ABU })] }),
  new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 12, color: BIRU, space: 12 } }, spacing: { before: 400 }, children: [
    new TextRun({ text: "Data ulasan per 25 September 2026  ·  Laporan disusun 26 September 2026", size: 20, color: ABU })] }),
  new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "Lokasi: Stasiun Tegalluar Summarecon, Kabupaten Bandung, Jawa Barat", size: 20, color: ABU })] }),
);

// ---------- Isi dokumen
tambah(
  new Paragraph({ pageBreakBefore: true, spacing: { after: 240 }, children: [new TextRun({ text: "Isi Dokumen", bold: true, size: 34, color: NAVY })] }),
  ...tabel("Peta isi laporan", ["Bagian", "Isi", "Untuk menjawab"], [
    ["1. Ringkasan", "Temuan utama dalam dua halaman", "Apa yang sedang terjadi?"],
    ["2. Tentang kajian ini", "Sumber data, cara kerja analisis, cara membaca angka", "Dari mana angka-angka ini?"],
    ["3. Gambaran besar", "Seberapa besar isu konektivitas dan bagaimana nadanya", "Seberapa penting masalah ini?"],
    ["4. Fenomena saat ini", "Topik yang dibicarakan dalam 11 bulan terakhir dan prioritasnya", "Apa yang menonjol sekarang?"],
    ["5. Pembahasan per tema", "Sepuluh tema, dari yang paling mendesak", "Apa persisnya masalahnya?"],
    ["6. Pemicu ketidakpuasan", "Keluhan yang paling menurunkan rating dan paling didukung", "Apa yang paling merugikan?"],
    ["7. Pola lain", "Keluhan yang muncul bersamaan, permintaan pengguna, tema tambahan", "Apa lagi yang perlu diketahui?"],
    ["8. Konteks kebijakan", "Peristiwa resmi yang menjelaskan kondisi sekarang", "Mengapa kondisinya begini?"],
    ["9. Rekomendasi", "Delapan langkah, dari yang cepat sampai jangka panjang", "Apa yang bisa dilakukan?"],
    ["10. Kekuatan temuan", "Tingkat keyakinan, keterbatasan, saran riset lanjutan", "Seberapa jauh bisa dipercaya?"],
    ["Lampiran", "Tabel lengkap, glosarium, rincian metode, daftar berkas, sumber linimasa, sumber data Google Maps", "Rujukan"],
  ], [2300, 4200, 2860]),
);

// ================================================================== 1. RINGKASAN
tambah(
  H1("1. Ringkasan"),
  P("Stasiun Whoosh Tegalluar dipuji sebagai bangunan: bersih, luas, dan modern. Yang dikeluhkan adalah perjalanan **menuju dan meninggalkan** stasiun. Dari 673 ulasan yang berisi teks, 234 (35%) membahas hal ini, dan kelompok ulasan ini memberi rata-rata **3,9 bintang**, jauh di bawah 4,6 bintang dari ulasan lain. Dua dari tiga ulasan bintang 1–2 yang berisi teks juga menyinggung konektivitas."),
  kartuAngka([["1.191", "ulasan Google Maps dari 5 listing"], ["234", "ulasan membahas konektivitas"], ["3,9 vs 4,6", "rata-rata bintang: ulasan konektivitas vs lainnya"], ["0", "ulasan yang dibalas pengelola"]]),
  kosong(),
  H2("Lima hal yang terjadi sekarang"),
  P("Lima temuan berikut disusun dari kondisi 11 bulan terakhir (Oktober 2025–September 2026), dibandingkan dengan masa awal operasi."),
  ...bernomor([
    "**Keluhan utama sekarang adalah jalan dan jarak.** Dalam 11 bulan terakhir, jarak/lokasi menjadi topik yang paling sering dibahas (31% dari seluruh penyebutan), disusul akses jalan (23%). Dari 19 penyebutan soal jalan, 14 bernada negatif: jalan sempit melewati kampung, gelap di malam hari, akses tol yang tidak pasti, dan rute yang membingungkan.",
    "**Parkir naik menjadi sumber keluhan ketiga.** Dari 15 penyebutan terbaru, 10 negatif. Yang dikeluhkan adalah lahan yang panas tanpa atap, kapasitas yang sempit (hanya 95 lot mobil, dibanding 630 di Stasiun Halim), alur drop-off yang membuat pengantar tetap harus membayar, dan cara pembayaran.",
    "**Angkutan umum reguler belum ada.** Pilihan yang tersedia hanya bus DAMRI, shuttle ke Summarecon, taksi, dan ojek daring. Layanan yang ada dinilai membantu, tetapi pengulas menggambarkan stasiun ini sebagai “stasiun elit, angkutan sulit”. Stasiun Padalarang, yang punya kereta penghubung gratis ke pusat kota, kini dipuji dalam 5 dari 6 penyebutan terbaru.",
    "**Konflik ojek pangkalan dengan ojek daring sudah tidak muncul lagi.** Konflik ini adalah keluhan paling keras di masa awal operasi: 24 ulasan dan hampir semua ulasan dengan dukungan terbanyak. Sejak periode menengah, tidak ada lagi ulasan yang menyebutnya. Keluhan ojek daring yang tersisa soal tarif mahal dan pesanan yang lama lalu dibatalkan.",
    "**Pengelola tidak menanggapi.** Tidak satu pun dari 1.191 ulasan di kelima listing pernah dibalas, termasuk keluhan yang didukung belasan pengguna lain.",
  ]),
  kotak("catatan", "Perlu diketahui sebelum membaca", [
    "Penandaan topik dan nada setiap ulasan dilakukan oleh **model kecerdasan buatan (AI)** dengan dua putaran pemeriksaan, tetapi **belum dicocokkan dengan penilaian manusia**. Angka dalam laporan ini sebaiknya dibaca sebagai pola yang kuat, bukan ukuran yang presisi. Tanggal ulasan juga hanya perkiraan, karena Google hanya menampilkan keterangan seperti “setahun lalu”. Rinciannya ada di Bab 10.",
  ]),
);

// ================================================================== 2. TENTANG KAJIAN
tambah(
  H1("2. Tentang Kajian Ini"),
  H2("2.1 Mengapa ulasan Google Maps"),
  P("Stasiun Tegalluar adalah stasiun akhir Kereta Cepat Whoosh di sisi Bandung. Letaknya di Kabupaten Bandung bagian timur, di kawasan yang masih berupa sawah dan permukiman ketika stasiun mulai beroperasi pada 17 Oktober 2023. Perjalanan kereta dari Jakarta hanya sekitar 45 menit, tetapi penumpang masih harus menempuh perjalanan lanjutan ke tujuan akhir. Kualitas perjalanan lanjutan inilah (sering disebut *first mile* dan *last mile*) yang menentukan apakah waktu yang dihemat di kereta benar-benar terasa."),
  P("Ulasan Google Maps adalah catatan pengalaman yang ditulis pengguna atas inisiatif sendiri, tanpa dipandu pertanyaan survei. Kelebihannya, topik yang muncul benar-benar hal yang dianggap penting oleh pengguna. Kekurangannya, penulis ulasan belum tentu mewakili seluruh penumpang. Kajian ini membaca seluruh ulasan yang tersedia untuk menjawab satu pertanyaan: **bagaimana pengguna menilai perjalanan menuju dan dari Stasiun Tegalluar, dan masalah apa yang paling menonjol saat ini?**"),
  H2("2.2 Data yang dikumpulkan"),
  P("Di Google Maps, stasiun ini tercatat dalam lima *listing* terpisah dengan nama berbeda, tetapi titik lokasinya berdekatan (dalam radius sekitar 200 meter). Seluruh ulasan dari kelima listing diambil pada 25 September 2026, dan jumlahnya sama persis dengan angka yang ditampilkan Google."),
  ...tabel("Sumber ulasan", ["Listing di Google Maps", "Tautan", "Ulasan", "Membahas konektivitas"], [
    ["Stasiun Kereta Cepat Tegalluar", "[[maps.app.goo.gl/RVeUwckH69V2AXit8|https://maps.app.goo.gl/RVeUwckH69V2AXit8]]", "416", "135"],
    ["Kereta Cepat Whoosh Tegalluar", "[[maps.app.goo.gl/qSH4xZkqkBoF3FzP7|https://maps.app.goo.gl/qSH4xZkqkBoF3FzP7]]", "663", "72"],
    ["Tegalluar Summarecon", "[[maps.app.goo.gl/sT2KabtsJ7ywaAQY9|https://maps.app.goo.gl/sT2KabtsJ7ywaAQY9]]", "72", "17"],
    ["Parkir Timur Stasiun Kereta Cepat Tegalluar", "[[maps.app.goo.gl/vddqzKDfdVzJMnEh7|https://maps.app.goo.gl/vddqzKDfdVzJMnEh7]]", "23", "6"],
    ["Stasiun KCJB Tegalluar", "[[maps.app.goo.gl/tWh3hbaB6Ypk5Zqt5|https://maps.app.goo.gl/tWh3hbaB6Ypk5Zqt5]]", "17", "4"],
    ["**Total**", "", "**1.191**", "**234**"],
  ], [3300, 3560, 1000, 1500], "Tautan dapat diklik. Tidak ada ulasan ganda antar-listing. Kolom terakhir dihitung dari ulasan yang berisi teks. Koordinat dan ID tempat setiap listing ada di Lampiran F."),
  P("Dari 1.191 ulasan, **518 hanya berisi bintang tanpa tulisan**, sehingga hanya dipakai untuk statistik rating. Sisanya, 673 ulasan bertekstual, dibaca satu per satu. Sebagian besar ditulis dalam bahasa Indonesia (587), lalu Inggris (73), dan sedikit dalam bahasa Jepang, Arab, Jerman, Sunda, dan Mandarin. Ulasan berbahasa asing ikut dianalisis dalam bahasa aslinya. Nama, foto, dan tautan profil pengulas tidak disimpan."),
  H2("2.3 Bagaimana ulasan dianalisis"),
  P("Analisis yang dipakai disebut **analisis sentimen berbasis aspek**. Satu ulasan sering membahas beberapa hal sekaligus dengan penilaian yang berbeda-beda. Karena itu, setiap ulasan dipecah menurut **aspek** (hal yang dibicarakan) dan **sentimen** (penilaian terhadap hal tersebut). Contohnya:"),
  ...kutipan("Stasiunnya bagus, parkirnya luas tapi panas, cuma jalan ke sininya macet parah.", "contoh karangan, bukan dari data"),
  P("Ulasan di atas menghasilkan dua penanda. **Parkir** bernilai *campuran* (luas tetapi panas), dan **akses jalan** bernilai *negatif*. Pujian untuk bangunan stasiun tidak dihitung, karena bukan soal konektivitas. Prosesnya berlangsung dalam lima langkah:"),
  ...tabel("Lima langkah analisis", ["Langkah", "Yang dilakukan"], [
    ["1. Mengumpulkan", "Mengambil seluruh ulasan dari lima listing Google Maps beserta bintang, tanggal perkiraan, jumlah ‘suka’, dan keberadaan foto."],
    ["2. Memilah", "Mengenali bahasa setiap ulasan, memecah kalimat panjang menjadi klausa, lalu menyaring ulasan yang mungkin menyinggung transportasi menggunakan daftar kata kunci dan kemiripan makna. Penyaringan dibuat longgar agar tidak ada yang terlewat. Pengecekan akhir menunjukkan tidak ada ulasan relevan yang tersaring keluar."],
    ["3. Menandai", "Setiap ulasan dibaca dan ditandai: relevan atau tidak, aspek apa, sentimennya, kutipan pendukungnya, dan jenis masalahnya (misalnya ‘tarif mahal’ atau ‘lokasi jauh’). Penandaan dilakukan oleh AI dalam dua putaran terpisah, lalu perbedaan antar-putaran diputuskan satu per satu."],
    ["4. Menghitung", "Menghitung jumlah dan persentase per aspek, perubahan antar-periode, hubungan dengan bintang, serta keluhan yang sering muncul bersamaan."],
    ["5. Menafsirkan", "Membaca ulang seluruh 447 kutipan untuk memahami cerita di balik angka, lalu mencocokkannya dengan pengumuman resmi dan pemberitaan."],
  ], [1900, 7460]),
  H2("2.4 Sepuluh aspek yang diamati"),
  P("Semua opini tentang perjalanan menuju dan dari stasiun dikelompokkan ke dalam sepuluh aspek berikut. Aspek ‘konektivitas umum’ menampung penilaian yang tidak menyebut moda tertentu, misalnya “Minim transportasi umum.”"),
  ...tabel("Aspek konektivitas", ["Aspek", "Cakupan"], [
    ["Feeder/bus", "Bus DAMRI, shuttle resmi dan shuttle Summarecon, halte bus"],
    ["Padalarang (KA feeder)", "Pilihan turun di Stasiun Padalarang dan kereta penghubung ke Stasiun Bandung"],
    ["Ojol", "Ojek dan mobil daring (Gojek, Grab, Maxim, inDrive), titik jemput"],
    ["Taksi", "Taksi konvensional seperti Bluebird"],
    ["Angkot/opang", "Angkot, ojek pangkalan, calo"],
    ["Parkir & antar-jemput", "Lahan parkir, tarif, parkir inap, zona drop-off dan penjemputan"],
    ["Akses jalan & macet", "Kondisi jalan, kemacetan, akses tol, rute dan petunjuk jalan"],
    ["Jarak & lokasi", "Letak stasiun terhadap pusat kota atau tujuan"],
    ["Integrasi jadwal", "Keselarasan jadwal angkutan lanjutan dengan kedatangan kereta"],
    ["Konektivitas umum", "Penilaian umum tentang akses dan angkutan tanpa menyebut moda"],
  ], [2600, 6760]),
  H2("2.5 Cara membaca angka dalam laporan"),
  P("Beberapa istilah akan sering muncul:"),
  ...bullets([
    "**Penyebutan** adalah satu aspek dalam satu ulasan. Ulasan yang membahas parkir dan jalan dihitung sebagai dua penyebutan. Total ada 392 penyebutan dari 234 ulasan.",
    "**Net sentiment** adalah persentase positif dikurangi persentase negatif. Nilai −60 berarti keluhan jauh lebih banyak daripada pujian, sedangkan +40 berarti sebaliknya. Nilai di sekitar 0 berarti berimbang, atau kebanyakan netral.",
    "**Rentang ketidakpastian (interval kepercayaan 95%)** ditampilkan sebagai garis di grafik. Makin sedikit ulasan, makin panjang garisnya. Dua angka yang garisnya tumpang tindih belum tentu benar-benar berbeda.",
    "**Periode waktu.** Google hanya menulis “setahun lalu” atau “2 tahun lalu”, dan 74% ulasan konektivitas bertanggal seperti itu. Karena itu, ulasan dibagi ke tiga periode: **masa awal** (±2 tahun lalu, kira-kira akhir 2023 sampai awal 2025), **periode menengah** (±setahun lalu, kira-kira 2025), dan **periode terkini** (11 bulan terakhir, Oktober 2025–September 2026). Angka untuk kelompok yang berisi kurang dari 10 penyebutan tidak ditampilkan.",
  ]),
);

// ================================================================== 3. GAMBARAN BESAR
tambah(
  H1("3. Gambaran Besar"),
  H2("3.1 Seberapa besar isu konektivitas"),
  P("Sepertiga ulasan bertekstual (234 dari 673) menyinggung perjalanan menuju atau dari stasiun. Angka ini cukup besar, mengingat pengulas tidak diminta membahas topik tersebut. Perbedaannya paling jelas terlihat pada bintang. Di antara ulasan yang tidak membahas konektivitas, 347 dari 439 (79%) memberi bintang 5. Di antara ulasan konektivitas, hanya 117 dari 234 (50%)."),
  ...tabel("Sebaran bintang menurut isi ulasan", ["Kelompok ulasan", "★1", "★2", "★3", "★4", "★5", "Rata-rata"], [
    ["Membahas konektivitas (234)", "31", "15", "17", "54", "117", "**3,90**"],
    ["Tidak membahas konektivitas (439)", "24", "1", "9", "58", "347", "**4,60**"],
    ["Hanya bintang, tanpa teks (518)", "–", "–", "–", "–", "–", "**4,80**"],
  ], [3600, 800, 800, 800, 800, 900, 1660]),
  P("Dari 71 ulasan bertekstual yang memberi bintang 1 atau 2, **46 (65%) membahas konektivitas**. Dengan kata lain, ketika pengguna kecewa berat pada stasiun ini, penyebabnya lebih sering perjalanan ke sana daripada stasiunnya sendiri."),
  H2("3.2 Nada keseluruhan: lebih banyak keluhan daripada pujian"),
  P("Dari 392 penyebutan aspek konektivitas, **218 (56%) negatif**, 90 (23%) positif, 73 (19%) netral, dan 11 (3%) campuran. Kalau dilihat per ulasan, 135 dari 234 ulasan (58%) hanya berisi keluhan, 50 (21%) hanya pujian, 28 (12%) berisi keduanya, dan 21 (9%) hanya menyampaikan informasi tanpa penilaian."),
  P("Nada ini tidak merata antar-aspek. Grafik berikut mengurutkan kesepuluh aspek dari yang paling dipuji sampai yang paling dikeluhkan."),
  ...gambar("01_sentimen_per_aspek.png", "Komposisi sentimen per aspek (seluruh periode). Angka n menunjukkan jumlah penyebutan."),
  P("Ada tiga kelompok yang terlihat jelas. **Angkot/opang, akses jalan, dan konektivitas umum** hampir seluruhnya negatif (75–96%). **Parkir, jarak & lokasi, dan ojol** terbelah, dengan porsi pujian yang masih berarti. **Feeder/bus dan taksi** didominasi penyebutan netral: pengulas memberi tahu bahwa layanan itu ada, tanpa mengeluhkannya. Padalarang adalah satu-satunya aspek yang jelas positif, karena disebut sebagai pembanding yang lebih baik."),
  ...gambar("02_net_sentiment.png", "Net sentiment per aspek beserta rentang ketidakpastiannya. Titik berongga menandakan data terlalu sedikit (n < 10)."),
  P("Rentang ketidakpastian pada gambar ini penting untuk dibaca. Garis feeder/bus dan taksi melintasi angka nol, sehingga keduanya belum bisa disebut jelas positif. Sebaliknya, lima aspek paling bawah (ojol, konektivitas umum, akses jalan, angkot/opang, dan integrasi jadwal yang datanya sangat sedikit) seluruh garisnya berada di sisi negatif."),
);

// ================================================================== 4. FENOMENA SAAT INI
tambah(
  H1("4. Fenomena Saat Ini"),
  P("Gambaran di Bab 3 menggabungkan seluruh periode sejak stasiun beroperasi. Bab ini memisahkan **apa yang dibicarakan sekarang**, karena sebagian masalah masa awal sudah mereda sementara masalah lain justru makin menonjol."),
  H2("4.1 Topik bergeser dari ojek ke jalan, jarak, dan parkir"),
  ...gambar("09_fokus_terkini.png", "Porsi setiap aspek dari seluruh penyebutan pada masa awal (abu-abu) dan 11 bulan terakhir (biru), beserta jumlah penyebutan negatif pada periode terkini."),
  P("Perbandingan ini menunjukkan pergeseran yang tajam. Di masa awal, percakapan paling ramai soal **ojek daring (16%)** dan **ojek pangkalan (10%)**. Dalam 11 bulan terakhir, keduanya hampir hilang: ojol tinggal 3 penyebutan dan ojek pangkalan tidak disebut sama sekali. Tempatnya diisi tiga topik:"),
  ...bullets([
    "**Jarak & lokasi** naik dari 15% menjadi **31%**. Nadanya terbelah: 10 negatif, 10 positif, 5 netral, dan 1 campuran dari 26 penyebutan.",
    "**Akses jalan & macet** naik dari 14% menjadi **23%**, dengan **14 dari 19 negatif**.",
    "**Parkir & antar-jemput** naik dari 11% menjadi **18%**, dengan **10 dari 15 negatif**.",
  ]),
  P("Perlu dicatat bahwa perhatian terhadap konektivitas secara keseluruhan justru berkurang. Di masa awal, 44% ulasan bertekstual (123 dari 278) membahas konektivitas. Dalam 11 bulan terakhir, angkanya 28% (62 dari 225). Rata-rata bintang ulasan konektivitas sedikit membaik, dari 3,77 menjadi 3,97. Jadi kondisi sekarang tidak lebih buruk. Yang berubah adalah jenis masalahnya: dari masalah masa peluncuran menjadi masalah struktural yang belum tertangani."),
  kotak("kini", "Kondisi sekarang dalam satu paragraf", [
    "Pengguna yang datang dengan kendaraan pribadi berhadapan dengan jalan sempit, gelap, dan kadang macet, lalu dengan lahan parkir yang panas dan terbatas. Pengguna tanpa kendaraan pribadi bergantung pada DAMRI, shuttle, taksi, atau ojek daring, karena tidak ada angkutan umum reguler. Sebagian pengguna yang tinggal di Bandung timur justru menganggap letak stasiun menguntungkan, sementara yang menuju pusat kota menyarankan turun di Padalarang.",
  ]),
  H2("4.2 Mana yang paling mendesak"),
  P("Dua pertanyaan berguna untuk menentukan prioritas: seberapa sering sebuah aspek dibicarakan, dan seberapa negatif nadanya. Grafik berikut memetakan kedua ukuran itu untuk seluruh periode."),
  ...gambar("07_matriks_prioritas.png", "Matriks prioritas. Sumbu mendatar menunjukkan seberapa sering aspek dibahas, sumbu tegak menunjukkan net sentiment. Ukuran titik menunjukkan besarnya penurunan bintang ketika aspek tersebut dikeluhkan."),
  P("Kuadran kanan bawah (sering dibahas dan negatif) berisi **akses jalan, konektivitas umum, ojol, parkir, dan jarak & lokasi**. Dari kelimanya, tiga yang masih dominan di periode terkini adalah akses jalan, parkir, dan jarak & lokasi, sehingga ketiganya menjadi prioritas saat ini. Titik angkot/opang paling besar karena keluhan ini paling menurunkan bintang, tetapi topiknya sudah tidak muncul lagi di ulasan terbaru."),
  ...gambar("05_pareto_keluhan.png", "Jumlah keluhan per aspek, diurutkan dari yang terbanyak, beserta persentase kumulatifnya."),
  P("Kalau semua keluhan dijumlahkan (229 penyebutan negatif atau campuran), **lima aspek menyumbang 84%**: akses jalan (47), parkir (41), konektivitas umum (38), jarak & lokasi (38), dan ojol (29). Memperbaiki kelima aspek ini akan menjawab sebagian besar keluhan yang pernah ditulis."),
);

// ================================================================== 5. PER TEMA
tambah(
  H1("5. Pembahasan per Tema"),
  P("Bab ini membahas setiap tema secara lebih dekat. Urutannya mengikuti tingkat urgensi saat ini, dimulai dari masalah yang paling banyak dikeluhkan dalam 11 bulan terakhir. Setiap kutipan ditampilkan dalam dua bentuk: versi yang dirapikan agar mudah dibaca, dan **teks asli** persis seperti yang ditulis pengulas, termasuk salah ketik dan singkatannya. Garis miring (/) menandai pergantian baris pada ulasan asli. Identitas pengulas tidak dicantumkan."),

  H2("5.1 Jalan menuju stasiun: masalah yang paling awet"),
  P("Akses jalan adalah aspek dengan keluhan terbanyak sepanjang masa (47 keluhan dari 61 penyebutan) dan tidak menunjukkan perbaikan. Persentase negatifnya sama, sekitar 74%, di masa awal maupun periode terkini, sementara porsinya dalam percakapan justru naik. Keluhannya sangat spesifik, sehingga bisa dipetakan titik demi titik:"),
  ...bullets([
    "**Jalan sempit melewati kampung atau sawah, sebagian rusak.** Ini keluhan paling umum (50 kutipan bertanda ‘akses jalan buruk’). Pengulas menyebut ruas yang hanya sebagian dicor dan jalan yang sulit dilalui dua mobil.",
    "**Akses tol tidak pasti.** Pengendara mengira ada pintu tol di dekat stasiun, ternyata tidak ada atau sedang ditutup. Mereka meminta akses tol langsung, terutama dari arah timur.",
    "**Tersasar karena peta digital.** Google Maps disebut mengarahkan pengendara lewat jalan sawah, Majalaya, Dayeuhkolot, atau desa Tegalluar. Bus pariwisata disebut rawan tersasar.",
    "**Gelap di malam hari.** Penerangan di ruas Gedebage–GBLA menuju stasiun disebut sangat kurang, dan keluhan ini masih muncul di periode terkini.",
    "**Macet di titik tertentu:** pertigaan menuju stasiun, perlintasan kereta api, Jalan Soekarno-Hatta arah Cibiru, dan lalu lintas akhir pekan menuju Masjid Al Jabbar.",
    "**Banjir saat hujan.** Satu pengulas terjebak banjir ketika hendak ke stasiun, lalu ditolak banyak taksi.",
  ]),
  ...kutipan("Orang Bandung sendiri saja pusing melihat jalannya, sampai tersasar ke jalan kecil.", "periode terkini", "org bdg sj pusing lihat jalan nya sampai nyasar ke jalan kecil"),
  ...kutipan("Jalannya perlu diperlebar dan diberi banyak lampu, karena kalau malam gelap sekali.", "periode terkini", "utk jln ny diperbesar dan perbagus banyak lampu juga karena kalau malam gelap sekali"),
  ...kutipan("Pintu tol yang paling dekat malah ditutup, jadi harus memutar lewat kampung.", "periode terkini", "Apa lagi mau keluar trus masuk pintu TOL yg deket malah di tutup / Jadi muter lewat kampung"),
  P("Pujian untuk jalan jarang, dan umumnya datang dari pengulas yang tinggal di Bandung timur atau yang datang saat jalanan sepi. Keluhan jalan juga berdampak nyata pada kepuasan: ulasan yang mengeluhkan jalan rata-rata memberi **0,9 bintang lebih rendah** daripada ulasan lain (lihat Bab 6)."),
  kotak("konteks", "Konteks: akses tol yang berubah-ubah", [
    "Pintu tol terdekat, exit Gedebage KM 149, awalnya hanya buka pukul 07.00–17.00. Perpanjangan jam operasi dan pembukaan akses KM 149 A dan KM 151 A diumumkan hanya untuk masa libur Natal dan Tahun Baru, dan exit KM 149 sempat ditutup untuk perbaikan jembatan pada Januari 2024. Akses yang tidak permanen ini menjelaskan mengapa pengendara bingung dan tersasar, terutama penumpang kereta pagi dan malam yang datang di luar jam operasi.",
  ]),

  H2("5.2 Jarak dan lokasi: jauh bagi sebagian, dekat bagi yang lain"),
  P("Jarak & lokasi kini topik yang paling sering dibahas (26 penyebutan dalam 11 bulan terakhir). Uniknya, nadanya benar-benar terbelah, dan pembedanya adalah asal dan tujuan pengulas."),
  P("**Bagi yang menuju pusat Kota Bandung**, stasiun terasa jauh. Pengulas menyebutnya terpencil, “di tengah sawah”, atau “jauh dari mana2”. Ada yang mencatat perjalanan mobil ke kawasan Trans Studio Mall memakan waktu sekitar 1,5 jam, sehingga waktu yang dihemat di kereta hilang di jalan."),
  P("**Bagi warga Bandung timur dan wilayah Priangan timur**, letak stasiun justru menguntungkan. Pengulas menyebut kedekatannya dengan Cileunyi, Jatinangor, Rancaekek, Buah Batu, Summarecon, bahkan Pangalengan, Garut, dan Tasikmalaya. Ada yang cukup naik motor lima menit dari rumah."),
  ...kutipan("Bus berbayar ke Kota Bandung butuh waktu sekitar satu jam lebih, karena jauh dan macet.", "periode terkini", "Disediakan bus berbayar jika ingin ke Kota Bandung yang jarak tempuhnya sekitar 1 jam lebih, karena jauh dan macet."),
  ...kutipan("Buat yang kampungnya di Jatinangor, Cileunyi, Pangalengan, Rancaekek, Garut, atau Tasik, mantap.", "masa awal", "Yg kampungya di jatinangor cileunyi pangalengan rancaeke garut tasik mantablah"),
  ...kutipan("Bisa turun di sini untuk yang rumahnya di Bandung timur dan sekitarnya.", "periode terkini", "bisa turun disini buat yang rumahnya diarea bandung timur dan sekitarnya."),
  P("Keluhan lokasi **tidak menurunkan bintang**. Ulasan yang mengeluhkan jarak tetap memberi rata-rata 4,3 bintang, dan hubungan statistiknya dengan rating tidak signifikan. Pengguna tampaknya menerima letak stasiun sebagai hal yang tidak bisa diubah. Yang mereka keluhkan adalah bagaimana jarak itu ditempuh, yaitu jalan dan angkutannya. Porsi negatif untuk aspek ini juga menurun dari 57% di masa awal menjadi 38% di periode terkini, sejalan dengan berkembangnya kawasan di sekitar stasiun."),

  H2("5.3 Parkir dan antar-jemput: luas, tapi panas dan membingungkan"),
  P("Parkir punya dua wajah. Di satu sisi, parkir adalah aspek yang paling banyak dipuji karena luas (15 kutipan positif bertanda ‘luas’), rapi, dan aman. Di sisi lain, porsi keluhannya naik dari 44% di masa awal menjadi 67% di periode terkini. Keluhan yang muncul dapat dikelompokkan menjadi lima:"),
  ...bernomor([
    "**Panas dan tanpa atap**, terutama parkir motor. Ada pengulas yang menyebut lahan yang luas percuma kalau panas dan kehujanan.",
    "**Kapasitas kurang saat ramai.** Ada yang mencari parkir selama 40 menit saat ada tamu VIP. Data resmi menunjukkan kapasitas parkir mobil di Tegalluar hanya 95 lot, jauh di bawah Stasiun Halim yang menyediakan 630 lot.",
    "**Alur drop-off.** Tidak ada jalur keluar khusus bagi pengantar, sehingga mobil yang hanya menurunkan penumpang harus lewat gerbang parkir dan membayar. Pintu dekat area kedatangan ditutup, papan penunjuk tempat jemput tidak jelas, dan zona drop-off dipakai untuk parkir.",
    "**Tarif parkir inap.** Pengulas melaporkan parkir beberapa hari tetap dihitung per jam. Ada yang menyebut biaya tiga malam setara tiket Whoosh, dan ada yang merasa informasi di situs tidak sesuai dengan yang ditagih.",
    "**Operasional.** Gerbang parkir sering bermasalah, tidak ada pintu keluar khusus motor, dan mobil berpelat khusus parkir sembarangan. Cara bayar juga membingungkan: ada yang mengeluh hampir tidak bisa bayar tunai, ada juga yang mengeluh hanya bisa tunai. Beberapa pengulas meminta pengelola parkir diganti.",
  ]),
  ...kutipan("Lahan parkirnya luas, percuma kalau panas dan kehujanan.", "periode terkini", "Parkiran nya percuma luas tapi panas, dan kehujanan"),
  ...kutipan("Mengantar saja tidak ada jalur keluar, akhirnya lewat parkir dan bayar Rp3.000 padahal tidak parkir sama sekali.", "periode terkini", "drop off gak ada jalur keluar/puter balik khusus, alhasil lewat parkir bayar 3rb padahal GK parkir sama sekali lewat doang"),
  kotak("konteks", "Konteks: tarif resmi vs pengalaman pengguna", [
    "Menurut pengumuman dan pemberitaan, parkir di Tegalluar sudah berbayar sejak paling lambat Januari 2024, **dengan batas biaya maksimal harian**: Rp30.000 untuk mobil, dan untuk motor Rp30.000 (Januari 2024) lalu Rp15.000 (2025). Pembayarannya memakai uang elektronik. Pujian ‘parkir gratis’ di ulasan masa awal kemungkinan berasal dari masa uji coba September–Oktober 2023.",
    "Laporan pengulas bahwa batas maksimal ‘dihapus’ bertentangan dengan informasi resmi. Bisa jadi pelaksanaan di lapangan pernah berbeda, atau pengulas salah paham karena batas maksimal berlaku per hari sehingga menginap tiga hari tetap dikenai tiga kali biaya maksimal. Apa pun penyebabnya, keluhan ini menunjukkan bahwa **informasi tarif belum tersampaikan dengan jelas**. Hal ini perlu dikonfirmasi ke pengelola.",
  ]),
  P("Keluhan parkir memberi dampak kedua terbesar terhadap bintang: ulasan yang mengeluhkan parkir rata-rata **1,3 bintang lebih rendah**."),

  H2("5.4 Angkutan umum lanjutan: “stasiun elit, angkutan sulit”"),
  P("Aspek konektivitas umum merekam penilaian yang tidak menyebut moda tertentu, dan 78% di antaranya negatif. Keluhannya konsisten: **tidak ada angkot atau trayek angkutan umum reguler** yang singgah di stasiun. Pilihan praktisnya hanya bus DAMRI, shuttle, taksi, ojek daring, atau kendaraan pribadi. Seorang pengulas menyarankan orang lain menyisihkan waktu dua jam lebih bila memakai angkutan umum, meskipun tujuannya masih di dalam kota. Pengulas lain merasa terpaksa selalu bergantung pada mobil pribadi atau taksi."),
  ...kutipan("Stasiun elit, angkutan sulit.", "masa awal", "Stasiun elit, angkutan sulit"),
  ...kutipan("Transportasi keluar dari sini sulit.", "periode terkini", "Transportasi ke luar sulit"),
  ...kutipan("Transportasi umum minim.", "periode terkini", "Minim transportasi umum."),
  P("Beberapa permintaan cukup spesifik. Ada yang meminta **rute ke Jatinangor**, yang disebut “urgent banget” karena kawasan kampus tersebut dekat tetapi tidak terlayani. Ada juga yang meminta papan petunjuk di dalam stasiun ke arah tempat mencari taksi atau angkutan. Ulasan dengan dukungan tinggi (15 suka) meminta kebijakan agar transportasi publik dari dan ke stasiun dipermudah. Sebagai alternatif, pengelola pernah menyarankan Commuter Line Bandung Raya ke Stasiun Cimekar lalu disambung ojek, tetapi jarak dari Cimekar juga termasuk yang dikeluhkan."),

  H2("5.5 Bus DAMRI dan shuttle: disukai, tetapi terbatas"),
  P("Feeder/bus adalah aspek dengan nada paling tenang: 60% penyebutan netral dan hanya 13% negatif. Kebanyakan pengulas sekadar memberi tahu pembaca bahwa layanan ini ada, dan itu menunjukkan layanan ini menjadi pengetahuan penting bagi calon penumpang. Yang dikenal pengguna adalah **bus DAMRI ke pusat kota** (Alun-Alun, Braga, Stasiun Bandung) seharga sekitar Rp15.000 dengan waktu tempuh 60–75 menit, serta **shuttle ke Summarecon Mall Bandung dan Masjid Al Jabbar**."),
  P("Keluhan yang ada menyangkut keterbatasan: rute yang dianggap sempit, permintaan agar armada ditambah, dan **jadwal DAMRI yang tidak selaras dengan kedatangan kereta** sehingga penumpang harus menunggu lama. Keluhan jadwal ini masuk akal jika melihat data awal operasi, ketika DAMRI hanya berangkat tujuh kali sehari dari Tegalluar."),
  ...kutipan("Hanya dengan Rp15 ribu bisa naik DAMRI ke Alun-Alun Bandung.", "masa awal", "Hanya dengan 15 ribu rupiah Anda bisa naik bus Damri ke Alun-Alun Bandung."),
  ...kutipan("Ada bus DAMRI juga, tapi jadwalnya tidak sesuai dengan jadwal Whoosh, jadi harus menunggu lama.", "masa awal", "Ada bus DAMRI juga jadual nya gak sesuai dg jadual whoosh jd kudu nunggu lama."),

  H2("5.6 Efek Padalarang: pembanding yang merugikan Tegalluar"),
  P("Padalarang adalah stasiun Whoosh lain di sisi Bandung. Aspek ini disebut positif dalam 12 dari 18 penyebutan, dan **5 dari 6 penyebutan terbaru**. Alasannya selalu sama: di Padalarang tersedia **kereta penghubung (KA Feeder) gratis bagi penumpang Whoosh**, yang langsung menuju Stasiun Bandung di pusat kota dalam sekitar 20 menit dan jadwalnya selaras dengan kedatangan kereta cepat. Banyak pengulas menyarankan orang lain turun di Padalarang bila tujuannya pusat kota."),
  ...kutipan("Lebih baik turun di Padalarang lalu naik kereta feeder yang gratis khusus penumpang Whoosh.", "periode terkini", "lebih baik turun di St. Padalarang lalu naik KA Feeder yang gratis hanya untuk penumpang Whoosh saja."),
  P("Efek ini juga memunculkan masalah informasi. Seorang pengulas membeli tiket tujuan Tegalluar dan baru tahu belakangan bahwa kereta penghubung hanya tersedia dari Padalarang, sehingga ia harus naik bus. Ia berpesan agar orang lain membeli tiket tujuan Padalarang. Di sisi lain, ada juga pengulas yang merasa Tegalluar lebih nyaman karena penjemputannya lebih cepat dan tidak serawan macet Padalarang."),

  H2("5.7 Ojek daring dan ojek pangkalan: dari konflik ke soal harga"),
  P("Di masa awal operasi, inilah keluhan yang paling keras. Ceritanya konsisten di puluhan ulasan: pengemudi ojek daring **dilarang menjemput** di stasiun oleh ojek pangkalan, dicegat, diteriaki, bahkan diancam. Penumpang dipaksa beralih ke ojek pangkalan, beberapa menyebut ada pungutan uang, dan akibatnya pengemudi ojek daring enggan menerima pesanan ke atau dari stasiun. Seorang pengulas bahkan dicegat ketika hanya menjemput saudaranya dengan kendaraan sendiri. Keluhan ini paling banyak didukung pembaca: hampir semua ulasan dengan ‘suka’ terbanyak (hingga 17) membahas hal ini."),
  ...kutipan("Pengemudi ojol saya dimarahi dan diancam sampai hampir dipukul oleh ojek yang mangkal di situ, seperti preman.", "masa awal", "si bapak ojol nya dimarahin diancam sampe mau dipukul sama ojek yang mangkal disitu,kaya preman maksa"),
  kotak("kini", "Kondisi sekarang", [
    "Keluhan terhadap ojek pangkalan **tidak muncul sama sekali** sejak periode menengah (24 ulasan di masa awal, lalu 0 dan 0). Penyebutan ojek daring juga turun dari 39 menjadi 3. Keluhan ojek daring yang tersisa di periode terkini berbeda jenis: tarif yang lebih mahal dari aplikasi, menunggu 15–20 menit untuk mendapat harga normal lalu dibatalkan, dan pengemudi yang dinilai tidak kompeten. Sementara itu, pengulas terkini juga menyebut area tunggu kendaraan daring yang luas dan rapi, serta semua penyedia aplikasi bisa dipesan.",
  ]),
  kotak("konteks", "Konteks: dari insiden ke area jemput resmi", [
    "Media melaporkan pengguna ojek daring dipalak Rp10.000 dan dilarang lewat oleh ojek pangkalan di Jalan Cimencrang pada 27 Oktober 2023. Lokasi ini persis yang diperingatkan pengulas (“Jangan pernah kesini lewat jalan cimencrang, soekarno hatta pake ojek online”). Pada Februari 2024, pengelola mengumumkan penyiapan **area pick-up khusus transportasi daring** bersama operator aplikasi. Urutan waktunya cocok dengan meredanya keluhan, tetapi belum ada pemberitaan yang memastikan konflik sudah selesai. Jumlah ulasan terbaru juga lebih sedikit, sehingga kondisi ini perlu dicek di lapangan.",
  ]),

  H2("5.8 Taksi: tersedia, jarang dikeluhkan"),
  P("Taksi disebut 16 kali, dan 69% di antaranya netral. Pengulas mencatat adanya antrean taksi Bluebird di area kedatangan dan bahwa semua penyedia bisa dipesan. Keluhan hanya dua: taksi yang menolak penumpang saat banjir, dan pengalaman merasa dipaksa naik taksi lalu diputar-putar rutenya."),

  H2("5.9 Informasi dan petunjuk arah: masalah yang ada di semua tema"),
  P("Kekurangan informasi tidak berdiri sebagai satu aspek, tetapi muncul di hampir setiap tema. Contohnya:"),
  ...bullets([
    "papan penunjuk arah di jalan raya menuju stasiun, yang diminta pengulas dari berbagai arah;",
    "rute di peta digital yang menyesatkan;",
    "papan penunjuk tempat jemput di area drop-off dan arah keluar ke tempat taksi atau angkutan;",
    "informasi tarif parkir inap yang dirasa tidak sesuai;",
    "informasi bahwa kereta penghubung gratis hanya tersedia bagi penumpang bertiket Padalarang.",
  ]),
  P("Ini temuan yang penting secara praktis. Perbaikannya relatif murah dan cepat, tetapi menyentuh banyak keluhan sekaligus."),

  H2("5.10 Pengelola yang diam"),
  P("Tidak satu pun dari 1.191 ulasan di kelima listing pernah dibalas pemilik atau pengelola. Ini termasuk keluhan dengan dukungan tinggi dan pertanyaan praktis dari calon penumpang, misalnya apakah ada tempat parkir untuk ditinggal beberapa hari. Membalas ulasan, sekadar untuk memberi informasi rute, tarif, atau tindak lanjut, adalah langkah paling murah untuk memperbaiki persepsi."),
);

// ================================================================== 6. PEMICU KETIDAKPUASAN
tambah(
  H1("6. Apa yang Paling Menurunkan Kepuasan"),
  P("Tidak semua keluhan sama beratnya. Bab ini melihat tiga ukuran: seberapa besar sebuah keluhan menurunkan bintang, apa isi ulasan bintang 1–2, dan keluhan mana yang paling banyak didukung pembaca lain."),
  H2("6.1 Keluhan dan penurunan bintang"),
  P("Grafik di bawah membandingkan rata-rata bintang ulasan yang memuat suatu keluhan atau pujian dengan ulasan yang tidak memuatnya, setelah memperhitungkan aspek-aspek lain dalam ulasan yang sama. Titik di kiri garis nol berarti menurunkan bintang. Garis horizontal menunjukkan rentang ketidakpastian."),
  ...gambar("04_ols_rating.png", "Perubahan bintang yang berkaitan dengan setiap kombinasi aspek dan sentimen. Hanya kombinasi dengan minimal 5 ulasan yang ditampilkan.", 500),
  ...tabel("Keluhan yang paling menurunkan bintang", ["Keluhan", "Selisih bintang", "Rentang ketidakpastian", "Jumlah ulasan"], [
    ["Angkot/opang", "−1,7", "−2,6 s.d. −0,8", "23"], ["Parkir & antar-jemput", "−1,3", "−1,9 s.d. −0,6", "33"],
    ["Akses jalan & macet", "−0,9", "−1,4 s.d. −0,5", "46"], ["Konektivitas umum", "−0,6", "−1,1 s.d. −0,1", "38"],
    ["Ojol", "−0,3", "−1,2 s.d. +0,6 (tidak pasti)", "29"], ["Jarak & lokasi", "+0,2", "−0,1 s.d. +0,5 (tidak pasti)", "36"],
  ], [3000, 1800, 2860, 1700], "Angka ini menunjukkan keterkaitan, bukan sebab-akibat. Keluhan ojol dan opang sering muncul bersamaan, sehingga dampak masing-masing sulit dipisahkan."),
  P("Dua hal menonjol. **Parkir dan akses jalan**, yang keduanya masih dominan sekarang, termasuk keluhan dengan dampak besar terhadap bintang. Sebaliknya, **keluhan jarak tidak menurunkan bintang**. Satu-satunya pujian yang jelas menaikkan bintang juga datang dari aspek jarak (+0,3), yaitu ketika pengulas merasa letaknya dekat."),
  H2("6.2 Isi ulasan bintang 1–2"),
  ...tabel("Keluhan konektivitas dalam 71 ulasan bintang 1–2 bertekstual", ["Keluhan", "Jumlah ulasan", "% dari ulasan bintang 1–2"], [
    ["Angkot/opang", "14", "20%"], ["Parkir & antar-jemput", "14", "20%"], ["Akses jalan & macet", "13", "18%"],
    ["Ojol", "13", "18%"], ["Konektivitas umum", "9", "13%"], ["Feeder/bus", "2", "3%"], ["Jarak & lokasi", "2", "3%"],
  ], [4400, 2200, 2760], "Satu ulasan bisa memuat lebih dari satu keluhan."),
  P("Jarak & lokasi, yang paling sering dibahas, hanya muncul di 2 ulasan bintang 1–2. Yang membuat pengguna sangat kecewa adalah pengalaman konkret: dihadang ojek pangkalan, kesulitan parkir, atau terjebak di jalan."),
  H2("6.3 Keluhan yang paling didukung pembaca lain"),
  P("Google Maps memungkinkan pembaca menekan ‘suka’ pada ulasan yang mereka anggap membantu. Jumlahnya kecil (hanya 79 dari 673 ulasan bertekstual yang punya minimal satu suka, maksimal 17), tetapi tetap menunjukkan keluhan mana yang dirasakan banyak orang. Ketika net sentiment dihitung ulang dengan memberi bobot lebih pada ulasan yang banyak disukai, nilai **ojol memburuk dari −50 menjadi −83** dan konektivitas umum dari −59 menjadi −75. Sebaliknya, parkir membaik dari −20 menjadi −5, karena keluhan parkir umumnya tidak banyak disukai. Tujuh dari delapan ulasan negatif dengan suka terbanyak membahas larangan ojek daring atau perilaku ojek pangkalan."),
  H2("6.4 Ulasan berfoto lebih jarang mengeluh"),
  P("Di antara ulasan konektivitas, yang menyertakan foto lebih jarang berisi keluhan (65%) dibanding yang tanpa foto (74%), dan bintangnya lebih tinggi (4,4 dibanding 3,5). Kemungkinan besar pengulas berfoto lebih sering menulis ulasan wisata atau dokumentasi, sedangkan ulasan tanpa foto lebih sering ditulis setelah pengalaman buruk."),
);

// ================================================================== 7. POLA LAIN
tambah(
  H1("7. Pola Lain yang Perlu Diketahui"),
  H2("7.1 Keluhan yang datang bersamaan"),
  P("Satu ulasan sering menyebut lebih dari satu aspek. Sebanyak 60% ulasan konektivitas hanya membahas satu aspek, 22% membahas dua, dan sisanya tiga atau lebih. Pasangan yang paling sering muncul bersama menunjukkan bagaimana pengguna memandang masalahnya sebagai satu rangkaian."),
  ...gambar("08_kookurensi_aspek.png", "Jumlah ulasan yang membahas dua aspek sekaligus. Angka dalam kurung di diagonal adalah total ulasan per aspek.", 520),
  ...bullets([
    "**Ojol dan angkot/opang (19 ulasan, 18 di antaranya sama-sama keluhan).** Keduanya adalah dua sisi dari satu konflik yang sama.",
    "**Akses jalan dan jarak & lokasi (18 ulasan).** Jarak terasa jauh karena jalannya buruk dan macet. Ini menguatkan temuan bahwa yang dikeluhkan adalah cara menempuh jarak, bukan jaraknya sendiri.",
    "**Feeder/bus dan konektivitas umum (16 ulasan, hanya 3 sama-sama keluhan).** Pengulas sering menyebut DAMRI sebagai satu-satunya pilihan sambil menilai angkutan secara umum masih minim.",
  ]),
  H2("7.2 Jenis masalah yang paling sering disebut"),
  P("Setiap kutipan diberi label jenis masalah. Peta di bawah memperlihatkan jenis masalah yang dominan di setiap aspek."),
  ...gambar("06_heatmap_aspek_tag.png", "Jumlah kutipan per aspek dan jenis masalah. Makin gelap warna, makin sering disebut."),
  P("Pola yang paling tegas adalah **akses jalan buruk** (50 kutipan) dan **macet** (21) pada aspek jalan, **lokasi jauh** (39) pada aspek jarak, **tidak tersedia** pada konektivitas umum (22) dan ojol (16), serta **konflik opang** (37 kutipan di aspek ojol dan opang). Pada aspek parkir, label terbanyak adalah ‘lainnya’ (27). Ini menunjukkan keluhan parkir sangat beragam: panas, gerbang, cara bayar, dan alur drop-off."),
  H2("7.3 Moda yang dibahas pengguna"),
  P("Ulasan tidak dirancang untuk mengukur cara orang datang ke stasiun. Meski begitu, moda yang disebut memberi gambaran kasar tentang pengalaman yang paling sering dialami."),
  ...tabel("Moda yang disebut dalam ulasan konektivitas", ["Moda", "Ulasan", "% ulasan konektivitas", "Positif", "Negatif", "Netral"], [
    ["Kendaraan pribadi / antar-jemput", "65", "28%", "20", "33", "4"], ["Ojek atau mobil daring", "44", "19%", "7", "29", "8"],
    ["Bus DAMRI / shuttle", "40", "17%", "11", "5", "24"], ["Angkot / ojek pangkalan", "24", "10%", "0", "23", "1"],
    ["Kereta penghubung via Padalarang", "18", "8%", "12", "4", "2"], ["Taksi", "16", "7%", "3", "2", "11"],
  ], [3300, 1100, 1700, 1080, 1080, 1100], "Kolom sentimen tidak mencakup kategori campuran (parkir: 8)."),
  P("Kendaraan pribadi paling sering disebut. Ini sejalan dengan tidak adanya angkutan umum reguler: pengguna yang punya pilihan cenderung membawa kendaraan sendiri atau diantar, sehingga parkir dan jalan menjadi pengalaman yang paling banyak dirasakan."),
  H2("7.4 Apa yang diminta pengguna"),
  P("Sebanyak 30 kutipan berisi permintaan atau saran eksplisit, misalnya yang diawali kata ‘tolong’, ‘perlu’, ‘semoga’, atau ‘sebaiknya’. Permintaan terbanyak menyangkut akses jalan (8), konektivitas umum (8), dan parkir (7). Isinya konkret:"),
  ...bullets([
    "**Jalan:** buat akses jalan yang layak, perlebar jalan, tambah lampu, pasang petunjuk arah, dan buka akses tol langsung.",
    "**Angkutan:** tambah moda lanjutan seperti bus, perbanyak armada feeder, dan tingkatkan sarana ke pusat kota.",
    "**Parkir:** perluas lahan, tambah atap untuk parkir motor, pasang pembatas ban, dan ganti pengelola parkir.",
    "**Ojek daring:** berhati-hati terhadap tarif yang ditembak pengemudi.",
  ]),
  H2("7.5 Tema yang ditemukan secara otomatis"),
  P("Sebagai pemeriksaan silang, 276 kutipan keluhan dikelompokkan ulang secara otomatis berdasarkan kemiripan isinya, tanpa memakai sepuluh aspek di atas. Hasilnya 14 kelompok tema, dan hampir semuanya sejalan dengan aspek yang sudah ada: konflik ojek, parkir, minimnya angkutan umum, jarak ke pusat kota, kemacetan, jalan kecil, dan permintaan akses yang layak. Satu tema yang tidak tercakup secara khusus oleh aspek mana pun adalah **jarak dari Stasiun Cimekar**, stasiun kereta lokal terdekat. Beberapa pengulas menyebut Cimekar sebagai sambungan yang seharusnya bisa dipakai tetapi terlalu jauh."),
  H2("7.6 Perbedaan antar-listing dan antar-bahasa"),
  P("Listing “Stasiun Kereta Cepat Tegalluar” menampung lebih dari separuh penyebutan konektivitas (253 dari 392). Di listing ini, keluhan konektivitas umum (81% negatif) dan ojek pangkalan (96%) paling terkonsentrasi. Listing “Parkir Timur” hampir seluruhnya berisi keluhan parkir. Listing lain terlalu kecil untuk dibandingkan secara berarti. Ulasan berbahasa Inggris memiliki porsi keluhan yang setara dengan ulasan berbahasa Indonesia (53% dan 56%). Jadi pengunjung asing mengalami masalah yang sama, terutama soal jarak dan jalan."),
  H2("7.7 Perubahan persentase keluhan dari waktu ke waktu"),
  P("Grafik terakhir menunjukkan persentase keluhan per periode untuk aspek yang datanya cukup. Garis yang terputus berarti data pada periode itu terlalu sedikit untuk ditampilkan."),
  ...gambar("03_tren_negatif.png", "Persentase penyebutan negatif per periode untuk empat aspek dengan data cukup, beserta rentang ketidakpastiannya."),
  P("Parkir naik dari 44% ke 67%. Jarak & lokasi turun dari 57% ke 38%. Akses jalan tetap di sekitar 74%. Konektivitas umum turun dari 83% ke 67% di periode menengah. Karena rentang ketidakpastiannya masih lebar, arah perubahan ini sebaiknya dibaca sebagai kecenderungan, bukan kepastian."),
);

// ================================================================== 8. KONTEKS KEBIJAKAN
tambah(
  H1("8. Konteks Kebijakan"),
  P("Untuk memahami mengapa kondisinya seperti sekarang, temuan dari ulasan dicocokkan dengan pengumuman resmi pengelola dan pemberitaan media. Tabel berikut merangkum peristiwa yang paling relevan dengan kondisi saat ini. Daftar lengkapnya (16 peristiwa beserta sumbernya) ada di Lampiran E."),
  ...tabel("Peristiwa penting terkait konektivitas", ["Waktu", "Peristiwa", "Kaitan dengan kondisi sekarang"], [
    ["Sep–Okt 2023", "Uji coba publik; shuttle DAMRI dan Summarecon gratis. Operasi komersial mulai 17 Oktober 2023.", "Menjelaskan pujian ‘gratis’ di ulasan masa awal"],
    ["18 Okt 2023", "KA Feeder Padalarang–Bandung beroperasi, gratis bagi penumpang Whoosh", "Akar ‘efek Padalarang’ yang masih terasa sampai sekarang"],
    ["23 Okt 2023", "DAMRI Tegalluar–Kota Bandung Rp10.000, 7 keberangkatan per hari", "Menjelaskan keluhan jadwal tidak selaras"],
    ["27 Okt 2023", "Insiden ojol dipalak ojek pangkalan di Jl. Cimencrang", "Puncak konflik yang kini tidak lagi muncul"],
    ["Des 2023–Jan 2024", "Jam exit tol KM 149 diperpanjang hanya untuk masa liburan, lalu exit ditutup untuk perbaikan", "Akses tol yang tidak pasti, keluhan yang masih ada"],
    ["Jan 2024", "Parkir berbayar dengan batas maksimal harian, pembayaran nontunai", "Dasar keluhan tarif dan cara bayar"],
    ["Feb 2024", "Pengelola menyiapkan area pick-up khusus transportasi daring", "Bertepatan dengan meredanya konflik ojek"],
    ["Agu 2024", "Nama berganti menjadi Stasiun Tegalluar Summarecon; kerja sama mencakup akses dan shuttle", "Latar shuttle ke Summarecon"],
    ["Okt 2024", "DAMRI rute Trans Studio Mall–Tegalluar Rp15.000", "Tarif yang disebut pengulas saat ini"],
    ["Des 2024", "Akses tol KM 149 A dan KM 151 A dibuka sementara untuk masa liburan", "Akses tol masih belum permanen"],
    ["Jun 2025–Apr 2026", "Layanan parkir inap diresmikan; tarif mobil maks. Rp30.000 per hari; kapasitas 95 lot mobil", "Menjelaskan keluhan kapasitas; tarif resmi berbeda dengan yang dilaporkan pengulas"],
  ], [1600, 4200, 3560]),
  P("Dari pencocokan ini, masalah masa awal dapat dibedakan dari masalah struktural. **Masalah masa peluncuran**, seperti konflik ojek, penyesuaian rute DAMRI, dan kebingungan masa uji coba, sebagian besar sudah mereda. **Masalah struktural** tetap dikeluhkan meskipun sudah ada intervensi, yaitu akses jalan dan tol yang belum permanen, kapasitas parkir yang kecil, dan tidak adanya angkutan umum reguler. Masalah struktural inilah yang membentuk fenomena saat ini."),
  kotak("catatan", "Batas penafsiran", [
    "Kecocokan waktu antara peristiwa dan perubahan isi ulasan tidak membuktikan sebab-akibat. Tanggal ulasan hanya perkiraan kasar, sehingga pencocokan dilakukan per periode, bukan per tanggal.",
  ]),
);

// ================================================================== 9. REKOMENDASI
tambah(
  H1("9. Rekomendasi"),
  P("Rekomendasi berikut diturunkan langsung dari keluhan dan permintaan pengguna. Urutannya mempertimbangkan dua hal: seberapa besar keluhan yang dijawab, dan seberapa cepat langkahnya bisa dilakukan."),
  ...tabel("Rekomendasi perbaikan", ["#", "Masalah", "Langkah yang disarankan", "Pihak terkait", "Waktu"], [
    ["1", "Petunjuk arah dan informasi kurang", "Papan arah di jalan utama dan di dalam stasiun, perbaikan rute di peta digital, informasi rute resmi di situs dan aplikasi", "Pengelola stasiun, Dishub, penyedia peta", "Cepat"],
    ["2", "Tarif parkir inap dan alur drop-off", "Pastikan batas maksimal harian diterapkan dan diumumkan, dengan contoh biaya 1–3 malam; jalur drop-off terpisah dengan waktu gratis singkat", "Pengelola stasiun, operator parkir", "Cepat"],
    ["3", "Pengelola tidak menanggapi ulasan", "Balas keluhan dengan informasi rute, tarif, dan tindak lanjut", "Pengelola stasiun", "Cepat"],
    ["4", "Zona ojek daring dan sisa masalah harga", "Pertahankan zona jemput resmi untuk semua aplikasi, sediakan kanal pengaduan, dan jalin kerja sama tarif dan antrean pada jam kedatangan kereta", "Pengelola, operator aplikasi", "Cepat–menengah"],
    ["5", "Jadwal DAMRI tidak selaras", "Sesuaikan jadwal dengan kedatangan kereta, tambah frekuensi dan rute (misalnya ke Jatinangor)", "DAMRI, pengelola", "Menengah"],
    ["6", "Parkir panas dan kapasitas kecil", "Kanopi atau peneduh, terutama untuk motor; kapasitas tambahan", "Pengelola stasiun", "Menengah"],
    ["7", "Tidak ada angkutan umum reguler", "Trayek reguler ke Cibiru, Cileunyi, Gedebage, dan Jatinangor; penyambung ke Stasiun Cimekar", "Dishub Jabar, Pemkab Bandung", "Menengah–panjang"],
    ["8", "Jalan akses dan tol", "Pelebaran dan perbaikan jalan, penerangan, penanganan banjir, akses tol permanen", "Pemkab, Pemprov, pengelola tol", "Panjang"],
  ], [500, 2000, 3760, 1900, 1200]),
  P("Tiga langkah pertama hampir tidak memerlukan pembangunan fisik, tetapi menjawab keluhan yang tersebar di banyak tema. Langkah 7 dan 8 membutuhkan koordinasi lintas instansi. Namun keduanya menyasar akar masalah yang paling awet, yaitu jalan dan ketiadaan angkutan umum."),
);

// ================================================================== 10. KEKUATAN TEMUAN
tambah(
  H1("10. Seberapa Kuat Temuan Ini"),
  H2("10.1 Tingkat keyakinan per temuan"),
  ...tabel("Tingkat keyakinan", ["Temuan", "Keyakinan", "Alasan"], [
    ["Konektivitas menurunkan kepuasan", "Tinggi", "Pola bintang konsisten; 65% ulasan bintang 1–2 membahasnya"],
    ["Jalan akses adalah masalah yang awet", "Tinggi", "Keluhan spesifik dan berulang di semua periode; didukung fakta akses tol yang tidak permanen"],
    ["Konflik ojek pangkalan di masa awal", "Tinggi", "24 ulasan dengan cerita konsisten, dukungan pembaca tinggi, dikonfirmasi pemberitaan"],
    ["Topik bergeser ke jarak, jalan, dan parkir", "Sedang", "Pola jelas, tetapi ulasan periode terkini lebih sedikit (84 penyebutan)"],
    ["Konflik ojek pangkalan sudah mereda", "Sedang–rendah", "Hanya berdasarkan tidak adanya keluhan pada periode dengan ulasan lebih sedikit"],
    ["Masalah kapasitas dan tarif parkir", "Sedang", "Didukung data kapasitas resmi; laporan tarif bertentangan dengan informasi resmi"],
    ["Lokasi menguntungkan warga Bandung timur", "Sedang", "Disebut berulang, tetapi hanya oleh pengulas yang tinggal di sana"],
    ["Jadwal DAMRI tidak selaras", "Rendah", "Hanya 1–2 ulasan, meski didukung data jadwal awal"],
  ], [3300, 1500, 4560]),
  H2("10.2 Keterbatasan"),
  P("**Penandaan oleh AI tanpa pemeriksaan manusia.** Setiap ulasan ditandai oleh model AI dalam dua putaran terpisah. Kedua putaran sangat konsisten satu sama lain (kesepakatan 99% untuk relevansi dan 94% untuk sentimen), tetapi keduanya berasal dari model yang sama. Konsistensi ini tidak menjamin penandaan itu benar menurut penilaian manusia. Sampel 122 ulasan sudah disiapkan untuk pemeriksaan manual, tetapi belum dikerjakan oleh manusia. Ini keterbatasan terbesar kajian ini."),
  P("**Tanggal yang kasar.** Sebanyak 74% ulasan konektivitas hanya bertanggal “setahun lalu” atau “2 tahun lalu”. Perubahan dari waktu ke waktu hanya bisa dilihat dalam tiga periode, dan pencocokan dengan peristiwa kebijakan tidak bisa dilakukan per tanggal."),
  P("**Siapa yang menulis ulasan.** Pengulas Google Maps cenderung pengguna yang melek digital, dan lebih sering menulis setelah pengalaman yang sangat baik atau sangat buruk. Pengalaman penumpang rutin atau yang tidak menulis ulasan tidak terwakili."),
  P("**Jumlah per aspek kecil.** Sebagian besar aspek memiliki kurang dari 75 penyebutan, dan beberapa di bawah 20. Perbandingan antar-listing, antar-bahasa, atau antar-periode karena itu harus dibaca hati-hati."),
  P("**Satu sumber, satu stasiun.** Tanpa pembanding dengan stasiun Whoosh lain (Halim, Karawang, Padalarang), belum bisa dipastikan apakah tingkat keluhan di Tegalluar lebih tinggi dari stasiun lain atau wajar untuk stasiun kereta cepat."),
  H2("10.3 Saran untuk riset lanjutan"),
  ...bernomor([
    "**Pemeriksaan manual 100–120 ulasan** oleh dua orang, menggunakan sampel yang sudah disiapkan. Hasilnya akan menunjukkan seberapa akurat penandaan AI dan membuat angka-angka dalam laporan ini dapat dipertanggungjawabkan secara ilmiah.",
    "**Perbandingan dengan stasiun Whoosh lain** dengan cara yang sama, untuk melihat apakah masalah ini khas Tegalluar.",
    "**Pengambilan ulasan berkala**, misalnya setiap bulan, agar tanggal ulasan baru bisa diketahui dengan tepat.",
    "**Konfirmasi lapangan** atas tiga dugaan: apakah konflik ojek pangkalan benar-benar selesai, bagaimana praktik tarif parkir inap, dan bagaimana status akses tol saat ini.",
    "**Survei atau wawancara penumpang** untuk menjangkau pengguna yang tidak menulis ulasan dan mengukur pilihan moda secara langsung.",
  ]),
);

// ================================================================== LAMPIRAN
tambah(
  H1("Lampiran A. Tabel Lengkap per Aspek"),
  ...tabel("Jumlah dan persentase sentimen per aspek (seluruh periode)", ["Aspek", "Total", "Neg", "Camp", "Net", "Pos", "% Neg", "% Pos", "Net sent.", "Porsi"], [
    ["Jarak & lokasi", "73", "36", "2", "15", "20", "49,3", "27,4", "−21,9", "18,6%"],
    ["Parkir & antar-jemput", "65", "33", "8", "4", "20", "50,8", "30,8", "−20,0", "16,6%"],
    ["Akses jalan & macet", "61", "46", "1", "6", "8", "75,4", "13,1", "−62,3", "15,6%"],
    ["Konektivitas umum", "49", "38", "0", "2", "9", "77,6", "18,4", "−59,2", "12,5%"],
    ["Ojol", "44", "29", "0", "8", "7", "65,9", "15,9", "−50,0", "11,2%"],
    ["Feeder/bus", "40", "5", "0", "24", "11", "12,5", "27,5", "+15,0", "10,2%"],
    ["Angkot/opang", "24", "23", "0", "1", "0", "95,8", "0,0", "−95,8", "6,1%"],
    ["Padalarang (KA feeder)", "18", "4", "0", "2", "12", "22,2", "66,7", "+44,4", "4,6%"],
    ["Taksi", "16", "2", "0", "11", "3", "12,5", "18,8", "+6,2", "4,1%"],
    ["Integrasi jadwal", "2", "2", "0", "0", "0", "100", "0,0", "−100", "0,5%"],
    ["**Semua aspek**", "**392**", "**218**", "**11**", "**73**", "**90**", "**55,6**", "**23,0**", "**−32,7**", "100%"],
  ], [2300, 700, 700, 700, 700, 700, 800, 800, 960, 800], "Neg = negatif, Camp = campuran, Net = netral, Pos = positif. Porsi = bagian dari seluruh penyebutan."),
  ...tabel("Penyebutan per aspek pada periode terkini (11 bulan terakhir)", ["Aspek", "Penyebutan", "Negatif", "Positif", "Netral/campuran"], [
    ["Jarak & lokasi", "26", "10", "10", "6"], ["Akses jalan & macet", "19", "14", "4", "1"], ["Parkir & antar-jemput", "15", "10", "4", "1"],
    ["Konektivitas umum", "7", "5", "2", "0"], ["Padalarang (KA feeder)", "6", "1", "5", "0"], ["Feeder/bus", "6", "0", "1", "5"],
    ["Ojol", "3", "1", "2", "0"], ["Taksi", "2", "1", "1", "0"], ["Angkot/opang", "0", "0", "0", "0"], ["**Total**", "**84**", "**42**", "**29**", "**13**"],
  ], [3400, 1500, 1400, 1400, 1660]),

  H1("Lampiran B. Glosarium"),
  ...tabel("Istilah dalam laporan", ["Istilah", "Arti"], [
    ["Analisis sentimen berbasis aspek", "Cara membaca ulasan dengan memisahkan hal yang dibicarakan (aspek) dari penilaiannya (sentimen), sehingga satu ulasan bisa punya beberapa penilaian."],
    ["Aspek", "Hal yang dibicarakan, misalnya parkir atau ojek daring. Ada sepuluh aspek (Bab 2.4)."],
    ["Sentimen", "Nada penilaian: positif, negatif, netral (fakta tanpa penilaian), atau campuran (baik sekaligus buruk)."],
    ["Penyebutan", "Satu aspek dalam satu ulasan."],
    ["Kutipan", "Potongan kalimat dari ulasan yang menjadi bukti suatu penilaian. Total ada 447 kutipan."],
    ["Net sentiment", "Persentase positif dikurangi persentase negatif, dengan rentang −100 sampai +100."],
    ["Rentang ketidakpastian", "Jangkauan nilai yang masuk akal mengingat jumlah ulasan yang terbatas (interval kepercayaan 95%)."],
    ["First mile / last mile", "Perjalanan dari titik asal ke stasiun, dan dari stasiun ke tujuan akhir."],
    ["Opang", "Ojek pangkalan: ojek konvensional yang mangkal di satu titik."],
    ["Ojol", "Ojek atau mobil daring berbasis aplikasi."],
    ["KA Feeder", "Kereta penghubung gratis dari Stasiun Padalarang ke Stasiun Bandung bagi penumpang Whoosh."],
    ["Listing", "Satu entri tempat di Google Maps. Stasiun ini tercatat dalam lima listing."],
    ["Periode awal / menengah / terkini", "±2 tahun lalu (≈ akhir 2023–awal 2025), ±setahun lalu (≈ 2025), dan 11 bulan terakhir (Okt 2025–Sep 2026), dihitung dari 25 September 2026."],
  ], [2800, 6560]),

  H1("Lampiran C. Rincian Metode"),
  P("Bagian ini merangkum rincian teknis bagi pembaca yang membutuhkannya, misalnya untuk menulis bab metode. Dokumen metode lengkap tersedia di berkas *metodologi.md*."),
  ...bullets([
    "**Pengumpulan:** otomatisasi peramban (Playwright) pada Google Maps, 25 September 2026. Ulasan diurutkan dari yang terbaru dan diambil sampai habis. Bila Google menampilkan terjemahan, teks asli dan terjemahannya sama-sama disimpan.",
    "**Pengenalan bahasa:** gabungan dua pendeteksi bahasa (fastText dan lingua), ditambah aturan khusus untuk teks pendek, bahasa gaul, dan penanda bahasa Sunda.",
    "**Pemecahan klausa:** model pemecah kalimat multibahasa (wtpsplit SaT), lalu dipecah lagi pada kata kontras seperti ‘tapi’ dan ‘namun’. Hasilnya 1.736 klausa.",
    "**Penyaringan:** kata kunci multibahasa (sekitar 320 istilah), kemiripan makna dengan model bge-m3 menggunakan skor selisih antara kemiripan dengan topik konektivitas dan topik lain, serta kata akses tidak langsung. Sebanyak 531 ulasan lolos. Ke-142 ulasan yang tidak lolos juga ditandai untuk pengecekan, dan tidak ada yang relevan.",
    "**Penandaan:** model AI Claude (Anthropic), dua putaran independen oleh enam instans terpisah. Pelabel tidak diberi informasi bintang. Setiap kutipan harus sama persis dengan teks aslinya. Sebanyak 35 ulasan yang berbeda antar-putaran diputuskan dengan alasan tertulis. Kesepakatan antar-putaran (kappa): relevansi 0,99, aspek 0,90–1,00, sentimen 0,94.",
    "**Pembanding:** model sentimen terbuka yang umum dipakai (RoBERTa berbahasa Indonesia dan XLM-RoBERTa multibahasa) hanya mencapai kesesuaian 0,61 untuk aspek dan 0,43 untuk sentimen terhadap hasil penandaan. Model tersebut tidak memadai untuk analisis ini, terutama karena sering membaca keluhan yang disampaikan dengan sopan sebagai pujian.",
    "**Statistik:** rentang ketidakpastian dengan metode Wilson; regresi linier bintang terhadap aspek dan sentimen dengan galat baku robust (HC3), R² = 0,22; pengelompokan tema otomatis dengan BERTopic.",
    "**Perangkat:** seluruh pengolahan dijalankan di komputer lokal dengan perangkat lunak terbuka dan gratis.",
  ]),

  H1("Lampiran D. Berkas Pendukung"),
  P("Seluruh berkas berada di folder proyek *whoosh-absa*."),
  ...tabel("Daftar berkas", ["Berkas", "Isi"], [
    ["output/whoosh_absa_hasil.xlsx", "Semua tabel angka dalam satu berkas Excel (24 lembar), termasuk katalog 447 kutipan yang bisa difilter"],
    ["output/laporan_wawasan.md", "Pembahasan tematik dalam format teks"],
    ["output/linimasa_kebijakan.md", "Linimasa 16 peristiwa dan pencocokannya dengan ulasan"],
    ["output/metodologi.md", "Dokumen metode lengkap untuk keperluan akademik"],
    ["output/evaluation.md", "Hasil pemeriksaan kualitas penandaan dan model pembanding"],
    ["output/analysis_report.md, analysis_extended.md", "Laporan angka lengkap"],
    ["output/figures/", "Seluruh grafik dalam format gambar"],
    ["data/raw/all_reviews.csv", "Data ulasan mentah (tanpa identitas pengulas)"],
    ["data/processed/final_labels.csv", "Hasil penandaan per ulasan dan aspek"],
  ], [3800, 5560]),

  H1("Lampiran E. Sumber Linimasa"),
  ...tabel("Peristiwa dan sumbernya", ["Tanggal", "Peristiwa", "Sumber"], [
    ["25 Sep 2023", "Shuttle DAMRI dan Summarecon gratis selama uji coba", "Kompas"],
    ["17 Okt 2023", "Operasi komersial Whoosh", "Siaran pers KCIC"],
    ["18 Okt 2023", "KA Feeder Padalarang–Bandung gratis mulai beroperasi", "Kompas, CNBC Indonesia"],
    ["23 Okt 2023", "DAMRI Tegalluar–Kota Bandung Rp10.000, 7 keberangkatan per hari", "Kompas TV"],
    ["27 Okt 2023", "DAMRI Tegalluar–Stasiun KA Bandung", "Kompas"],
    ["27 Okt 2023", "Insiden ojol dipalak ojek pangkalan di Jl. Cimencrang", "PRFM News"],
    ["23 Des 2023", "Jam exit tol KM 149 diperpanjang (masa Nataru)", "Siaran pers KCIC"],
    ["1 Jan 2024", "Exit tol KM 149 ditutup sementara untuk perbaikan jembatan", "Kompas, siaran pers KCIC"],
    ["9 Jan 2024", "Tarif parkir dengan batas maksimal; pembayaran nontunai", "Kompas"],
    ["19–20 Feb 2024", "Area pick-up khusus transportasi daring disiapkan", "Kontan, PRFM News"],
    ["28 Agu 2024", "Nama berganti menjadi Stasiun Tegalluar Summarecon", "Siaran pers KCIC, RRI"],
    ["22 Okt 2024", "DAMRI Trans Studio Mall–Tegalluar Rp15.000", "Kompas"],
    ["28 Des 2024", "Akses tol KM 149 A dan KM 151 A dibuka sementara", "Siaran pers KCIC"],
    ["7 Jun 2025", "Layanan parkir inap di seluruh stasiun Whoosh", "Siaran pers KCIC"],
    ["30 Okt 2025", "Tarif parkir Tegalluar; kapasitas 95 lot mobil", "detikNews"],
    ["7 Apr 2026", "Tarif parkir Tegalluar tidak berubah", "UlasBandung"],
  ], [1700, 5160, 2500], "Tautan lengkap setiap sumber tercantum di berkas output/linimasa_kebijakan.md dan config/events.csv."),

  H1("Lampiran F. Sumber Data Google Maps"),
  P("Seluruh ulasan dalam laporan ini berasal dari lima listing Google Maps berikut. Listing diambil pada 25 September 2026, dengan tampilan berbahasa Indonesia dan urutan ‘Terbaru’. Untuk memeriksa sendiri, buka tautan lalu pilih tab *Ulasan*. Jumlah ulasan yang tampil sekarang bisa berbeda karena ulasan baru terus bertambah."),
  ...tabel("Listing Google Maps yang dianalisis", ["#", "Nama listing", "Tautan", "Ulasan"], [
    ["1", "Stasiun Kereta Cepat Tegalluar", "[[https://maps.app.goo.gl/RVeUwckH69V2AXit8|https://maps.app.goo.gl/RVeUwckH69V2AXit8]]", "416"],
    ["2", "Kereta Cepat Whoosh Tegalluar", "[[https://maps.app.goo.gl/qSH4xZkqkBoF3FzP7|https://maps.app.goo.gl/qSH4xZkqkBoF3FzP7]]", "663"],
    ["3", "Stasiun KCJB Tegalluar", "[[https://maps.app.goo.gl/tWh3hbaB6Ypk5Zqt5|https://maps.app.goo.gl/tWh3hbaB6Ypk5Zqt5]]", "17"],
    ["4", "Tegalluar Summarecon", "[[https://maps.app.goo.gl/sT2KabtsJ7ywaAQY9|https://maps.app.goo.gl/sT2KabtsJ7ywaAQY9]]", "72"],
    ["5", "Parkir Timur Stasiun Kereta Cepat Tegalluar", "[[https://maps.app.goo.gl/vddqzKDfdVzJMnEh7|https://maps.app.goo.gl/vddqzKDfdVzJMnEh7]]", "23"],
  ], [500, 3300, 4560, 1000]),
  ...tabel("Titik lokasi dan identitas tempat di Google", ["#", "Nama listing", "Koordinat (lintang, bujur)", "ID tempat Google"], [
    ["1", "Stasiun Kereta Cepat Tegalluar", "−6,96428; 107,71544", "0x2e68c2ffe88dd7b3:0xe4c246dd4a0c8a50"],
    ["2", "Kereta Cepat Whoosh Tegalluar", "−6,96465; 107,71477", "0x2e68c30038b3ed85:0xd23009b1cd0c30ee"],
    ["3", "Stasiun KCJB Tegalluar", "−6,96423; 107,71564", "0x2e68c2ffe7b25803:0x4e70541db036c708"],
    ["4", "Tegalluar Summarecon", "−6,96392; 107,71510", "0x2e68c2ffc1798b77:0x33f2bec3bc27506"],
    ["5", "Parkir Timur Stasiun Kereta Cepat Tegalluar", "−6,96353; 107,71626", "0x2e68c300120f2d5d:0xcc8279b2e4ddc81e"],
  ], [420, 2650, 2000, 4290], "Koordinat dan ID tempat diambil dari alamat lengkap Google Maps setelah tautan pendek dibuka. Kelima titik berjarak 23–206 meter satu sama lain, sehingga merujuk pada kompleks stasiun yang sama."),
  P("Kelima listing memiliki ID tempat yang berbeda, sehingga Google memperlakukannya sebagai lima tempat terpisah dengan kumpulan ulasan masing-masing. Pemeriksaan silang tidak menemukan ulasan yang sama muncul di lebih dari satu listing, sehingga seluruh ulasan dapat digabungkan tanpa penghitungan ganda. Listing nomor 5 (Parkir Timur) adalah area parkir di timur stasiun, sehingga ulasannya didominasi topik parkir."),
);

// ------------------------------------------------------------------ DOKUMEN
const doc = new Document({
  creator: "Analisis ABSA Whoosh Tegalluar",
  title: "Konektivitas Transportasi Stasiun Whoosh Tegalluar",
  description: "Laporan analisis ulasan Google Maps",
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: "1F1F1F" } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, color: NAVY, font: FONT },
        paragraph: { spacing: { before: 0, after: 240 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "B7D3F6", space: 6 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, color: NAVY, font: FONT }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: BIRU, font: FONT }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 460, hanging: 320 } }, run: { bold: true, color: NAVY } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, bottom: 1200, left: 1273, right: 1273 } },
      titlePage: true },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: "Konektivitas Transportasi Stasiun Whoosh Tegalluar", size: 16, color: "8F8E88" })] })] }),
      first: new Header({ children: [new Paragraph({ text: "" })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
        new TextRun({ children: ["Halaman ", PageNumber.CURRENT], size: 16, color: "8F8E88" })] })] }),
      first: new Footer({ children: [new Paragraph({ text: "" })] }),
    },
    children: isi,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("Tersimpan:", OUT, (buf.length / 1024).toFixed(0), "KB"); });
