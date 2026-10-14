"""Tahap 7 — Analisis label final -> output/figures/*.png + output/analysis_report.md

Sumber: data/processed/final_labels.csv (label Claude/LLM; lihat output/evaluation.md).
Semua persentase memakai sample_weight (saat ini 1.0 untuk semua review karena seluruh
kandidat + seluruh review filter-out dilabel).

Isi:
  1. Distribusi sentimen per aspek + net sentiment (%pos - %neg), CI 95% Wilson (MOVER untuk selisih)
  2. Top issue_tags per aspek (positif & negatif) + contoh evidence
  3. Tren %negatif per aspek per periode relatif (tanggal Google hanya "x bulan/tahun lalu")
  4. Regresi OLS rating ~ dummy aspek x sentimen (SE robust HC3)
  5. Perbandingan antar-listing & antar-bahasa
  6. BERTopic pada evidence KONEKTIVITAS_UMUM + evidence negatif
  7. Ranking keluhan berdasarkan likes
Ringkasan naratif (output/summary.md) ditulis terpisah dari laporan angka ini.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
FIGURES = OUTPUT / "figures"
CONFIG = ROOT / "config"

ASPEK = ["FEEDER_BUS", "PADALARANG", "OJOL", "TAKSI", "ANGKOT_OJEK_PANGKALAN", "PARKIR",
         "AKSES_JALAN_MACET", "JARAK_LOKASI", "INTEGRASI_JADWAL", "KONEKTIVITAS_UMUM"]
NAMA = {"FEEDER_BUS": "Feeder/bus", "PADALARANG": "Padalarang (KA feeder)", "OJOL": "Ojol",
        "TAKSI": "Taksi", "ANGKOT_OJEK_PANGKALAN": "Angkot/opang", "PARKIR": "Parkir & antar-jemput",
        "AKSES_JALAN_MACET": "Akses jalan & macet", "JARAK_LOKASI": "Jarak & lokasi",
        "INTEGRASI_JADWAL": "Integrasi jadwal", "KONEKTIVITAS_UMUM": "Konektivitas umum"}
# Warna: polaritas = diverging biru (positif) <-> merah (negatif), netral abu-abu (titik tengah);
# mixed kuning. Divalidasi dengan dataviz validate_palette.js (abu-abu sengaja tanpa chroma;
# kontras < 3:1 dikompensasi label n + tabel di laporan).
WARNA = {"negative": "#e34948", "mixed": "#eda100", "neutral": "#8f8e88", "positive": "#2a78d6"}
TEKS, TEKS2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
MIN_N_TREN = 10
Z = 1.96


# --------------------------------------------------------------------------- statistik
def wilson(k: float, n: float) -> tuple[float, float, float]:
    if n <= 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    d = 1 + Z**2 / n
    c = (p + Z**2 / (2 * n)) / d
    h = Z * np.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / d
    return p, c - h, c + h


def net_ci(k_pos: float, k_neg: float, n: float) -> tuple[float, float, float]:
    """Net sentiment = %pos - %neg, CI dengan MOVER (Newcombe) dari interval Wilson masing-masing.
    Kovarians multinomial (pos & neg saling eksklusif) diabaikan -> interval sedikit konservatif."""
    p1, l1, u1 = wilson(k_pos, n)
    p2, l2, u2 = wilson(k_neg, n)
    d = p1 - p2
    lo = d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, max(lo, -1.0), min(hi, 1.0)  # selisih proporsi selalu di [-1, 1]


# --------------------------------------------------------------------------- data
def muat() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lab = pd.read_csv(PROCESSED / "final_labels.csv", encoding="utf-8")
    lab["relevant"] = lab["relevant"].astype(bool)
    teks = pd.read_csv(INTERIM / "reviews_text.csv", encoding="utf-8")
    lab = lab.merge(teks[["review_id", "date_relative", "date_precision", "text_original"]], on="review_id", how="left")
    lab["periode"] = lab["date_relative"].map(periode_relatif)
    spans = pd.read_csv(PROCESSED / "final_spans.csv", encoding="utf-8").merge(
        teks[["review_id", "likes", "language", "place_name"]], on="review_id", how="left")
    return lab, spans, teks


def periode_relatif(rel) -> str | None:
    """Tanggal Google hanya relatif. 'x tahun lalu' tidak bisa dipecah per kuartal."""
    if not isinstance(rel, str):
        return None
    t = rel.lower().replace("diedit", "").strip()
    if "tahun" in t:
        return "±setahun lalu" if t.startswith(("setahun", "1 ")) else "±2 tahun lalu"
    return "≤ 11 bulan terakhir"


PERIODE = ["±2 tahun lalu", "±setahun lalu", "≤ 11 bulan terakhir"]


# --------------------------------------------------------------------------- gaya grafik
def gaya(ax) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=TEKS2, labelsize=9)
    ax.xaxis.label.set_color(TEKS2)
    ax.yaxis.label.set_color(TEKS2)


def plt_():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE})
    return plt


# --------------------------------------------------------------------------- 1. sentimen per aspek
def sentimen_per_aspek(lab: pd.DataFrame, md: list[str]) -> pd.DataFrame:
    a = lab[lab["category"].notna()]
    baris = []
    for asp in ASPEK:
        g = a[a["category"] == asp]
        n = g["sample_weight"].sum()
        if n == 0:
            continue
        k = {s: g.loc[g["sentiment"] == s, "sample_weight"].sum() for s in WARNA}
        net, lo, hi = net_ci(k["positive"], k["negative"], n)
        pneg, nlo, nhi = wilson(k["negative"], n)
        baris.append({"aspek": asp, "n": int(round(n)), **{f"%{s[:3]}": 100 * k[s] / n for s in WARNA},
                      "net": 100 * net, "net_lo": 100 * lo, "net_hi": 100 * hi,
                      "%neg_lo": 100 * nlo, "%neg_hi": 100 * nhi})
    t = pd.DataFrame(baris).sort_values("net")
    plt = plt_()

    # (a) 100% stacked horizontal: negatif di kiri, positif di kanan
    fig, ax = plt.subplots(figsize=(8, 4.6))
    gaya(ax)
    y = np.arange(len(t))
    kiri = np.zeros(len(t))
    for s, kol in [("negative", "%neg"), ("mixed", "%mix"), ("neutral", "%neu"), ("positive", "%pos")]:
        ax.barh(y, t[kol], left=kiri, color=WARNA[s], height=0.62, label=s, edgecolor=SURFACE, linewidth=2)
        for yi, v, l in zip(y, t[kol], kiri):
            if v >= 9:
                ax.text(l + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=8,
                        color="white" if s in ("negative", "positive") else TEKS)
        kiri += t[kol].values
    ax.set_yticks(y, [f"{NAMA[x]}" for x in t["aspek"]])
    for yi, n in zip(y, t["n"]):
        ax.text(101.5, yi, f"n={n}", va="center", fontsize=8, color=TEKS2)
    ax.set_xlim(0, 112)
    ax.set_xlabel("% pasangan review×aspek")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.45, 1.1), frameon=False, fontsize=8)
    ax.set_title("Distribusi sentimen per aspek konektivitas", loc="left", fontsize=11, color=TEKS, pad=24)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_sentimen_per_aspek.png", dpi=150)
    plt.close(fig)

    # (b) net sentiment + CI
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    gaya(ax)
    ax.axvline(0, color=TEKS2, lw=1)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    warna = [WARNA["negative"] if v < 0 else WARNA["positive"] for v in t["net"]]
    kecil = (t["n"] < MIN_N_TREN).values
    ax.hlines(y, t["net_lo"], t["net_hi"], color=warna, lw=2, alpha=[0.35 if k else 1 for k in kecil])
    ax.scatter(t["net"][~kecil], y[~kecil], color=np.array(warna)[~kecil], s=46, zorder=3,
               edgecolor=SURFACE, linewidth=2)
    ax.scatter(t["net"][kecil], y[kecil], facecolor=SURFACE, edgecolor=np.array(warna)[kecil], s=46,
               zorder=3, linewidth=1.5)
    for yi, v, n, k in zip(y, t["net"], t["n"], kecil):
        ax.text(103, yi, f"{v:+.0f} (n={n}{', n kecil' if k else ''})", va="center", fontsize=8, color=TEKS2)
    ax.set_yticks(y, [NAMA[x] for x in t["aspek"]])
    ax.set_xlim(-100, 130)
    ax.set_xlabel(f"net sentiment = %positif − %negatif (CI 95%) · titik berongga: n < {MIN_N_TREN}")
    ax.set_title("Net sentiment per aspek", loc="left", fontsize=11, color=TEKS)
    fig.tight_layout()
    fig.savefig(FIGURES / "02_net_sentiment.png", dpi=150)
    plt.close(fig)

    tampil = t.sort_values("net")[["aspek", "n", "%neg", "%mix", "%neu", "%pos", "net", "net_lo", "net_hi"]].copy()
    tampil["aspek"] = tampil["aspek"].map(NAMA)
    md += ["## 1. Sentimen per aspek", "",
           "Unit: pasangan review×aspek. Net = %positif − %negatif; CI 95% Wilson (selisih: MOVER).", "",
           tabel(tampil.round(1)), "", "![](figures/01_sentimen_per_aspek.png)", "",
           "![](figures/02_net_sentiment.png)", ""]
    return t


# --------------------------------------------------------------------------- 2. issue tags
def issue_tags(spans: pd.DataFrame, md: list[str]) -> None:
    s = spans.copy()
    s["tag"] = s["issue_tags"].fillna("").str.split(";")
    s = s.explode("tag")
    s = s[s["tag"].fillna("") != ""]
    md += ["## 2. Issue tags teratas per aspek", "",
           "Dihitung per span. Contoh = evidence terpendek (kutipan asli, untuk verifikasi; di summary diparafrasekan).", ""]
    for asp in ASPEK:
        g = s[s["category"] == asp]
        if g.empty:
            continue
        md.append(f"### {NAMA[asp]}")
        for pol in ("negative", "positive"):
            h = g[g["sentiment"] == pol]
            if h.empty:
                continue
            top = h["tag"].value_counts().head(3)
            item = []
            for tag, n in top.items():
                ev = h.loc[h["tag"] == tag, "evidence"]
                contoh = min(ev, key=len) if len(ev) else ""
                item.append(f"`{tag}` ({n}) — \"{contoh[:90]}\"")
            md.append(f"- **{pol}**: " + "; ".join(item))
        md.append("")


# --------------------------------------------------------------------------- 3. tren
def tren(lab: pd.DataFrame, md: list[str]) -> None:
    a = lab[lab["category"].notna() & lab["periode"].notna()]
    baris = []
    for asp in ASPEK:
        for per in PERIODE:
            g = a[(a["category"] == asp) & (a["periode"] == per)]
            n = g["sample_weight"].sum()
            k = g.loc[g["sentiment"] == "negative", "sample_weight"].sum()
            p, lo, hi = wilson(k, n)
            baris.append({"aspek": asp, "periode": per, "n": int(round(n)), "%neg": 100 * p,
                          "lo": 100 * lo, "hi": 100 * hi, "tampil": n >= MIN_N_TREN})
    t = pd.DataFrame(baris)
    layak = [asp for asp in ASPEK if t[(t["aspek"] == asp) & t["tampil"]].shape[0] >= 2]
    plt = plt_()
    if layak:
        kol = 3
        brs = int(np.ceil(len(layak) / kol))
        fig, axes = plt.subplots(brs, kol, figsize=(9, 2.6 * brs), sharey=True, squeeze=False)
        for ax, asp in zip(axes.flat, layak):
            gaya(ax)
            g = t[(t["aspek"] == asp)].reset_index(drop=True)
            x = np.arange(len(PERIODE))
            ok = g["tampil"].values
            ax.plot(x, g["%neg"].where(ok), color=WARNA["negative"], lw=2)  # NaN = garis terputus
            ax.vlines(x[ok], g.loc[ok, "lo"], g.loc[ok, "hi"], color=WARNA["negative"], lw=1.5, alpha=0.5)
            ax.scatter(x[ok], g.loc[ok, "%neg"], color=WARNA["negative"], s=40, zorder=3, edgecolor=SURFACE, lw=2)
            for xi, v, n, o in zip(x, g["%neg"], g["n"], ok):
                ax.text(xi, 104, f"n={n}" if o else f"n={n}\n(disembunyikan)", ha="center", fontsize=7, color=TEKS2)
            ax.set_xticks(x, ["±2 th", "±1 th", "≤11 bln"])
            ax.set_ylim(0, 118)
            ax.set_title(NAMA[asp], fontsize=9, color=TEKS, loc="left")
            ax.grid(axis="y", color=GRID, lw=0.8)
        for ax in list(axes.flat)[len(layak):]:
            ax.axis("off")
        axes[0][0].set_ylabel("% negatif")
        fig.suptitle("Persentase sentimen negatif per periode (tanggal relatif Google; CI 95% Wilson)",
                     x=0.01, ha="left", fontsize=10, color=TEKS)
        fig.tight_layout()
        fig.savefig(FIGURES / "03_tren_negatif.png", dpi=150)
        plt.close(fig)
    tt = t.copy()
    tt["aspek"] = tt["aspek"].map(NAMA)
    tt.loc[~tt["tampil"], ["%neg", "lo", "hi"]] = np.nan
    events = pd.read_csv(CONFIG / "events.csv")
    md += ["## 3. Tren %negatif per periode", "",
           "Google hanya memberi tanggal relatif; 74% review relevan bertanggal \"setahun lalu\" atau \"2 tahun lalu\","
           " sehingga tren bulanan/kuartalan tidak dapat dibuat. Dipakai tiga periode relatif (dari tanggal scraping"
           " 2026-09-25): ±2 tahun lalu (≈ Okt 2023 – awal 2025), ±setahun lalu (≈ 2025), ≤ 11 bulan terakhir."
           f" Sel dengan n < {MIN_N_TREN} disembunyikan.", "",
           f"config/events.csv memuat {len(events)} peristiwa ({events['date'].min()} s.d. {events['date'].max()})."
           " Karena tanggal review hanya relatif, peristiwa tidak digambar sebagai garis; persilangan peristiwa"
           " dengan periode review dibahas di output/linimasa_kebijakan.md.", "",
           tabel(tt.drop(columns="tampil").round(1)), ""]
    if layak:
        md += ["![](figures/03_tren_negatif.png)", ""]


# --------------------------------------------------------------------------- 4. OLS
def regresi_rating(lab: pd.DataFrame, teks: pd.DataFrame, md: list[str]) -> None:
    import statsmodels.api as sm

    df = teks[["review_id", "rating"]].dropna().copy()
    a = lab[lab["category"].notna() & lab["sentiment"].isin(["negative", "positive"])]
    dummies = {}
    for (asp, sen), g in a.groupby(["category", "sentiment"]):
        if g["review_id"].nunique() >= 5:
            dummies[f"{asp}|{sen}"] = df["review_id"].isin(g["review_id"]).astype(int)
    X = pd.DataFrame(dummies)
    X = sm.add_constant(X)
    model = sm.OLS(df["rating"].values, X).fit(cov_type="HC3")
    ci = model.conf_int()
    hasil = pd.DataFrame({"koef": model.params, "lo": ci[0], "hi": ci[1], "p": model.pvalues,
                          "n": X.sum()}).drop(index="const").sort_values("koef")
    plt = plt_()
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(hasil) + 1.2))
    gaya(ax)
    y = np.arange(len(hasil))
    warna = [WARNA["negative"] if i.endswith("negative") else WARNA["positive"] for i in hasil.index]
    ax.axvline(0, color=TEKS2, lw=1)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.hlines(y, hasil["lo"], hasil["hi"], color=warna, lw=2)
    ax.scatter(hasil["koef"], y, color=warna, s=40, zorder=3, edgecolor=SURFACE, lw=2)
    ax.set_yticks(y, [f"{NAMA[i.split('|')[0]]} · {i.split('|')[1][:3]}  (n={int(n)})"
                      for i, n in zip(hasil.index, hasil["n"])])
    ax.set_xlabel("perubahan rating (bintang) dibanding review tanpa aspek tsb (CI 95%, HC3)")
    ax.set_title("Dampak aspek×sentimen terhadap rating bintang", loc="left", fontsize=11, color=TEKS, pad=18)
    ax.text(0, 1.01, f"OLS, n={int(model.nobs)} review bertekstual, R²={model.rsquared:.2f}; asosiasi, bukan kausal",
            transform=ax.transAxes, fontsize=8, color=TEKS2)
    fig.tight_layout()
    fig.savefig(FIGURES / "04_ols_rating.png", dpi=150)
    plt.close(fig)
    t = hasil.reset_index().rename(columns={"index": "dummy"})
    t["dummy"] = t["dummy"].map(lambda i: f"{NAMA[i.split('|')[0]]} · {i.split('|')[1]}")
    md += ["## 4. Dampak ke rating (OLS)", "",
           f"rating ~ dummy(aspek×sentimen), hanya dummy dengan ≥ 5 review; n = {int(model.nobs)} review bertekstual;"
           f" R² = {model.rsquared:.3f}; intersep = {model.params['const']:.2f}. SE robust HC3."
           " Koefisien = selisih rata-rata bintang dibanding review tanpa aspek×sentimen tersebut (asosiasi, bukan kausal).",
           "", tabel(t.round(3)), "", "![](figures/04_ols_rating.png)", ""]


# --------------------------------------------------------------------------- 5. listing & bahasa
def listing_bahasa(lab: pd.DataFrame, md: list[str]) -> None:
    rev = lab.drop_duplicates("review_id")
    a = lab[lab["category"].notna()]
    out = []
    for kol, judul in [("place_name", "Listing"), ("language", "Bahasa")]:
        baris = []
        for nilai, g in rev.groupby(kol):
            ga = a[a[kol] == nilai]
            n = len(ga)
            k = (ga["sentiment"] == "negative").sum()
            p, lo, hi = wilson(k, n) if n else (np.nan,) * 3
            baris.append({judul: nilai, "review": len(g), "relevan": int(g["relevant"].sum()),
                          "%relevan": 100 * g["relevant"].mean(), "review×aspek": n,
                          "%neg": 100 * p, "%neg_lo": 100 * lo, "%neg_hi": 100 * hi,
                          "aspek terbanyak": ga["category"].map(NAMA).value_counts().index[0] if n else "–"})
        out.append((judul, pd.DataFrame(baris).sort_values("review", ascending=False)))
    md += ["## 5. Perbandingan antar-listing dan antar-bahasa", ""]
    for judul, t in out:
        md += [f"### {judul}", "", tabel(t.round(1)), ""]
    md.append("Listing/bahasa dengan review×aspek < 10 tidak layak dibandingkan (CI sangat lebar).")
    md.append("")


# --------------------------------------------------------------------------- 6. BERTopic
def topik(spans: pd.DataFrame, md: list[str]) -> None:
    dok = spans[(spans["category"] == "KONEKTIVITAS_UMUM") | (spans["sentiment"] == "negative")]
    dok = dok.drop_duplicates("evidence")
    teks = dok["evidence"].astype(str).tolist()
    md += ["## 6. Tema di luar taksonomi (BERTopic)", "",
           f"Dokumen: {len(teks)} evidence unik (KONEKTIVITAS_UMUM + semua evidence negatif). Embedding:"
           " paraphrase-multilingual-mpnet-base-v2 (lokal, CPU).", ""]
    try:
        from bertopic import BERTopic
        from hdbscan import HDBSCAN
        from sentence_transformers import SentenceTransformer
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP

        stop = ("yang dan di ke dari ini itu juga untuk dengan ada tidak ga gak nya sih aja karena kalau kalo"
                " atau jadi masih sudah udah lagi bisa buat saya kita the and to is of in it for a").split()
        emb_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", device="cpu")
        emb = emb_model.encode(teks, show_progress_bar=False)
        model = BERTopic(embedding_model=emb_model,
                         umap_model=UMAP(n_neighbors=10, n_components=5, min_dist=0.0, metric="cosine", random_state=42),
                         hdbscan_model=HDBSCAN(min_cluster_size=6, min_samples=3, prediction_data=True),
                         vectorizer_model=CountVectorizer(stop_words=stop, ngram_range=(1, 2), min_df=2),
                         calculate_probabilities=False)
        topics, _ = model.fit_transform(teks, emb)
        info = model.get_topic_info()
        dok = dok.assign(topik=topics)
        baris = []
        for _, r in info[info["Topic"] != -1].iterrows():
            g = dok[dok["topik"] == r["Topic"]]
            baris.append({"topik": r["Topic"], "n": r["Count"],
                          "kata kunci": ", ".join(w for w, _ in model.get_topic(r["Topic"])[:6]),
                          "aspek dominan (label)": g["category"].map(NAMA).value_counts().index[0],
                          "contoh (dokumen representatif)": (model.get_representative_docs(r["Topic"]) or [""])[0][:90]})
        md += [f"Topik terbentuk: {len(baris)} (outlier: {int((np.array(topics) == -1).sum())} dokumen).", "",
               tabel(pd.DataFrame(baris)), "",
               "Interpretasi: topik yang aspek dominannya tersebar/tidak cocok dengan satu kode menandakan"
               " tema lintas-aspek.", ""]
        from anon import kode_ulasan

        dok.assign(kode_ulasan=dok["review_id"].map(kode_ulasan))[
            ["kode_ulasan", "category", "sentiment", "evidence", "topik"]].to_csv(
            OUTPUT / "bertopic_documents.csv", index=False, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        md += [f"BERTopic gagal dijalankan: `{e}`", ""]
        print("! BERTopic gagal:", e)


# --------------------------------------------------------------------------- 7. likes
def ranking_likes(spans: pd.DataFrame, md: list[str]) -> None:
    neg = spans[spans["sentiment"] == "negative"].copy()
    neg["tag"] = neg["issue_tags"].fillna("").str.split(";")
    neg = neg.explode("tag")
    neg = neg[neg["tag"].fillna("") != ""]
    per_review = neg.drop_duplicates(["review_id", "category", "tag"])
    r = (per_review.groupby(["category", "tag"])
                   .agg(review=("review_id", "nunique"), total_likes=("likes", "sum"), maks_likes=("likes", "max"))
                   .reset_index().sort_values(["total_likes", "review"], ascending=False).head(12))
    r["category"] = r["category"].map(NAMA)
    top = (spans[spans["sentiment"] == "negative"].sort_values("likes", ascending=False)
           .drop_duplicates("review_id").head(8))
    md += ["## 7. Keluhan yang paling banyak disetujui (likes)", "",
           "Total likes = jumlah likes review yang memuat keluhan (aspek×tag) tersebut. Likes di Google Maps kecil"
           f" (maks {int(spans['likes'].max())}); 79 dari 673 review punya ≥ 1 like.", "",
           tabel(r), "", "Review negatif dengan likes terbanyak (evidence asli):", ""]
    for _, x in top.iterrows():
        md.append(f"- {int(x['likes'])} likes · {NAMA[x['category']]} — \"{str(x['evidence'])[:120]}\"")
    md.append("")


# --------------------------------------------------------------------------- utilitas tabel
def tabel(df: pd.DataFrame) -> str:
    kol = list(df.columns)
    out = ["| " + " | ".join(map(str, kol)) + " |", "|" + "---|" * len(kol)]
    for _, r in df.iterrows():
        sel = []
        for v in r:
            if isinstance(v, float):
                sel.append("–" if np.isnan(v) else (f"{v:.1f}" if abs(v) >= 1 or v == 0 else f"{v:.3f}"))
            else:
                sel.append(str(v))
        out.append("| " + " | ".join(sel) + " |")
    return "\n".join(out)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    lab, spans, teks = muat()
    rev = lab.drop_duplicates("review_id")
    tanpa_teks = pd.read_csv(INTERIM / "reviews_no_text.csv", encoding="utf-8")
    md = ["# Laporan analisis — ABSA konektivitas Stasiun Whoosh Tegalluar", "",
          "> Label dibuat oleh LLM (Claude; 2 pass + adjudikasi) **tanpa validasi manusia** — lihat output/evaluation.md.", "",
          f"- Review total: {len(rev) + len(tanpa_teks)} (bertekstual {len(rev)}, hanya rating {len(tanpa_teks)})",
          f"- Review relevan konektivitas: {int(rev['relevant'].sum())} ({100 * rev['relevant'].mean():.1f}% dari bertekstual)",
          f"- Pasangan review×aspek: {int(lab['category'].notna().sum())} · span: {len(spans)}",
          f"- Rata-rata rating: relevan {rev.loc[rev['relevant'], 'rating'].mean():.2f} · tidak relevan"
          f" {rev.loc[~rev['relevant'], 'rating'].mean():.2f} · tanpa teks {tanpa_teks['rating'].mean():.2f}", ""]
    sentimen_per_aspek(lab, md)
    print("[1] sentimen per aspek")
    issue_tags(spans, md)
    print("[2] issue tags")
    tren(lab, md)
    print("[3] tren")
    regresi_rating(lab, teks, md)
    print("[4] OLS")
    listing_bahasa(lab, md)
    print("[5] listing & bahasa")
    topik(spans, md)
    print("[6] BERTopic")
    ranking_likes(spans, md)
    print("[7] likes")
    (OUTPUT / "analysis_report.md").write_text("\n".join(md), encoding="utf-8")
    print("Tersimpan: output/analysis_report.md, output/figures/0*.png")


if __name__ == "__main__":
    main()
