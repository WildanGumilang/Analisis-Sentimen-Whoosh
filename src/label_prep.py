"""Tahap 5 — Siapkan task Label Studio.

  python src/label_prep.py                 # data/labels/tasks_main.json (kandidat + sampel filter-out, diacak)
  python src/label_prep.py --consistency   # SETELAH pelabelan utama: 10% task acak untuk dilabel ulang
  python src/label_prep.py --annotator2    # opsional: 150 review acak untuk anotator kedua
  python src/label_prep.py --gold          # ~120 review stratified untuk dilabel BUTA oleh peneliti (gold)

Prinsip:
- Blind labeling: TIDAK ada prediksi baseline / pre-annotation.
- Sampel filter-out dicampur tanpa penanda di tampilan; asal task hanya dicatat di
  data/labels/tasks_main_source.csv.
- Urutan task acak dengan seed tetap (bukan per listing/tanggal).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
LABELS = ROOT / "data" / "labels"
SEED = 20260926
DETIK_PER_REVIEW = 30
BATAS_OPSI_SAMPLING = 1500
PROPORSI_KONSISTENSI = 0.10
N_ANOTATOR2 = 150
# Alokasi sampel gold per kelompok filter (total 120; A = kandidat ber-keyword dilebihkan).
ALOKASI_GOLD = {"A": 60, "B": 35, "C": 25}

KOLOM = ["review_id", "place_name", "rating", "language", "text_original", "text_translated"]


def data_task(r: pd.Series) -> dict:
    """Isi 'data' task. Hanya info bantu yang diizinkan; tanpa skor filter/baseline."""
    rating = "-" if pd.isna(r["rating"]) else f"{r['rating']:.0f}★"
    return {
        "review_id": r["review_id"],
        "text_original": r["text_original"],
        "text_translated": r["text_translated"] if isinstance(r["text_translated"], str) else "(tidak ada terjemahan)",
        "meta": f"Tempat: {r['place_name']}  ·  Bahasa: {r['language']}  ·  Rating: {rating}",
        "place_name": r["place_name"],
        "language": r["language"],
        "rating": None if pd.isna(r["rating"]) else float(r["rating"]),
    }


def tulis_task(df: pd.DataFrame, path: Path) -> None:
    tasks = [{"data": data_task(r)} for _, r in df.iterrows()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")


def siapkan_utama() -> None:
    kand = pd.read_csv(INTERIM / "candidates.csv", encoding="utf-8")[KOLOM].assign(sumber="candidate")
    out = pd.read_csv(INTERIM / "filtered_out_sample.csv", encoding="utf-8")[KOLOM].assign(sumber="filtered_out")
    n_out_total = len(pd.read_csv(INTERIM / "reviews_text.csv", usecols=["review_id"])) - len(kand)
    semua = pd.concat([kand, out], ignore_index=True).drop_duplicates("review_id")
    semua = semua.sample(frac=1, random_state=SEED).reset_index(drop=True)  # urutan acak

    # Bobot sampling (dipakai di Tahap 7). Kandidat dilabel semua -> bobot 1.
    # Filter-out: bobot = total tidak lolos / jumlah sampel (1.0 bila semua tidak lolos dilabel).
    bobot_out = n_out_total / max(1, len(out))
    semua["sample_weight"] = semua["sumber"].map({"candidate": 1.0, "filtered_out": bobot_out})
    semua["urutan_task"] = range(1, len(semua) + 1)

    tulis_task(semua, LABELS / "tasks_main.json")
    semua[["urutan_task", "review_id", "sumber", "sample_weight"]].to_csv(
        LABELS / "tasks_main_source.csv", index=False, encoding="utf-8")

    n = len(semua)
    jam = n * DETIK_PER_REVIEW / 3600
    print("=== Task pelabelan utama ===")
    print(f"Kandidat         : {len(kand)}")
    print(f"Sampel filter-out: {len(out)} (dari {n_out_total} review tidak lolos; bobot {bobot_out:.2f})")
    print(f"Total task       : {n}  ->  estimasi {jam:.1f} jam (asumsi {DETIK_PER_REVIEW} dtk/review)")
    print(f"Per bahasa       : {semua['language'].value_counts().to_dict()}")
    if n > BATAS_OPSI_SAMPLING:
        print(f"! Task > {BATAS_OPSI_SAMPLING}: tentukan (a) labeli semua, atau (b) sampel stratified.")
    print("Tersimpan: data/labels/tasks_main.json, data/labels/tasks_main_source.csv (penanda asal task)")


def siapkan_konsistensi() -> None:
    utama = pd.read_csv(LABELS / "tasks_main_source.csv", encoding="utf-8")
    sampel = utama.sample(frac=PROPORSI_KONSISTENSI, random_state=SEED + 1)
    review = muat_review().set_index("review_id").loc[sampel["review_id"]].reset_index()
    review = review.sample(frac=1, random_state=SEED + 2)  # urutan berbeda dari task utama
    tulis_task(review, LABELS / "tasks_consistency.json")
    print(f"tasks_consistency.json: {len(review)} task (10% acak). Labeli minimal beberapa hari setelah"
          " pelabelan utama, tanpa melihat label lama (buat project Label Studio terpisah).")


def siapkan_anotator2() -> None:
    utama = pd.read_csv(LABELS / "tasks_main_source.csv", encoding="utf-8")
    sampel = utama.sample(n=min(N_ANOTATOR2, len(utama)), random_state=SEED + 3)
    review = muat_review().set_index("review_id").loc[sampel["review_id"]].reset_index()
    tulis_task(review, LABELS / "tasks_annotator2.json")
    print(f"tasks_annotator2.json: {len(review)} task untuk anotator kedua (project Label Studio terpisah;"
          " beri guideline yang sama, tanpa label Anda).")


def siapkan_gold() -> None:
    """Sampel stratified untuk dilabel BUTA oleh peneliti (gold) -> mengukur akurasi label Claude.

    Strata = kelompok filter (A: kandidat ber-keyword, B: kandidat embedding saja, C: filter-out)
             x bahasa (id / lainnya) x rating (<=3 / >=4).
    Alokasi per kelompok sengaja tidak proporsional (A dilebihkan: kaya aspek), lalu proporsional
    di dalam kelompok dengan minimal 1 per sel. Bobot = N_sel / n_sel untuk estimasi terbobot.
    """
    kand = pd.read_csv(INTERIM / "candidates.csv", encoding="utf-8")
    src = pd.read_csv(LABELS / "tasks_main_source.csv", encoding="utf-8")
    rev = muat_review().merge(src[["review_id", "sumber"]], on="review_id")
    ber_kw = set(kand.loc[kand["alasan"].str.contains("keyword"), "review_id"])
    rev["kelompok"] = [("A" if r in ber_kw else "B") if s == "candidate" else "C"
                       for r, s in zip(rev["review_id"], rev["sumber"])]
    rev["bhs"] = rev["language"].where(rev["language"] == "id", "lain")
    rev["rtg"] = rev["rating"].apply(lambda x: "<=3" if x <= 3 else ">=4")
    rev["stratum"] = rev["kelompok"] + "|" + rev["bhs"] + "|" + rev["rtg"]

    terpilih = []
    for kel, n_kel in ALOKASI_GOLD.items():
        sub = rev[rev["kelompok"] == kel]
        ukuran = sub["stratum"].value_counts()
        alok = (ukuran / ukuran.sum() * n_kel).round().clip(lower=1).astype(int)
        alok = alok.clip(upper=ukuran)  # tidak melebihi isi sel
        for st, n in alok.items():
            terpilih.append(sub[sub["stratum"] == st].sample(n=n, random_state=SEED + 4))
    gold = pd.concat(terpilih)
    n_sel = gold["stratum"].value_counts()
    N_sel = rev["stratum"].value_counts()
    gold["gold_weight"] = gold["stratum"].map(N_sel / n_sel)
    gold = gold.sample(frac=1, random_state=SEED + 5).reset_index(drop=True)  # urutan acak

    tulis_task(gold, LABELS / "tasks_gold.json")
    gold[["review_id", "kelompok", "stratum", "gold_weight"]].to_csv(
        LABELS / "gold_source.csv", index=False, encoding="utf-8")
    print(f"tasks_gold.json: {len(gold)} task  (estimasi {len(gold) * DETIK_PER_REVIEW / 60:.0f} menit)")
    print("Per kelompok:", gold["kelompok"].value_counts().to_dict(),
          "| per bahasa:", gold["bhs"].value_counts().to_dict(),
          "| per rating:", gold["rtg"].value_counts().to_dict())
    print("Labeli BUTA (project Label Studio terpisah), export JSON ke data/labels/export/gold/.")


def muat_review() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")[KOLOM]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--consistency", action="store_true")
    ap.add_argument("--annotator2", action="store_true")
    ap.add_argument("--gold", action="store_true")
    args = ap.parse_args()
    if args.gold:
        siapkan_gold()
    if args.consistency:
        siapkan_konsistensi()
    if args.annotator2:
        siapkan_anotator2()
    if not (args.consistency or args.annotator2 or args.gold):
        siapkan_utama()


if __name__ == "__main__":
    main()
