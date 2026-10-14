"""Tahap 5.5 — Konversi export JSON Label Studio menjadi tabel label final.

Letakkan export (format "JSON") di:
  data/labels/export/*.json               -> pelabelan utama (Claude) -> data/processed/final_labels.csv
  data/labels/export/gold/*.json          -> gold peneliti     -> data/processed/gold_labels.csv
  data/labels/export/llm2/*.json          -> pelabel LLM kedua (122 review sampel gold; BUKAN manusia)
                                             -> data/processed/llm2_labels.csv
  data/labels/export/consistency/*.json   -> label ulang 10%   -> data/processed/consistency_labels.csv
  data/labels/export/annotator2/*.json    -> anotator kedua    -> data/processed/annotator2_labels.csv

Boleh export bertahap (beberapa file): untuk review yang sama, anotasi yang paling baru
(updated_at) yang dipakai. Script idempotent: aman dijalankan berkali-kali.

Output tambahan:
  data/processed/final_spans.csv       satu baris per span (detail sebelum digabung per aspek)
  data/labels/review_ragu.csv          semua span bertanda "ragu" untuk ditinjau ulang
  data/labels/validation_report.md     hasil validasi
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "labels"
EXPORT = LABELS / "export"
PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"

KOLOM_FINAL = ["review_id", "place_name", "date_estimated", "rating", "language", "likes", "relevant",
               "category", "sentiment", "evidence", "issue_tags", "ragu", "catatan", "sample_weight"]


def rel(path: Path) -> str:
    """Path relatif terhadap root project (untuk laporan)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------- baca export
def baca_export(folder: Path) -> dict[str, dict]:
    """Kembalikan {review_id: {"result": [...], "updated_at": ..., "annotator": ...}} (anotasi terbaru)."""
    terbaru: dict[str, dict] = {}
    for f in sorted(folder.glob("*.json")):
        tasks = json.loads(f.read_text(encoding="utf-8"))
        for t in tasks:
            rid = t["data"]["review_id"]
            for a in t.get("annotations", []):
                if a.get("was_cancelled"):
                    continue
                waktu = a.get("updated_at") or a.get("created_at") or ""
                if rid not in terbaru or waktu > terbaru[rid]["updated_at"]:
                    terbaru[rid] = {"result": a.get("result", []), "updated_at": waktu,
                                    "annotator": a.get("completed_by"), "file": f.name}
    return terbaru


def urai_anotasi(result: list[dict]) -> tuple[str | None, list[dict]]:
    """Pisahkan jawaban relevan (level review) dan span beserta atribut per-region."""
    relevan = None
    span: dict[str, dict] = {}
    for r in result:
        nama, nilai, rid = r.get("from_name"), r.get("value", {}), r.get("id")
        if nama == "relevan":
            relevan = (nilai.get("choices") or [None])[0]
            continue
        s = span.setdefault(rid, {"span_id": rid})
        if nama == "aspek":
            s.update(category=(nilai.get("labels") or [None])[0], evidence=nilai.get("text"),
                     start=nilai.get("start"), end=nilai.get("end"))
        elif nama == "sentimen":
            s["sentiment"] = (nilai.get("choices") or [None])[0]
        elif nama == "issue_tags":
            s["issue_tags"] = ";".join(nilai.get("choices") or [])
        elif nama == "ragu":
            s["ragu"] = "ragu" in (nilai.get("choices") or [])
        elif nama == "catatan":
            teks = nilai.get("text") or []
            s["catatan"] = " ".join(teks) if isinstance(teks, list) else str(teks)
    return relevan, list(span.values())


# --------------------------------------------------------------------------- gabung per aspek
def gabung_sentimen(sent: pd.Series) -> str | None:
    s = set(sent.dropna())
    if not s:
        return None
    if len(s) == 1:
        return s.pop()
    if "mixed" in s or {"positive", "negative"} <= s:
        return "mixed"
    return (s - {"neutral"}).pop()  # mis. positive + neutral -> positive


def ke_per_aspek(spans: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per review x aspek (beberapa span aspek yang sama digabung)."""
    if spans.empty:
        return spans
    return (spans.groupby(["review_id", "category"], sort=False)
                 .agg(sentiment=("sentiment", gabung_sentimen),
                      evidence=("evidence", lambda x: " | ".join(e for e in x if isinstance(e, str))),
                      issue_tags=("issue_tags", lambda x: ";".join(sorted({t for v in x.dropna() for t in v.split(";") if t}))),
                      ragu=("ragu", "any"),
                      catatan=("catatan", lambda x: " | ".join(c for c in x.dropna() if c)),
                      n_spans=("span_id", "size"))
                 .reset_index())


# --------------------------------------------------------------------------- proses satu folder
def proses(folder: Path, nama: str, task_file: Path | None) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    anot = baca_export(folder)
    laporan = [f"## {nama}", f"- Folder: `{rel(folder)}` — {len(list(folder.glob('*.json')))} file,"
               f" {len(anot)} review beranotasi"]
    baris_review, baris_span = [], []
    for rid, a in anot.items():
        relevan, spans = urai_anotasi(a["result"])
        baris_review.append({"review_id": rid, "relevan": relevan, "annotator": a["annotator"],
                             "updated_at": a["updated_at"]})
        for s in spans:
            baris_span.append({"review_id": rid, **s})
    rev = pd.DataFrame(baris_review, columns=["review_id", "relevan", "annotator", "updated_at"])
    spans = pd.DataFrame(baris_span, columns=["review_id", "span_id", "category", "evidence", "start", "end",
                                              "sentiment", "issue_tags", "ragu", "catatan"])
    spans["ragu"] = spans["ragu"].fillna(False).astype(bool)

    # ---- validasi
    masalah = []
    tanpa_sent = spans[spans["sentiment"].isna()]
    masalah.append(("Span tanpa sentimen", tanpa_sent[["review_id", "category", "evidence"]]))
    tanpa_label = spans[spans["category"].isna()]
    masalah.append(("Atribut per-span tanpa span aspek (region tanpa label)", tanpa_label[["review_id", "span_id"]]))
    punya_span = set(spans.loc[spans["category"].notna(), "review_id"])
    ya_tanpa = rev[(rev["relevan"] == "ya") & ~rev["review_id"].isin(punya_span)]
    masalah.append(("Relevan = ya tetapi tanpa span", ya_tanpa[["review_id"]]))
    tidak_span = rev[(rev["relevan"] == "tidak") & rev["review_id"].isin(punya_span)]
    masalah.append(("Relevan = tidak tetapi punya span", tidak_span[["review_id"]]))
    tanpa_rel = rev[rev["relevan"].isna()]
    masalah.append(("Jawaban 'relevan' kosong", tanpa_rel[["review_id"]]))
    lainnya = spans[spans["issue_tags"].fillna("").str.contains("lainnya") & spans["catatan"].fillna("").eq("")]
    masalah.append(("issue_tags 'lainnya' tanpa catatan", lainnya[["review_id", "category", "evidence"]]))
    if task_file is not None and task_file.exists():
        semua = {t["data"]["review_id"] for t in json.loads(task_file.read_text(encoding="utf-8"))}
        terlewat = sorted(semua - set(anot))
        masalah.append(("Task terlewat (belum/tidak dianotasi)", pd.DataFrame({"review_id": terlewat})))
        laporan.append(f"- Progres: {len(set(anot) & semua)}/{len(semua)} task"
                       f" ({100 * len(set(anot) & semua) / max(1, len(semua)):.1f}%)")
    for judul, tabel in masalah:
        laporan.append(f"- {judul}: **{len(tabel)}**")
        if 0 < len(tabel) <= 30:
            laporan += [f"    - {', '.join(str(v) for v in row)}" for row in tabel.astype(str).values]
        elif len(tabel) > 30:
            laporan.append(f"    - (menampilkan 30 pertama) " + ", ".join(tabel.iloc[:30, 0].astype(str)))
    return rev, spans[spans["category"].notna()], laporan


def tabel_final(rev: pd.DataFrame, spans: pd.DataFrame) -> pd.DataFrame:
    meta = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")[
        ["review_id", "place_name", "date_estimated", "rating", "language", "likes"]]
    sumber = LABELS / "tasks_main_source.csv"
    bobot = (pd.read_csv(sumber, encoding="utf-8")[["review_id", "sample_weight"]] if sumber.exists()
             else pd.DataFrame(columns=["review_id", "sample_weight"]))
    aspek = ke_per_aspek(spans)
    rev = rev.assign(relevant=rev["relevan"].map({"ya": True, "tidak": False}))
    # Review relevan dengan span -> satu baris per aspek; lainnya -> satu baris tanpa aspek.
    dengan = rev.merge(aspek, on="review_id", how="inner")
    tanpa = rev[~rev["review_id"].isin(aspek["review_id"] if len(aspek) else [])]
    final = pd.concat([dengan, tanpa], ignore_index=True)
    final = final.merge(meta, on="review_id", how="left").merge(bobot, on="review_id", how="left")
    final["sample_weight"] = final["sample_weight"].fillna(1.0)
    final["ragu"] = final["ragu"].fillna(False).astype(bool)
    return final[KOLOM_FINAL].sort_values(["review_id", "category"], na_position="last")


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    laporan = [f"# Validasi label ({datetime.now():%Y-%m-%d %H:%M})", ""]
    target = [
        (EXPORT, "Pelabelan utama", LABELS / "tasks_main.json", "final_labels.csv", "final_spans.csv"),
        (EXPORT / "gold", "Gold (peneliti, buta)", LABELS / "tasks_gold.json", "gold_labels.csv", None),
        (EXPORT / "llm2", "Pelabel LLM kedua (bukan manusia)", LABELS / "tasks_gold.json", "llm2_labels.csv", None),
        (EXPORT / "consistency", "Konsistensi (label ulang)", LABELS / "tasks_consistency.json",
         "consistency_labels.csv", None),
        (EXPORT / "annotator2", "Anotator kedua", LABELS / "tasks_annotator2.json", "annotator2_labels.csv", None),
    ]
    ada = False
    for folder, nama, task_file, keluaran, file_span in target:
        if not folder.exists() or not list(folder.glob("*.json")):
            continue
        ada = True
        rev, spans, lap = proses(folder, nama, task_file)
        laporan += lap + [""]
        final = tabel_final(rev, spans)
        final.to_csv(PROCESSED / keluaran, index=False, encoding="utf-8")
        print(f"{nama}: {rev['review_id'].nunique()} review, {len(spans)} span -> data/processed/{keluaran}")
        if file_span:
            spans.to_csv(PROCESSED / file_span, index=False, encoding="utf-8")
            ragu = spans[spans["ragu"]].merge(
                pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")[["review_id", "text_original"]],
                on="review_id", how="left")
            ragu.to_csv(LABELS / "review_ragu.csv", index=False, encoding="utf-8")
            print(f"  span ragu: {len(ragu)} -> data/labels/review_ragu.csv")
    if not ada:
        print("Belum ada export di data/labels/export/. Export dari Label Studio (format JSON) lalu jalankan lagi.")
        return
    (LABELS / "validation_report.md").write_text("\n".join(laporan), encoding="utf-8")
    print("\n".join(laporan))
    print("\nLaporan: data/labels/validation_report.md")


if __name__ == "__main__":
    main()
