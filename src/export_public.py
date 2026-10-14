"""Ekspor data publik (untuk repo GitHub dan dashboard) -> data/public/

Berisi hasil olahan saja:
  ulasan.csv   metadata 1.191 ulasan (tanpa teks lengkap): listing, bintang, tanggal relatif, bahasa,
               suka, foto, ada/tidaknya teks
  label.csv    label per ulasan x aspek (aspek, sentimen, kutipan bukti, jenis masalah)
  kutipan.csv  label per kutipan (span)
  listing.csv  lima listing Google Maps (tautan, koordinat, ID tempat, jumlah ulasan terkumpul)

ID ulasan Google diganti kode samaran (src/anon.py). Teks ulasan lengkap, data mentah, dan berkas
pelabelan TIDAK diekspor.

    .venv/Scripts/python src/export_public.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anon import kode_ulasan  # noqa: E402

PUB = ROOT / "data" / "public"
TANGGAL_DATA = "2026-09-25"  # tanggal pengambilan data


def main() -> None:
    PUB.mkdir(parents=True, exist_ok=True)
    teks = pd.read_csv(ROOT / "data/interim/reviews_text.csv", encoding="utf-8")
    tanpa = pd.read_csv(ROOT / "data/interim/reviews_no_text.csv", encoding="utf-8")
    lab = pd.read_csv(ROOT / "data/processed/final_labels.csv", encoding="utf-8")
    spans = pd.read_csv(ROOT / "data/processed/final_spans.csv", encoding="utf-8")
    state = json.loads((ROOT / "data/raw/_scrape_state.json").read_text(encoding="utf-8"))

    kol = ["review_id", "place_name", "rating", "date_relative", "language", "likes", "has_photo"]
    ulasan = pd.concat([teks.assign(has_text=True), tanpa.assign(has_text=False, language=None)],
                       ignore_index=True)[kol + ["has_text"]]
    for df in (ulasan, lab, spans):
        df["review_id"] = df["review_id"].map(kode_ulasan)
    assert ulasan["review_id"].is_unique, "tabrakan kode samaran"

    ulasan.to_csv(PUB / "ulasan.csv", index=False, encoding="utf-8")
    lab.drop(columns=["language"]).to_csv(PUB / "label.csv", index=False, encoding="utf-8")
    spans.to_csv(PUB / "kutipan.csv", index=False, encoding="utf-8")

    terkumpul = ulasan["place_name"].value_counts()
    listing = pd.DataFrame([{"no": v["no"], "place_name": v["place_name"], "short_url": v["short_url"],
                             "feature_id": v["feature_id"], "lat": v["lat"], "lng": v["lng"]}
                            for v in state.values()]).sort_values("no")
    listing["ulasan_terkumpul"] = listing["place_name"].map(terkumpul).fillna(0).astype(int)
    listing["tanggal_data"] = TANGGAL_DATA
    listing.to_csv(PUB / "listing.csv", index=False, encoding="utf-8")

    print(f"data/public/: ulasan {len(ulasan)} (bertekstual {int(ulasan['has_text'].sum())}), "
          f"label {len(lab)}, kutipan {len(spans)}, listing {len(listing)}")


if __name__ == "__main__":
    main()
