"""Tahap 4 — Baseline model open-source (pembanding label manual, BUKAN hasil final).

Per klausa (data/interim/clauses.csv):
  Aspek   : keyword aspek (config/keywords.yaml) pada klausa, ATAU embedding: aspek terdekat
            bila skor margin klausa >= 0.10 (--emb-threshold untuk analisis sensitivitas).
  Sentimen: routing bahasa (bahasa review dari Tahap 2)
            - Indonesia : w11wo/indonesian-roberta-base-sentiment-classifier
            - lainnya   : cardiffnlp/twitter-xlm-roberta-base-sentiment (termasuk Sunda)
Agregasi per review x aspek: ada positif & negatif -> mixed; hanya positif -> positive;
hanya negatif -> negative; selain itu neutral.

Dijalankan untuk SEMUA review bertekstual (kandidat + filter-out) agar bisa dibandingkan
dengan seluruh label manual.

Output: data/processed/baseline_labels.csv (satu baris per review x aspek; review tanpa aspek
        = satu baris relevant=False)
        data/processed/baseline_clauses.csv (detail per klausa, untuk analisis error)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))

from filter import cocokkan, muat_keyword  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MODEL_ID = "w11wo/indonesian-roberta-base-sentiment-classifier"
MODEL_LAIN = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LABEL_URUT = {0: "negative", 1: "neutral", 2: "positive"}  # urutan label model cardiffnlp
# Ambang margin untuk aspek dari embedding. Dipilih SEBELUM label manual ada (keputusan peneliti,
# Tahap 4): ~median margin klausa ber-keyword (0.129). Ambang filter Tahap 3 (0.0) terlalu longgar
# untuk memberi label aspek.
AMBANG_BASELINE = 0.10


def deteksi_aspek(klausa: pd.DataFrame, ambang: float) -> pd.DataFrame:
    aspek_kw, _ = muat_keyword()
    unit = pd.read_csv(INTERIM / "embedding_unit_scores.csv", encoding="utf-8")
    unit = unit[unit["sumber"] == "klausa"]
    # embedding_unit_scores berisi klausa dalam urutan yang sama dengan clauses.csv
    assert len(unit) == len(klausa), "clauses.csv berubah sejak Tahap 3; jalankan ulang filter.py"
    unit = unit.reset_index(drop=True)

    baris = []
    for i, k in klausa.iterrows():
        teks = [k["clause_norm"] if isinstance(k["clause_norm"], str) else ""]
        dari_kw = [a for a, pola in aspek_kw.items() if cocokkan(teks, pola)]
        dari_emb = [unit.at[i, "aspek_terdekat"]] if unit.at[i, "skor"] >= ambang else []
        for a in dict.fromkeys(dari_kw + dari_emb):  # urutan stabil, tanpa duplikat
            sumber = "+".join(s for s, ada in [("keyword", a in dari_kw), ("embedding", a in dari_emb)] if ada)
            baris.append({"review_id": k["review_id"], "clause_idx": k["clause_idx"], "clause": k["clause"],
                          "category": a, "aspect_source": sumber, "emb_margin": round(unit.at[i, "skor"], 4)})
    return pd.DataFrame(baris)


def buat_pipeline(nama: str):
    from transformers import pipeline

    return pipeline("text-classification", model=nama, tokenizer=nama, device=-1, truncation=True,
                    max_length=256, top_k=None)


def seragamkan_label(label: str) -> str:
    l = label.lower()
    if l.startswith("label_"):
        return LABEL_URUT[int(l.split("_")[1])]
    return {"pos": "positive", "neg": "negative", "neu": "neutral"}.get(l[:3], l)


def sentimen(teks: list[str], bahasa: list[str]) -> pd.DataFrame:
    hasil = [None] * len(teks)
    for nama, pilih in [(MODEL_ID, lambda b: b == "id"), (MODEL_LAIN, lambda b: b != "id")]:
        idx = [i for i, b in enumerate(bahasa) if pilih(b)]
        if not idx:
            continue
        print(f"Sentimen {len(idx)} klausa dengan {nama} ...")
        clf = buat_pipeline(nama)
        keluaran = clf([teks[i] for i in idx], batch_size=16)
        for i, skor in zip(idx, keluaran):
            terbaik = max(skor, key=lambda d: d["score"])
            hasil[i] = {"sentiment_clause": seragamkan_label(terbaik["label"]),
                        "sent_score": round(terbaik["score"], 4), "sent_model": nama}
    return pd.DataFrame(hasil)


def agregasi(sent: pd.Series) -> str:
    s = set(sent)
    if {"positive", "negative"} <= s:
        return "mixed"
    if "positive" in s:
        return "positive"
    if "negative" in s:
        return "negative"
    return "neutral"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emb-threshold", type=float, default=None,
                    help=f"ambang margin untuk aspek dari embedding (default {AMBANG_BASELINE})")
    args = ap.parse_args()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    reviews = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")
    klausa = pd.read_csv(INTERIM / "clauses.csv", encoding="utf-8")

    ambang = AMBANG_BASELINE if args.emb_threshold is None else args.emb_threshold
    asp = deteksi_aspek(klausa, ambang)
    print(f"Klausa: {len(klausa)} | pasangan klausa-aspek: {len(asp)} (ambang margin {ambang})")

    # Sentimen hanya untuk klausa yang punya aspek (hemat waktu CPU)
    bahasa = asp["review_id"].map(reviews.set_index("review_id")["language"]).fillna("und").tolist()
    unik = asp.drop_duplicates(["review_id", "clause_idx"]).copy()
    unik_bahasa = unik["review_id"].map(reviews.set_index("review_id")["language"]).fillna("und").tolist()
    s = sentimen(unik["clause"].tolist(), unik_bahasa)
    unik = pd.concat([unik[["review_id", "clause_idx"]].reset_index(drop=True), s], axis=1)
    asp = asp.merge(unik, on=["review_id", "clause_idx"], how="left")
    asp["language"] = bahasa
    asp.to_csv(PROCESSED / "baseline_clauses.csv", index=False, encoding="utf-8")

    # Agregasi review x aspek
    agg = (asp.groupby(["review_id", "category"])
              .agg(sentiment=("sentiment_clause", agregasi),
                   evidence=("clause", " | ".join),
                   aspect_source=("aspect_source", lambda x: "+".join(sorted(set("+".join(x).split("+"))))),
                   n_clauses=("clause", "size"))
              .reset_index())
    agg["relevant"] = True
    tanpa = reviews.loc[~reviews["review_id"].isin(agg["review_id"]), ["review_id"]].assign(relevant=False)
    hasil = pd.concat([agg, tanpa], ignore_index=True)
    meta = reviews[["review_id", "place_name", "rating", "language", "date_estimated"]]
    hasil = meta.merge(hasil, on="review_id", how="right")
    kolom = ["review_id", "place_name", "date_estimated", "rating", "language", "relevant", "category",
             "sentiment", "evidence", "aspect_source", "n_clauses"]
    hasil["emb_threshold"] = ambang
    hasil[kolom + ["emb_threshold"]].to_csv(PROCESSED / "baseline_labels.csv", index=False, encoding="utf-8")

    rel = hasil[hasil["relevant"]]
    print("\n=== Ringkasan baseline ===")
    print(f"Review: {len(reviews)} | relevan menurut baseline: {rel['review_id'].nunique()}"
          f" | tidak relevan: {int((~hasil['relevant']).sum())}")
    print("Aspek:", rel["category"].value_counts().to_dict())
    print("Sentimen:", rel["sentiment"].value_counts().to_dict())
    print("Sumber aspek:", rel["aspect_source"].value_counts().to_dict())
    print("Tersimpan: data/processed/baseline_labels.csv, data/processed/baseline_clauses.csv")


if __name__ == "__main__":
    main()
