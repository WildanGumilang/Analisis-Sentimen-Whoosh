"""Tahap 6 — Evaluasi kualitas label & baseline -> output/evaluation.md

PENTING: label referensi (data/processed/final_labels.csv) dibuat oleh Claude (LLM, 2 pass +
adjudikasi), BUKAN oleh manusia. Peneliti memutuskan lanjut tanpa gold manusia (2026-09-26).
Semua angka di bawah adalah kesepakatan terhadap label LLM, bukan akurasi terhadap kebenaran.

Isi:
  1. Recall filter   : % review filter-out yang ternyata relevan (menurut label Claude).
  2. Konsistensi     : Claude pass1 vs pass2 (sebelum adjudikasi) — relevansi, aspek, sentimen.
  3. Antar-pelabel   : label final Claude vs pelabel LLM kedua (122 review; bukan manusia).
  4. Baseline        : baseline vs label Claude — F1 aspek per kategori, macro-F1 sentimen,
                       pair-F1, per bahasa, confusion matrix, sensitivitas ambang aspek-embedding.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
LABELS = ROOT / "data" / "labels"
OUTPUT = ROOT / "output"
FIGURES = OUTPUT / "figures"
ASPEK = ["FEEDER_BUS", "PADALARANG", "OJOL", "TAKSI", "ANGKOT_OJEK_PANGKALAN", "PARKIR",
         "AKSES_JALAN_MACET", "JARAK_LOKASI", "INTEGRASI_JADWAL", "KONEKTIVITAS_UMUM"]
SENT = ["positive", "negative", "neutral", "mixed"]
BATAS_RECALL = 0.05


# --------------------------------------------------------------------------- utilitas
def f1_set(ref: set, pred: set) -> tuple[float, float, float]:
    tp = len(ref & pred)
    p = tp / len(pred) if pred else float("nan")
    r = tp / len(ref) if ref else float("nan")
    f = 2 * p * r / (p + r) if pred and ref and (p + r) else 0.0
    return p, r, f


def fmt(x: float) -> str:
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def kappa(a, b) -> float:
    return cohen_kappa_score(a, b) if len(set(a) | set(b)) > 1 else float("nan")


def tabel_md(df: pd.DataFrame) -> str:
    kol = list(df.columns)
    baris = ["| " + " | ".join(map(str, kol)) + " |", "|" + "---|" * len(kol)]
    for _, r in df.iterrows():
        baris.append("| " + " | ".join(fmt(v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(baris)


def per_review(lab: pd.DataFrame) -> tuple[dict, dict]:
    """(relevan per review, {review_id: {aspek: sentimen}})."""
    rel = lab.groupby("review_id")["relevant"].first().astype(bool).to_dict()
    asp = {}
    for rid, g in lab[lab["category"].notna()].groupby("review_id"):
        asp[rid] = dict(zip(g["category"], g["sentiment"]))
    return rel, asp


# --------------------------------------------------------------------------- 1. recall filter
def recall_filter(ref: pd.DataFrame, md: list[str]) -> None:
    src = pd.read_csv(LABELS / "tasks_main_source.csv", encoding="utf-8")
    rel, _ = per_review(ref)
    src["relevan"] = src["review_id"].map(rel)
    ringkas = src.groupby("sumber")["relevan"].agg(["size", "sum"])
    out = src[src["sumber"] == "filtered_out"]
    kand = src[src["sumber"] == "candidate"]
    miss = out["relevan"].mean()
    md += ["## 1. Recall filter (Tahap 3)", "",
           f"- Review filter-out yang relevan: **{int(out['relevan'].sum())}/{len(out)} = {miss:.1%}**"
           f" (batas {BATAS_RECALL:.0%}).",
           f"- Presisi filter (kandidat yang relevan): {int(kand['relevan'].sum())}/{len(kand)}"
           f" = {kand['relevan'].mean():.1%}.",
           f"- Recall filter (terhadap semua review relevan): "
           f"{kand['relevan'].sum() / src['relevan'].sum():.1%}.", ""]
    if miss > BATAS_RECALL or out["relevan"].sum():
        teks = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8").set_index("review_id")["text_original"]
        md.append("Review relevan yang lolos dari filter:")
        for rid in out.loc[out["relevan"], "review_id"]:
            asp = ref[(ref["review_id"] == rid) & ref["category"].notna()]
            md.append(f"- {', '.join(asp['category'] + '/' + asp['sentiment'])} — \"{teks[rid][:160]}\"")
        md.append("")
    print(f"[1] recall filter: miss {miss:.1%}")
    ringkas.to_csv(OUTPUT / "_eval_filter.csv")


# --------------------------------------------------------------------------- 2. konsistensi Claude
def konsistensi_claude(md: list[str]) -> None:
    from claude_label import muat_pass, ringkas

    p1, p2 = muat_pass(1), muat_pass(2)
    ks = sorted(set(p1) & set(p2))
    r1 = [ringkas(p1[k]) for k in ks]
    r2 = [ringkas(p2[k]) for k in ks]
    baris = []
    for a in ASPEK:
        x = [a in r[1] for r in r1]
        y = [a in r[1] for r in r2]
        baris.append({"aspek": a, "n_pass1": sum(x), "n_pass2": sum(y), "kappa": kappa(x, y)})
    s1, s2 = [], []
    for a_, b_ in zip(r1, r2):
        for asp in set(a_[1]) & set(b_[1]):
            s1.append(a_[1][asp]); s2.append(b_[1][asp])
    k_rel = kappa([r[0] for r in r1], [r[0] for r in r2])
    k_sent = kappa(s1, s2)
    n_beda = sum(a != b for a, b in zip(r1, r2))
    md += ["## 2. Konsistensi pelabel (Claude pass 1 vs pass 2, sebelum adjudikasi)", "",
           f"- Relevansi: kappa **{k_rel:.3f}**",
           f"- Sentimen pada aspek yang sama ({len(s1)} pasangan): kappa **{k_sent:.3f}**",
           f"- Review tidak sepakat (diadjudikasi): {n_beda}/{len(ks)}",
           "- Catatan: kedua pass dikerjakan model yang sama, sehingga kappa ini cenderung **melebih-lebihkan**"
           " keandalan dibanding dua anotator manusia. Target spesifikasi (≥ 0,70) terpenuhi, tetapi ini"
           " bukan bukti akurasi.", "", tabel_md(pd.DataFrame(baris)), ""]
    print(f"[2] konsistensi: kappa relevansi {k_rel:.3f}, sentimen {k_sent:.3f}")


# --------------------------------------------------------------------------- 3. antar-pelabel
def antar_pelabel(ref: pd.DataFrame, lain: pd.DataFrame, judul: str, md: list[str]) -> None:
    rel_a, asp_a = per_review(ref)
    rel_b, asp_b = per_review(lain)
    ids = sorted(set(rel_b))
    k_rel = kappa([rel_a[i] for i in ids], [rel_b[i] for i in ids])
    baris = []
    for a in ASPEK:
        x = [a in asp_a.get(i, {}) for i in ids]
        y = [a in asp_b.get(i, {}) for i in ids]
        if sum(x) + sum(y):
            baris.append({"aspek": a, "n_claude": sum(x), "n_lain": sum(y), "kappa": kappa(x, y)})
    s1, s2 = [], []
    for i in ids:
        for a in set(asp_a.get(i, {})) & set(asp_b.get(i, {})):
            s1.append(asp_a[i][a]); s2.append(asp_b[i][a])
    md += [f"## 3. Kesepakatan antar-pelabel: {judul}", "",
           f"- Review: {len(ids)} (sampel stratified yang semula untuk gold)",
           f"- Relevansi: kappa **{k_rel:.3f}**",
           f"- Sentimen pada aspek yang sama ({len(s1)} pasangan): kappa **{kappa(s1, s2):.3f}**",
           "- **Bukan validasi manusia.** File ini dibuat oleh LLM (lead_time 0 detik, 88/122 identik"
           " dengan label Claude), sehingga kesepakatan tinggi tidak menunjukkan akurasi.", "",
           tabel_md(pd.DataFrame(baris)), ""]
    print(f"[3] antar-pelabel ({judul}): kappa relevansi {k_rel:.3f}")


# --------------------------------------------------------------------------- 4. baseline
def evaluasi_pred(ref: pd.DataFrame, pred: pd.DataFrame, ids: list[str]) -> dict:
    rel_r, asp_r = per_review(ref)
    rel_p, asp_p = per_review(pred)
    hasil = {}
    y = [rel_r.get(i, False) for i in ids]
    yp = [rel_p.get(i, False) for i in ids]
    hasil["rel"] = f1_set({i for i, v in zip(ids, y) if v}, {i for i, v in zip(ids, yp) if v})
    hasil["rel_kappa"] = kappa(y, yp)
    pas_r = {(i, a) for i in ids for a in asp_r.get(i, {})}
    pas_p = {(i, a) for i in ids for a in asp_p.get(i, {})}
    hasil["aspek_micro"] = f1_set(pas_r, pas_p)
    per_aspek = {a: f1_set({x for x in pas_r if x[1] == a}, {x for x in pas_p if x[1] == a}) for a in ASPEK}
    hasil["per_aspek"] = per_aspek
    hasil["aspek_macro"] = float(np.nanmean([v[2] for v in per_aspek.values()]))
    sama = sorted(pas_r & pas_p)
    s_r = [asp_r[i][a] for i, a in sama]
    s_p = [asp_p[i][a] for i, a in sama]
    hasil["sent_n"] = len(sama)
    hasil["sent_acc"] = float(np.mean([a == b for a, b in zip(s_r, s_p)])) if sama else float("nan")
    hasil["sent_macro"] = f1_score(s_r, s_p, labels=SENT, average="macro", zero_division=0) if sama else float("nan")
    hasil["cm"] = confusion_matrix(s_r, s_p, labels=SENT) if sama else None
    hasil["pair"] = f1_set({(i, a, asp_r[i][a]) for i, a in pas_r}, {(i, a, asp_p[i][a]) for i, a in pas_p})
    return hasil


def plot_cm(cm: np.ndarray, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 4.2))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(SENT)), SENT, rotation=30)
    ax.set_yticks(range(len(SENT)), SENT)
    ax.set_xlabel("baseline")
    ax.set_ylabel("label Claude (referensi)")
    for i in range(len(SENT)):
        for j in range(len(SENT)):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_title("Sentimen: baseline vs label Claude\n(pasangan review×aspek yang sama-sama terdeteksi)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def evaluasi_baseline(ref: pd.DataFrame, md: list[str]) -> None:
    pred = pd.read_csv(PROCESSED / "baseline_labels.csv", encoding="utf-8")
    ambang = float(pred["emb_threshold"].iloc[0])
    ids = sorted(ref["review_id"].unique())
    h = evaluasi_pred(ref, pred, ids)
    md += [f"## 4. Baseline vs label Claude (ambang aspek-embedding {ambang})", "",
           "| Metrik | Presisi | Recall | F1 |", "|---|---|---|---|",
           f"| Relevansi review | {fmt(h['rel'][0])} | {fmt(h['rel'][1])} | {fmt(h['rel'][2])} |",
           f"| Aspek (micro, review×aspek) | {fmt(h['aspek_micro'][0])} | {fmt(h['aspek_micro'][1])} | {fmt(h['aspek_micro'][2])} |",
           f"| Pair (aspek + sentimen persis) | {fmt(h['pair'][0])} | {fmt(h['pair'][1])} | {fmt(h['pair'][2])} |",
           "", f"- Aspek macro-F1: **{h['aspek_macro']:.3f}** · kappa relevansi: {h['rel_kappa']:.3f}",
           f"- Sentimen (pada {h['sent_n']} pasangan review×aspek yang sama-sama terdeteksi): akurasi"
           f" {h['sent_acc']:.3f}, macro-F1 **{h['sent_macro']:.3f}**", "",
           "### F1 aspek per kategori", ""]
    baris = [{"aspek": a, "presisi": v[0], "recall": v[1], "F1": v[2]} for a, v in h["per_aspek"].items()]
    md += [tabel_md(pd.DataFrame(baris)), ""]

    # per bahasa
    meta = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8").set_index("review_id")["language"]
    baris = []
    for nama, pilih in [("Indonesia (id)", lambda l: l == "id"), ("bahasa lain", lambda l: l != "id")]:
        sub = [i for i in ids if pilih(meta.get(i, "und"))]
        hh = evaluasi_pred(ref, pred, sub)
        baris.append({"bahasa": nama, "n_review": len(sub), "F1 relevansi": hh["rel"][2],
                      "F1 aspek (micro)": hh["aspek_micro"][2], "macro-F1 sentimen": hh["sent_macro"],
                      "pair-F1": hh["pair"][2]})
    md += ["### Per bahasa", "", tabel_md(pd.DataFrame(baris)), ""]

    # confusion matrix
    if h["cm"] is not None:
        FIGURES.mkdir(parents=True, exist_ok=True)
        plot_cm(h["cm"], FIGURES / "eval_confusion_sentiment.png")
        cm = pd.DataFrame(h["cm"], index=[f"ref:{s}" for s in SENT], columns=[f"base:{s}" for s in SENT])
        md += ["### Confusion matrix sentimen (baris = label Claude, kolom = baseline)", "",
               tabel_md(cm.reset_index().rename(columns={"index": ""})), "",
               "![confusion](figures/eval_confusion_sentiment.png)", ""]

    # sensitivitas ambang (deteksi aspek saja; sentimen tidak dihitung ulang)
    import baseline as B

    klausa = pd.read_csv(INTERIM / "clauses.csv", encoding="utf-8")
    baris = []
    for t in (0.0, 0.05, 0.10, 0.15):
        a = B.deteksi_aspek(klausa, t)
        p = a.drop_duplicates(["review_id", "category"]).assign(relevant=True, sentiment="?")
        tanpa = pd.DataFrame({"review_id": sorted(set(ids) - set(p["review_id"])), "relevant": False})
        hh = evaluasi_pred(ref, pd.concat([p, tanpa], ignore_index=True), ids)
        baris.append({"ambang": t, "F1 relevansi": hh["rel"][2], "presisi aspek": hh["aspek_micro"][0],
                      "recall aspek": hh["aspek_micro"][1], "F1 aspek (micro)": hh["aspek_micro"][2],
                      "F1 aspek (macro)": hh["aspek_macro"]})
    md += ["### Sensitivitas ambang aspek-embedding (hanya deteksi aspek)", "",
           "Ambang baseline (0,10) sudah ditetapkan **sebelum** label ada. Tabel ini hanya analisis"
           " sensitivitas, bukan dasar untuk memilih ulang ambang.", "", tabel_md(pd.DataFrame(baris)), ""]
    print(f"[4] baseline: aspek micro-F1 {h['aspek_micro'][2]:.3f}, sentimen macro-F1 {h['sent_macro']:.3f},"
          f" pair-F1 {h['pair'][2]:.3f}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(PROCESSED / "final_labels.csv", encoding="utf-8")
    md = ["# Evaluasi — ABSA konektivitas Stasiun Whoosh Tegalluar", "",
          "> **Label referensi dibuat oleh LLM (Claude: 2 pass independen + adjudikasi), bukan oleh manusia.**"
          " Peneliti memutuskan lanjut tanpa gold manusia. Semua angka di bawah menunjukkan **kesepakatan"
          " terhadap label LLM**, bukan akurasi terhadap kebenaran.", "",
          f"- Review berlabel: {ref['review_id'].nunique()} · relevan: "
          f"{ref.loc[ref['relevant'].astype(bool), 'review_id'].nunique()} · pasangan review×aspek: "
          f"{int(ref['category'].notna().sum())}", ""]
    recall_filter(ref, md)
    konsistensi_claude(md)
    llm2 = PROCESSED / "llm2_labels.csv"
    if llm2.exists():
        antar_pelabel(ref, pd.read_csv(llm2, encoding="utf-8"), "Claude vs pelabel LLM kedua", md)
    ann2 = PROCESSED / "annotator2_labels.csv"
    if ann2.exists():
        antar_pelabel(ref, pd.read_csv(ann2, encoding="utf-8"), "Claude vs anotator kedua", md)
    evaluasi_baseline(ref, md)
    (OUTPUT / "evaluation.md").write_text("\n".join(md), encoding="utf-8")
    print("Tersimpan: output/evaluation.md")


if __name__ == "__main__":
    main()
