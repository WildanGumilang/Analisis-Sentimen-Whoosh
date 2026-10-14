"""Tahap 2 — Preprocessing.

- Pisahkan review tanpa teks (tetap disimpan untuk statistik rating).
- Deteksi bahasa: ansambel fastText lid.176 + lingua-py, heuristik Sunda, flag code_mixed.
- Segmentasi klausa: wtpsplit SaT, lalu dipecah lagi di kata kontras.
- Normalisasi ringan (hanya untuk pencocokan keyword); teks asli TIDAK diubah.

Input : data/raw/all_reviews.csv
Output: data/interim/reviews_text.csv     (review bertekstual + bahasa + teks ternormalisasi)
        data/interim/reviews_no_text.csv  (review hanya rating)
        data/interim/clauses.csv          (satu baris per klausa, dengan offset karakter)

Pemakaian:
  python src/preprocess.py                     # SaT "sat-12l-sm"
  python src/preprocess.py --sat sat-3l-sm     # versi ringan jika laptop berat
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "all_reviews.csv"
INTERIM = ROOT / "data" / "interim"
FASTTEXT_MODEL = ROOT / "models" / "lid.176.bin"
FASTTEXT_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
# Model HuggingFace disimpan di dalam project (bukan di drive C:).
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))

# Teks dengan jumlah kata <= ini dianggap "pendek" (aturan Melayu -> Indonesia).
BATAS_KATA_PENDEK = 10
# Probabilitas bahasa kedua >= ini dianggap tanda campuran bahasa.
AMBANG_CAMPUR = 0.20

PENANDA_SUNDA = ["mah", "teh", "pisan", "euy", "atuh", "teu", "henteu", "tebih", "abdi",
                 "anjeun", "ieu", "eta", "kumaha", "sae"]
RE_SUNDA = re.compile(r"\b(" + "|".join(PENANDA_SUNDA) + r")\b", re.I)

# Kata kontras tempat klausa dipecah. Kata Latin dicocokkan sebagai kata utuh.
KONTRAS_LATIN = ["tapi", "tetapi", "namun", "cuma", "hanya saja", "sayangnya", "padahal",
                 "walaupun", "but", "however", "although"]
KONTRAS_LAIN = ["但是", "可是", "でも", "しかし", "하지만", "لكن"]
RE_KONTRAS = re.compile(
    r"(?=\b(?:" + "|".join(re.escape(k) for k in KONTRAS_LATIN) + r")\b)"
    + r"|(?=" + "|".join(re.escape(k) for k in KONTRAS_LAIN) + r")",
    re.I,
)

# Bahasa yang dianggap satu rumpun "Melayu-Indonesia" saat membandingkan detektor.
SERUMPUN = {"id", "ms"}

# Teks pendek/slang sering salah dideteksi kedua model ("Mantap" -> Turki, "Keren" -> Belanda).
# Untuk teks pendek atau confidence rendah, kata-kata ini dipakai sebagai penentu bahasa Indonesia.
# Dicocokkan setelah huruf berulang dikompres ("kereeen" -> "keren", "mevvah" -> "mevah").
KATA_INDONESIA = set("""
mantap mantaps mantul keren bagus luas puas bersih nyaman enak cakep indah megah mewah mevah
kemewahan luar biasa sip oke mantab josss jos top recomended rekomended rekomendasi cepat
lumayan ramah murah mahal jauh dekat deket parkir stasiun kereta sepi rame ramai asik asyik
gokil gila kece banget bgt aja udah sudah ga gak nggak ngga engga kalo kalau gimana yg dgn
yang dan tidak sangat buat untuk dari ke di sini situ tapi tp cuma sama juga lagi bisa bs
belum blm akses ojol ojek naik turun pulang pergi tolong harus mau
wus wush whos whosh wosh wow
""".split())
# Penanda Indonesia informal: jika ada, prediksi "ms" diubah menjadi "id".
PENANDA_ID_INFORMAL = set("ga gak nggak ngga engga banget bgt aja udah deket kalo gimana yg dgn enakan".split())
# Bahasa yang wajar muncul sebagai campuran di review ini (probabilitas detektor lain dianggap derau).
BAHASA_CAMPUR_WAJAR = {"en", "su", "jv", "ar", "id", "ms"}
# Kata Inggris umum: dipakai untuk mendeteksi campuran Indonesia-Inggris ("wkt keberangkatan on time").
KATA_INGGRIS = set("""
the is are was very good nice great place station train clean love thank thanks you first class
worth it view time on best recommended but and not with for from to access far city
""".split())


# --------------------------------------------------------------------------- normalisasi
def normalisasi_ringan(teks) -> str:
    """Lowercase + NFKC + kompres huruf berulang (>=3 -> 1) + rapikan spasi."""
    if not isinstance(teks, str):
        return ""
    t = unicodedata.normalize("NFKC", teks).lower()
    t = re.sub(r"(\w)\1{2,}", r"\1", t)  # "macettt" -> "macet", "jauhhh" -> "jauh"
    return re.sub(r"\s+", " ", t).strip()


def token_kompres(teks: str) -> list[str]:
    """Token huruf kecil dengan huruf berulang dikompres penuh ("mantaappp" -> "mantap")."""
    t = unicodedata.normalize("NFKC", teks).lower()
    return [kompres_penuh(w) for w in re.findall(r"[^\W\d_]+", t)]


def kompres_penuh(kata: str) -> str:
    return re.sub(r"(\w)\1+", r"\1", kata)


LEKSIKON_ID = {kompres_penuh(k) for k in KATA_INDONESIA}  # "mevvah" -> "mevah", "keren" tetap


def ada_teks(x) -> bool:
    return isinstance(x, str) and x.strip() != ""


# --------------------------------------------------------------------------- deteksi bahasa
class DetektorBahasa:
    def __init__(self) -> None:
        import fasttext
        from lingua import LanguageDetectorBuilder

        if not FASTTEXT_MODEL.exists():
            import urllib.request

            FASTTEXT_MODEL.parent.mkdir(parents=True, exist_ok=True)
            print(f"Mengunduh {FASTTEXT_URL} ...")
            urllib.request.urlretrieve(FASTTEXT_URL, FASTTEXT_MODEL)
        self.ft = fasttext.load_model(str(FASTTEXT_MODEL))
        self.lingua = LanguageDetectorBuilder.from_all_languages().build()

    def fasttext(self, teks: str) -> list[tuple[str, float]]:
        # Pakai fungsi tingkat-rendah (self.ft.f.predict) karena .predict() rusak di NumPy 2.
        hasil = self.ft.f.predict(teks.replace("\n", " ") + "\n", 3, 0.0, "strict")
        return [(lab.replace("__label__", ""), float(p)) for p, lab in hasil]

    def lingua_top(self, teks: str) -> list[tuple[str, float]]:
        nilai = self.lingua.compute_language_confidence_values(teks)[:3]
        return [(v.language.iso_code_639_1.name.lower(), float(v.value)) for v in nilai]

    def deteksi(self, teks: str, petunjuk_google: str | None = None) -> dict:
        ft = self.fasttext(teks)
        li = self.lingua_top(teks)
        n_kata = len(teks.split())
        pendek = n_kata <= BATAS_KATA_PENDEK
        token = token_kompres(teks)
        n_kata_id = sum(t in LEKSIKON_ID for t in token)
        n_kata_en = sum(t in KATA_INGGRIS for t in token)

        def seragamkan(kode: str) -> str:
            return "id" if (pendek and kode == "ms") else kode

        ft_lang, ft_p = seragamkan(ft[0][0]), ft[0][1]
        li_lang, li_p = (seragamkan(li[0][0]), li[0][1]) if li else ("und", 0.0)

        sepakat = ft_lang == li_lang
        if sepakat:
            lang, conf = ft_lang, max(ft_p, li_p)
        else:
            lang, conf = (ft_lang, ft_p) if ft_p >= li_p else (li_lang, li_p)
        uncertain = not sepakat

        # Teks tanpa huruf (emoji/tanda baca saja): bahasa tidak bisa ditentukan.
        if not token:
            lang, conf, uncertain = "und", 0.0, True
        # Teks sangat pendek atau kedua detektor ragu: pakai leksikon Indonesia, lalu petunjuk Google.
        elif n_kata <= 3 or max(ft_p, li_p) < 0.5:
            kandidat = {k for k, _ in ft} | {k for k, _ in li}
            g = (petunjuk_google or "").split("-")[0].lower()
            if n_kata_id > n_kata_en:
                lang, uncertain = "id", True
            elif g and g in kandidat:
                lang, uncertain = g, True
            else:
                uncertain = True
        # Bahasa Latin "tak lazim" (sv, ro, nl, ...) padahal >= separuh kata ada di leksikon Indonesia.
        if (token and lang not in ("id", "en", "ms", "su", "jv") and not re.search(r"[^\x00-ɏ\s\W]", teks)
                and n_kata_id >= max(1, len(token) / 2) and n_kata_id > n_kata_en):
            lang, uncertain = "id", True
        # Lingua sering melabeli Indonesia informal sebagai Melayu.
        if lang == "ms" and (ft_lang == "id" or any(t in PENANDA_ID_INFORMAL for t in token)):
            lang = "id"

        # Heuristik Sunda: >= 2 penanda berbeda -> Sunda; 1 penanda -> campuran.
        penanda = sorted({m.lower() for m in RE_SUNDA.findall(teks)})
        code_mixed = False
        if lang in SERUMPUN | {"su", "jv"} or ft_lang == "su":
            if len(penanda) >= 2 or ft_lang == "su":
                if lang != "su":
                    uncertain = True  # keputusan diambil heuristik, bukan kedua detektor
                lang = "su"
            elif len(penanda) == 1:
                code_mixed = True

        # Campuran bahasa. Probabilitas bahasa kedua hanya dipercaya untuk teks >= 5 kata
        # (pada teks pendek distribusi probabilitasnya acak).
        if n_kata >= 5:
            for daftar in (ft, li):
                if len(daftar) > 1 and daftar[1][1] >= AMBANG_CAMPUR:
                    a, b = seragamkan(daftar[0][0]), seragamkan(daftar[1][0])
                    lain = ({a, b} - {lang}) or {b}
                    if a != b and not {a, b} <= SERUMPUN and lain <= BAHASA_CAMPUR_WAJAR:
                        code_mixed = True
        # Indonesia + Inggris: minimal satu kata dari masing-masing leksikon.
        if n_kata_id and n_kata_en and lang in ("id", "en", "su"):
            code_mixed = True
        # Campuran aksara Latin dengan CJK/Hangul/Arab.
        if (re.search(r"[A-Za-z]{3,}", teks)
                and re.search(r"[぀-ヿ一-鿿가-힯؀-ۿ]", teks)):
            code_mixed = True
        # Sunda bercampur Indonesia.
        if lang == "su" and sum(t in PENANDA_ID_INFORMAL or t in {"yang", "dan", "tidak", "sangat",
                                                                  "cuma", "kenapa", "ada"} for t in token) >= 2:
            code_mixed = True

        return {
            "language": lang, "lang_conf": round(conf, 3),
            "lang_fasttext": ft[0][0], "lang_fasttext_conf": round(ft_p, 3),
            "lang_lingua": li[0][0] if li else None, "lang_lingua_conf": round(li_p, 3),
            "lang_uncertain": uncertain, "code_mixed": code_mixed,
            "sunda_markers": ",".join(penanda),
        }


# --------------------------------------------------------------------------- segmentasi
def muat_sat(nama: str):
    from wtpsplit import SaT

    try:
        return SaT(nama), nama
    except Exception as e:  # noqa: BLE001  (unduh gagal / memori kurang)
        if nama != "sat-3l-sm":
            print(f"! Gagal memuat {nama} ({e}); pakai sat-3l-sm")
            return SaT("sat-3l-sm"), "sat-3l-sm"
        raise


def pecah_kontras(kalimat: str) -> list[str]:
    potongan = [p for p in RE_KONTRAS.split(kalimat) if p and p.strip()]
    return potongan or [kalimat]


def segmentasi(teks: str, kalimat_sat: list[str]) -> list[tuple[str, int, int]]:
    """Kembalikan (klausa, start, end) dengan offset terhadap text_original."""
    klausa, kursor = [], 0
    for kal in kalimat_sat:
        for bagian in pecah_kontras(kal):
            bersih = bagian.strip()
            if not re.search(r"\w", bersih):
                continue  # hanya tanda baca/emoji
            start = teks.find(bersih, kursor)
            if start < 0:  # seharusnya tidak terjadi; cadangan agar tidak gagal
                start = teks.find(bersih)
            end = start + len(bersih) if start >= 0 else -1
            klausa.append((bersih, start, end))
            if start >= 0:
                kursor = end
    return klausa


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sat", default="sat-12l-sm", help="model SaT (default sat-12l-sm; ringan: sat-3l-sm)")
    ap.add_argument("--resegment", action="store_true", help="abaikan cache clauses.csv")
    args = ap.parse_args()
    INTERIM.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(RAW_FILE, encoding="utf-8")
    print(f"Input: {len(df)} review")
    if "is_near_dup" in df:
        n_dup = int(df["is_near_dup"].sum())
        df = df[~df["is_near_dup"].astype(bool)]
        print(f"Buang near-duplicate: {n_dup}")

    bertekstual = df["text_original"].map(ada_teks)
    df[~bertekstual].to_csv(INTERIM / "reviews_no_text.csv", index=False, encoding="utf-8")
    df = df[bertekstual].reset_index(drop=True)
    print(f"Tanpa teks (hanya rating): {int((~bertekstual).sum())}  |  bertekstual: {len(df)}")

    # Deteksi bahasa
    t0 = time.time()
    det = DetektorBahasa()
    petunjuk = df["lang_google"].where(df["lang_google"].notna(), None)
    bahasa = pd.DataFrame([det.deteksi(t, g) for t, g in zip(df["text_original"], petunjuk)])
    df = pd.concat([df, bahasa], axis=1)
    print(f"Deteksi bahasa selesai ({time.time() - t0:.0f} dtk)")

    # Normalisasi ringan (kolom baru; teks asli tetap)
    df["text_norm"] = df["text_original"].map(normalisasi_ringan)
    df["text_translated_norm"] = df["text_translated"].map(normalisasi_ringan)

    # Segmentasi klausa (di-cache: SaT lambat di CPU; pakai --resegment untuk mengulang)
    t0 = time.time()
    file_klausa = INTERIM / "clauses.csv"
    klausa = pd.read_csv(file_klausa, encoding="utf-8") if file_klausa.exists() else None
    file_ids = INTERIM / "_clauses_review_ids.txt"  # daftar review yang sudah disegmentasi
    ids_sekarang = "\n".join(sorted(df["review_id"]))
    if (klausa is not None and not args.resegment and file_ids.exists()
            and file_ids.read_text(encoding="utf-8") == ids_sekarang):
        nama_sat = "cache"
    else:
        sat, nama_sat = muat_sat(args.sat)
        hasil_sat = list(sat.split(df["text_original"].tolist()))
        baris = []
        for rid, teks, kal in zip(df["review_id"], df["text_original"], hasil_sat):
            for i, (k, s, e) in enumerate(segmentasi(teks, kal)):
                baris.append({"review_id": rid, "clause_idx": i, "clause": k, "char_start": s,
                              "char_end": e, "clause_norm": normalisasi_ringan(k)})
        klausa = pd.DataFrame(baris)
    df["n_clauses"] = df["review_id"].map(klausa.groupby("review_id").size()).fillna(0).astype(int)
    print(f"Segmentasi ({nama_sat}) selesai: {len(klausa)} klausa ({time.time() - t0:.0f} dtk)")

    df.to_csv(INTERIM / "reviews_text.csv", index=False, encoding="utf-8")
    klausa.to_csv(file_klausa, index=False, encoding="utf-8")
    file_ids.write_text(ids_sekarang, encoding="utf-8")

    # Ringkasan
    print("\n=== Ringkasan ===")
    print("Bahasa:", df["language"].value_counts().to_dict())
    print(f"lang_uncertain: {int(df['lang_uncertain'].sum())}  |  code_mixed: {int(df['code_mixed'].sum())}"
          f"  |  ada penanda Sunda: {int((df['sunda_markers'] != '').sum())}")
    print(f"Klausa per review: rata-rata {df['n_clauses'].mean():.2f}, maks {df['n_clauses'].max()}")
    print(f"Offset klausa tidak ditemukan: {int((klausa['char_start'] < 0).sum())}")
    print("Tersimpan: data/interim/reviews_text.csv, reviews_no_text.csv, clauses.csv")


if __name__ == "__main__":
    main()
