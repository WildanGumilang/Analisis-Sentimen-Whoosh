"""Tahap 3 — Filter kandidat (recall tinggi).

Review lolos jika memenuhi SALAH SATU:
  (a) keyword dari config/keywords.yaml cocok di text_original ATAU text_translated;
  (b) skor margin embedding (per klausa, ambil maksimum) >= ambang, dengan
      margin = similarity maks ke deskripsi aspek konektivitas
               - similarity maks ke prototipe topik NON-konektivitas (taxonomy.yaml: non_aspect_prototypes).
      Similarity mentah bge-m3 hampir sama (~0.6) untuk semua review stasiun, sehingga margin dipakai
      agar review konektivitas lebih terpisah dari pujian umum/fasilitas (keputusan peneliti, Tahap 3).
  (c) mengandung kata akses tidak langsung (keywords.yaml: _indirect).

Dua langkah:
  python src/filter.py --explore            # hitung skor, tampilkan distribusi + 20 contoh di sekitar ambang
  python src/filter.py --threshold 0.0      # tulis candidates.csv & filtered_out_sample.csv

Model embedding: BAAI/bge-m3 (default) atau --model intfloat/multilingual-e5-base (prefix "query: ").
Skor embedding di-cache di data/interim/embedding_scores.csv.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))  # model disimpan di project (drive D:)

from preprocess import normalisasi_ringan  # noqa: E402  (normalisasi yang sama dengan Tahap 2)

INTERIM = ROOT / "data" / "interim"
CONFIG = ROOT / "config"
FIGURES = ROOT / "output" / "figures"
SKOR_FILE = INTERIM / "embedding_scores.csv"
N_SAMPEL_FILTER_OUT = 200
SEED = 42

# Keyword huruf Latin sependek ini atau lebih pendek dicocokkan sebagai kata utuh.
BATAS_KATA_UTUH = 4


# --------------------------------------------------------------------------- (a) + (c) keyword
def pola_keyword(kw: str, wajib_utuh: set[str]) -> re.Pattern:
    kw_n = normalisasi_ringan(kw)
    latin = bool(re.fullmatch(r"[a-z0-9 .\-]+", kw_n))
    utuh = latin and (len(kw_n) <= BATAS_KATA_UTUH or kw_n in wajib_utuh)
    return re.compile(rf"\b{re.escape(kw_n)}\b" if utuh else re.escape(kw_n))


def muat_keyword() -> tuple[dict[str, list[tuple[str, re.Pattern]]], list[tuple[str, re.Pattern]]]:
    cfg = yaml.safe_load((CONFIG / "keywords.yaml").read_text(encoding="utf-8"))
    wajib_utuh = {normalisasi_ringan(k) for k in cfg.pop("_whole_word", [])}
    # Kata akses tidak langsung selalu dicocokkan sebagai kata utuh ("pergi" tidak cocok dengan "bepergian").
    indirect = [(k, re.compile(rf"\b{re.escape(normalisasi_ringan(k))}\b")) for k in cfg.pop("_indirect", [])]
    aspek = {a: [(k, pola_keyword(str(k), wajib_utuh)) for k in daftar] for a, daftar in cfg.items()}
    return aspek, indirect


def cocokkan(teks_list: list[str], pola: list[tuple[str, re.Pattern]]) -> list[str]:
    hit = []
    for kw, p in pola:
        if any(t and p.search(t) for t in teks_list):
            hit.append(str(kw))
    return hit


# --------------------------------------------------------------------------- (b) embedding
def deskripsi_aspek() -> dict[str, list[str]]:
    """Prototipe per aspek: deskripsi dari taxonomy.yaml + contoh karangan dari guideline.md."""
    tax = yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))["aspects"]
    guide = (CONFIG / "guideline.md").read_text(encoding="utf-8")
    proto = {}
    for kode, desk in tax.items():
        teks = [f"{kode.replace('_', ' ').lower()}: {desk}"]
        blok = re.search(rf"### {kode}\n(.*?)(?=\n### |\n## |\Z)", guide, re.S)
        if blok:
            teks += re.findall(r'- "([^"]+)"', blok.group(1))
        proto[kode] = teks
    return proto


def hitung_skor(model_name: str, reviews: pd.DataFrame, klausa: pd.DataFrame) -> pd.DataFrame:
    from sentence_transformers import SentenceTransformer

    prefix = "query: " if "e5" in model_name else ""
    print(f"Memuat model {model_name} ...")
    model = SentenceTransformer(model_name, device="cpu")
    proto = deskripsi_aspek()
    label_proto, teks_proto = [], []
    for kode, daftar in proto.items():
        label_proto += [kode] * len(daftar)
        teks_proto += daftar
    emb_proto = model.encode([prefix + t for t in teks_proto], normalize_embeddings=True, batch_size=16)
    negatif = yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))["non_aspect_prototypes"]
    emb_neg = model.encode([prefix + t for t in negatif], normalize_embeddings=True, batch_size=16)

    # Unit yang di-embed: tiap klausa asli + teks terjemahan utuh (jika ada; satu unit per review).
    unit = klausa[["review_id", "clause"]].rename(columns={"clause": "unit_text"}).assign(sumber="klausa")
    terj = reviews.loc[reviews["text_translated"].notna(), ["review_id", "text_translated"]]
    unit = pd.concat([unit, terj.rename(columns={"text_translated": "unit_text"}).assign(sumber="terjemahan")],
                     ignore_index=True)
    print(f"Meng-embed {len(unit)} unit (klausa + terjemahan) ...")
    emb = model.encode([prefix + t for t in unit["unit_text"]], normalize_embeddings=True,
                       batch_size=16, show_progress_bar=True)
    sim = emb @ emb_proto.T  # cosine (sudah dinormalisasi)
    kode_urut = list(proto)
    per_aspek = np.stack([sim[:, [i for i, l in enumerate(label_proto) if l == k]].max(1) for k in kode_urut], 1)
    unit["sim_aspek"] = per_aspek.max(1)
    unit["sim_non_aspek"] = (emb @ emb_neg.T).max(1)
    unit["skor"] = unit["sim_aspek"] - unit["sim_non_aspek"]  # skor margin
    unit["aspek_terdekat"] = [kode_urut[i] for i in per_aspek.argmax(1)]
    for j, k in enumerate(kode_urut):
        unit[f"skor_{k}"] = per_aspek[:, j]
    # Skor review = maksimum antar-unit
    idx = unit.groupby("review_id")["skor"].idxmax()
    terbaik = unit.loc[idx, ["review_id", "skor", "sim_aspek", "aspek_terdekat", "unit_text", "sumber"]]
    terbaik.columns = ["review_id", "emb_margin", "emb_sim_aspect", "emb_best_aspect", "emb_best_unit",
                       "emb_best_source"]
    skor = reviews[["review_id"]].merge(terbaik, on="review_id", how="left")
    skor["emb_margin"] = skor["emb_margin"].fillna(-1.0)  # review tanpa klausa (emoji saja)
    skor.attrs["model"] = model_name
    unit.to_csv(INTERIM / "embedding_unit_scores.csv", index=False, encoding="utf-8")
    return skor


# --------------------------------------------------------------------------- main
def siapkan(args) -> pd.DataFrame:
    reviews = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")
    klausa = pd.read_csv(INTERIM / "clauses.csv", encoding="utf-8")
    aspek_kw, indirect = muat_keyword()

    # (a) keyword & (c) kata akses tidak langsung, pada teks asli DAN terjemahan (ternormalisasi)
    kw_aspek, kw_hit, ind_hit = [], [], []
    for _, r in reviews.iterrows():
        teks = [r["text_norm"] if isinstance(r["text_norm"], str) else "",
                r["text_translated_norm"] if isinstance(r["text_translated_norm"], str) else ""]
        hits = {a: cocokkan(teks, pola) for a, pola in aspek_kw.items()}
        kw_aspek.append(";".join(a for a, h in hits.items() if h))
        kw_hit.append(";".join(sorted({k for h in hits.values() for k in h})))
        ind_hit.append(";".join(cocokkan(teks, indirect)))
    reviews["keyword_aspects"] = kw_aspek
    reviews["keywords_hit"] = kw_hit
    reviews["indirect_hit"] = ind_hit
    reviews["match_keyword"] = reviews["keywords_hit"] != ""
    reviews["match_indirect"] = reviews["indirect_hit"] != ""

    # (b) embedding (cache jika model sama)
    if SKOR_FILE.exists() and not args.recompute:
        skor = pd.read_csv(SKOR_FILE, encoding="utf-8")
        if (skor["model"].iloc[0] != args.model or "emb_margin" not in skor
                or set(skor["review_id"]) != set(reviews["review_id"])):
            skor = None
    else:
        skor = None
    if skor is None:
        skor = hitung_skor(args.model, reviews, klausa)
        skor["model"] = args.model
        skor.to_csv(SKOR_FILE, index=False, encoding="utf-8")
    return reviews.merge(skor.drop(columns="model"), on="review_id", how="left")


def eksplorasi(df: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = df["emb_margin"]
    kw = df["match_keyword"]
    print("\n=== Distribusi skor margin embedding (maks per review) ===")
    print(s.describe(percentiles=[.05, .1, .25, .5, .75, .9, .95]).round(3).to_string())
    print(f"\nRata-rata skor: dengan keyword = {s[kw].mean():.3f} | tanpa keyword = {s[~kw].mean():.3f}")
    # Ambang yang disepakati peneliti (Tahap 3): margin >= 0, yaitu klausa lebih mirip aspek konektivitas
    # daripada topik non-konektivitas mana pun.
    usulan = 0.0
    print(f"Ambang: margin >= {usulan}")
    for t in (-0.05, 0.0, 0.02, 0.05):
        tambah = ((s >= t) & ~df["match_keyword"] & ~df["match_indirect"]).sum()
        print(f"  ambang {t:.3f}: review lolos HANYA karena embedding = {tambah}")

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist([s[kw].clip(lower=-0.3), s[~kw].clip(lower=-0.3)], bins=40, stacked=True, label=["cocok keyword", "tanpa keyword"],
            color=["#2a6f97", "#bbbbbb"])
    ax.axvline(usulan, color="#c0392b", ls="--", label=f"ambang {usulan}")
    ax.set_xlabel("skor margin maksimum per review (aspek - non-aspek)")
    ax.set_ylabel("jumlah review")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "filter_embedding_scores.png", dpi=130)
    print(f"Histogram: output/figures/filter_embedding_scores.png")

    # 20 contoh di sekitar ambang, hanya yang TIDAK tertangkap keyword/kata tidak langsung
    # (kelompok inilah yang nasibnya ditentukan ambang).
    sisa = df[~df["match_keyword"] & ~df["match_indirect"]].copy()
    sisa["jarak"] = (sisa["emb_margin"] - usulan).abs()
    contoh = sisa.nsmallest(20, "jarak").sort_values("emb_margin", ascending=False)
    print("\n=== 20 contoh di sekitar ambang (tanpa keyword / kata tidak langsung) ===")
    for _, r in contoh.iterrows():
        tanda = "LOLOS " if r["emb_margin"] >= usulan else "tidak "
        print(f"[{tanda}{r['emb_margin']:+.3f} {r['emb_best_aspect']}] {str(r['text_original'])[:160]!r}")
        print(f"      klausa terdekat: {str(r['emb_best_unit'])[:100]!r}")


def finalisasi(df: pd.DataFrame, ambang: float) -> None:
    df["match_embedding"] = df["emb_margin"] >= ambang
    df["lolos"] = df["match_keyword"] | df["match_embedding"] | df["match_indirect"]
    df["alasan"] = df.apply(lambda r: ";".join(n for n, m in [("keyword", r["match_keyword"]),
                                                             ("embedding", r["match_embedding"]),
                                                             ("tidak_langsung", r["match_indirect"])] if m), axis=1)
    df["emb_threshold"] = ambang
    kolom = ["review_id", "place_name", "rating", "date_estimated", "date_precision", "language",
             "lang_uncertain", "code_mixed", "likes", "text_original", "text_translated", "alasan",
             "keyword_aspects", "keywords_hit", "indirect_hit", "emb_margin", "emb_sim_aspect", "emb_best_aspect",
             "emb_best_unit", "emb_threshold"]
    kandidat = df[df["lolos"]][kolom]
    tidak = df[~df["lolos"]]
    sampel = tidak.sample(n=min(N_SAMPEL_FILTER_OUT, len(tidak)), random_state=SEED)[kolom]
    kandidat.to_csv(INTERIM / "candidates.csv", index=False, encoding="utf-8")
    sampel.to_csv(INTERIM / "filtered_out_sample.csv", index=False, encoding="utf-8")

    print(f"\n=== Hasil filter (ambang margin embedding {ambang}) ===")
    print(f"Review bertekstual : {len(df)}")
    print(f"Kandidat (lolos)   : {len(kandidat)}")
    print(f"  keyword          : {int(df['match_keyword'].sum())}")
    print(f"  embedding        : {int(df['match_embedding'].sum())}  (hanya embedding: "
          f"{int((df['match_embedding'] & ~df['match_keyword'] & ~df['match_indirect']).sum())})")
    print(f"  tidak langsung   : {int(df['match_indirect'].sum())}  (hanya ini: "
          f"{int((df['match_indirect'] & ~df['match_keyword'] & ~df['match_embedding']).sum())})")
    print(f"Tidak lolos        : {len(tidak)} -> sampel {len(sampel)} untuk uji recall")
    if len(tidak) < N_SAMPEL_FILTER_OUT:
        print(f"! Review tidak lolos < {N_SAMPEL_FILTER_OUT}; seluruhnya dipakai sebagai sampel.")
    print("Keyword paling sering:",
          pd.Series(";".join(df["keywords_hit"]).split(";")).replace("", np.nan).dropna()
          .value_counts().head(15).to_dict())
    print("Tersimpan: data/interim/candidates.csv, data/interim/filtered_out_sample.csv")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="BAAI/bge-m3")
    ap.add_argument("--explore", action="store_true", help="tampilkan distribusi skor & contoh sekitar ambang")
    ap.add_argument("--threshold", type=float, help="ambang margin embedding final (disepakati: 0.0)")
    ap.add_argument("--recompute", action="store_true", help="abaikan cache skor embedding")
    args = ap.parse_args()
    if not args.explore and args.threshold is None:
        ap.error("pakai --explore dulu, lalu --threshold X setelah ambang disepakati")
    df = siapkan(args)
    if args.explore:
        eksplorasi(df)
    if args.threshold is not None:
        finalisasi(df, args.threshold)


if __name__ == "__main__":
    main()
