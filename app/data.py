"""Pemuatan data dan perhitungan statistik untuk dashboard.

Semua angka dihitung ulang dari label publik (data/public/, hasil src/export_public.py) sehingga filter di
sidebar (periode, listing, bahasa) berlaku konsisten. Fungsi statistik dipakai ulang dari
src/analyze.py agar angka di dashboard sama dengan laporan.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyze as A  # noqa: E402

ASPEK = A.ASPEK
NAMA = A.NAMA
WARNA = A.WARNA
SENT = ["negative", "mixed", "neutral", "positive"]
LABEL_SENT = {"negative": "Negatif", "mixed": "Campuran", "neutral": "Netral", "positive": "Positif"}
# Periode relatif (tanggal Google hanya "x bulan/tahun lalu"; dihitung dari scraping 25 Sep 2026)
PERIODE = {"±2 tahun lalu": "Masa awal", "±setahun lalu": "Menengah", "≤ 11 bulan terakhir": "Terkini"}
URUT_PERIODE = ["Masa awal", "Menengah", "Terkini"]
PRIORITAS_PERIODE = {"Terkini": 0, "Menengah": 1, "Masa awal": 2}  # untuk mengurutkan kutipan: terbaru dulu
# Rentang kalender perkiraan. Google membulatkan ke bawah: "setahun lalu" = 12–23 bulan, "2 tahun lalu"
# = 24–35 bulan sebelum tanggal pengambilan data (25 Sep 2026). Buktinya: tidak ada ulasan "3 tahun lalu"
# padahal stasiun sudah beroperasi 35 bulan (sejak 17 Okt 2023).
KET_PERIODE = {"Masa awal": "Okt 2023 – Sep 2024", "Menengah": "Okt 2024 – Sep 2025", "Terkini": "Okt 2025 – Sep 2026"}
TEKS_GOOGLE = {"Masa awal": "“2 tahun lalu”", "Menengah": "“setahun lalu”",
               "Terkini": "“x hari/minggu/bulan lalu” (s.d. 11 bulan)"}
UMUR = {"Masa awal": "24–35 bulan", "Menengah": "12–23 bulan", "Terkini": "0–11 bulan"}


PUB = ROOT / "data" / "public"


def teks_lengkap_lokal() -> pd.DataFrame | None:
    """Teks ulasan lengkap hanya ada di komputer lokal (tidak dipublikasikan). None bila tidak ada."""
    p = ROOT / "data/interim/reviews_text.csv"
    if not p.exists():
        return None
    from anon import kode_ulasan

    t = pd.read_csv(p, encoding="utf-8", usecols=["review_id", "text_original", "text_translated"])
    t["review_id"] = t["review_id"].map(kode_ulasan)
    return t


@st.cache_data
def muat() -> dict[str, pd.DataFrame]:
    """Muat semua tabel sumber sekali (di-cache).

    Sumber utama: data/public/ (hasil src/export_public.py; ID ulasan berupa kode samaran).
    Teks ulasan lengkap ditambahkan hanya bila data lokal (data/interim) tersedia.
    """
    ulasan = pd.read_csv(PUB / "ulasan.csv", encoding="utf-8")
    lab = pd.read_csv(PUB / "label.csv", encoding="utf-8")
    spans = pd.read_csv(PUB / "kutipan.csv", encoding="utf-8")
    listing = pd.read_csv(PUB / "listing.csv", encoding="utf-8").sort_values("no")
    events = pd.read_csv(ROOT / "config/events.csv", encoding="utf-8")

    lengkap = teks_lengkap_lokal()
    if lengkap is not None:
        ulasan = ulasan.merge(lengkap, on="review_id", how="left")
    else:
        ulasan["text_original"] = None
        ulasan["text_translated"] = None
    teks = ulasan[ulasan["has_text"]].reset_index(drop=True)
    tanpa = ulasan[~ulasan["has_text"]].reset_index(drop=True)

    teks["periode"] = teks["date_relative"].map(A.periode_relatif).map(PERIODE)
    teks["bahasa"] = np.where(teks["language"] == "id", "Indonesia", "Lainnya")
    meta = teks[["review_id", "periode", "bahasa", "date_relative", "text_original", "text_translated",
                 "has_photo", "language"]]
    lab["relevant"] = lab["relevant"].astype(bool)
    lab = lab.merge(meta, on="review_id", how="left")
    spans = spans.merge(lab.drop_duplicates("review_id")[["review_id", "place_name", "rating", "likes",
                                                           "periode", "bahasa", "language", "date_relative",
                                                           "text_original", "text_translated"]],
                        on="review_id", how="left")
    return {"teks": teks, "tanpa": tanpa, "lab": lab, "spans": spans, "events": events, "listing": listing,
            "ada_teks_lengkap": lengkap is not None}


def terapkan_filter(df: pd.DataFrame, f: dict, pakai_periode: bool = True) -> pd.DataFrame:
    """Saring tabel apa pun yang punya kolom periode/place_name/bahasa."""
    m = pd.Series(True, index=df.index)
    if pakai_periode and f.get("periode"):
        m &= df["periode"].isin(f["periode"])
    if f.get("listing"):
        m &= df["place_name"].isin(f["listing"])
    if f.get("bahasa") and f["bahasa"] != "Semua":
        m &= df["bahasa"] == f["bahasa"]
    return df[m]


# --------------------------------------------------------------------------- statistik
def ringkas_aspek(lab: pd.DataFrame) -> pd.DataFrame:
    """Jumlah, persen, net sentiment (CI Wilson/MOVER) per aspek."""
    a = lab[lab["category"].notna()]
    total = len(a)
    baris = []
    for asp in ASPEK:
        g = a[a["category"] == asp]
        n = len(g)
        if n == 0:
            continue
        c = g["sentiment"].value_counts()
        net, lo, hi = A.net_ci(c.get("positive", 0), c.get("negative", 0), n)
        baris.append({"kode": asp, "Aspek": NAMA[asp], "n": n,
                      **{LABEL_SENT[s]: int(c.get(s, 0)) for s in SENT},
                      **{f"% {LABEL_SENT[s]}": 100 * c.get(s, 0) / n for s in SENT},
                      "Net": 100 * net, "Net_lo": 100 * lo, "Net_hi": 100 * hi,
                      "Porsi %": 100 * n / total if total else np.nan})
    return pd.DataFrame(baris)


def polaritas_review(lab: pd.DataFrame) -> pd.Series:
    a = lab[lab["category"].notna()]

    def pol(g):
        s = set(g)
        neg, pos = bool(s & {"negative", "mixed"}), bool(s & {"positive", "mixed"})
        return "Campuran" if neg and pos else "Negatif saja" if neg else "Positif saja" if pos else "Netral saja"
    return a.groupby("review_id")["sentiment"].agg(pol)


def per_periode(lab: pd.DataFrame) -> pd.DataFrame:
    """Porsi penyebutan dan jumlah negatif per aspek per periode."""
    a = lab[lab["category"].notna() & lab["periode"].notna()]
    baris = []
    for per in URUT_PERIODE:
        gp = a[a["periode"] == per]
        tot = len(gp)
        for asp in ASPEK:
            g = gp[gp["category"] == asp]
            k = int((g["sentiment"] == "negative").sum())
            p, lo, hi = A.wilson(k, len(g))
            baris.append({"Periode": per, "kode": asp, "Aspek": NAMA[asp], "n": len(g), "negatif": k,
                          "Porsi %": 100 * len(g) / tot if tot else 0, "% negatif": 100 * p,
                          "lo": 100 * lo, "hi": 100 * hi, "total_periode": tot})
    return pd.DataFrame(baris)


def pareto(lab: pd.DataFrame) -> pd.DataFrame:
    neg = lab[lab["sentiment"].isin(["negative", "mixed"])]
    c = neg["category"].value_counts()
    t = pd.DataFrame({"Aspek": [NAMA[k] for k in c.index], "Keluhan": c.values})
    t["% keluhan"] = 100 * t["Keluhan"] / max(1, t["Keluhan"].sum())
    t["Kumulatif %"] = t["% keluhan"].cumsum()
    return t


def ols_rating(lab: pd.DataFrame, teks: pd.DataFrame, min_n: int = 5) -> pd.DataFrame | None:
    """rating ~ dummy(aspek x sentimen), SE robust HC3. None bila data terlalu sedikit."""
    import statsmodels.api as sm

    ids = teks[["review_id", "rating"]].dropna()
    a = lab[lab["category"].notna() & lab["sentiment"].isin(["negative", "positive"])]
    X = {}
    for (asp, sen), g in a.groupby(["category", "sentiment"]):
        if g["review_id"].nunique() >= min_n:
            X[f"{asp}|{sen}"] = ids["review_id"].isin(g["review_id"]).astype(int).values
    if not X or len(ids) < 30:
        return None
    Xd = sm.add_constant(pd.DataFrame(X, index=ids.index))
    m = sm.OLS(ids["rating"].values, Xd).fit(cov_type="HC3")
    ci = m.conf_int()
    t = pd.DataFrame({"koef": m.params, "lo": ci[0], "hi": ci[1], "p": m.pvalues, "n": Xd.sum()}).drop(index="const")
    t["Aspek"] = [NAMA[i.split("|")[0]] for i in t.index]
    t["Sentimen"] = [LABEL_SENT[i.split("|")[1]] for i in t.index]
    t.attrs["r2"] = m.rsquared
    t.attrs["n"] = int(m.nobs)
    return t.sort_values("koef").reset_index(drop=True)


def tag_matriks(spans: pd.DataFrame) -> pd.DataFrame:
    s = spans.assign(tag=spans["issue_tags"].fillna("").str.split(";")).explode("tag").reset_index(drop=True)
    s = s[s["tag"].fillna("") != ""]
    if s.empty:
        return pd.DataFrame()
    m = pd.crosstab(s["category"].map(NAMA), s["tag"])
    return m.loc[:, m.sum().sort_values(ascending=False).index]


def kookurensi(lab: pd.DataFrame) -> pd.DataFrame:
    per = lab[lab["category"].notna()].groupby("review_id")["category"].apply(lambda x: sorted(set(x)))
    pas = Counter(p for lst in per for p in combinations(lst, 2))
    m = pd.DataFrame(0, index=[NAMA[a] for a in ASPEK], columns=[NAMA[a] for a in ASPEK])
    for (a, b), n in pas.items():
        m.loc[NAMA[a], NAMA[b]] = m.loc[NAMA[b], NAMA[a]] = n
    return m


def fmt(x: float, des: int = 1) -> str:
    """Format angka gaya Indonesia (koma desimal)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:,.{des}f}".replace(",", "X").replace(".", ",").replace("X", ".")
