"""Tahap 7b — Analisis lanjutan (turunan dari label final; tidak ada pelabelan ulang).

Output:
  output/analysis_extended.md       laporan (tabel + grafik + catatan)
  output/tables/E*.csv              setiap tabel sebagai CSV
  output/whoosh_absa_hasil.xlsx     semua tabel, satu sheet per analisis (+ katalog kutipan)
  output/figures/05-10_*.png        grafik

Isi:
  E1  Jumlah absolut sentimen: keseluruhan, per aspek, per span, per review
  E2  Pareto keluhan (kontribusi tiap aspek ke total keluhan)
  E3  Issue tags: jumlah per tag x sentimen; matriks aspek x tag
  E4  Matriks prioritas (volume x net sentiment x dampak rating)
  E5  Kookurensi aspek dalam satu review
  E6  Rating: distribusi bintang per aspek x sentimen; komposisi review 1-2 bintang
  E7  Profil per review (jumlah aspek, polaritas review)
  E8  Listing x aspek, bahasa x aspek
  E9  Volume & %negatif per periode x aspek
  E10 Moda yang dibahas (proksi cara datang/pulang)
  E11 Permintaan / saran perbaikan
  E12 Kata & frasa teratas dalam keluhan per aspek
  E13 Foto & likes (sentimen berbobot likes)
  E14 Balasan pengelola
  E15 Katalog kutipan (Excel)
Label = hasil LLM tanpa validasi manusia (lihat output/evaluation.md).
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyze as A  # noqa: E402  (gaya grafik, statistik, loader yang sama)
from anon import kode_ulasan  # noqa: E402

OUTPUT = ROOT / "output"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"
SENT = ["negative", "mixed", "neutral", "positive"]
LABEL_SENT = {"negative": "negatif", "mixed": "campuran", "neutral": "netral", "positive": "positif"}
MODA = {"FEEDER_BUS": "Bus feeder/DAMRI/shuttle", "PADALARANG": "KA feeder via Padalarang",
        "OJOL": "Ojek/mobil online", "TAKSI": "Taksi", "ANGKOT_OJEK_PANGKALAN": "Angkot/ojek pangkalan",
        "PARKIR": "Kendaraan pribadi/antar-jemput"}
RE_SARAN = re.compile(r"\b(tolong|mohon|perlu|harusnya|seharusnya|semoga|sebaiknya|kalau bisa|kalo bisa|"
                      r"diharapkan|diperbanyak|ditambah|ditambahin|diperluas|diperbaiki|dibikin|dibuat|"
                      r"please|should|hopefully|hope|need)\b", re.I)
STOP = set("""yang dan di ke dari ini itu juga untuk dengan ada tidak ga gak nya sih aja karena kalau kalo atau
jadi masih sudah udah lagi bisa buat saya kita kami mau banget sangat agak cukup lebih dr yg dgn utk tp tapi
kok deh dong nih ya kan pun pas sama the and to is of in it for a are was be there this that with on at no
not very so stasiun whoosh tegalluar tegal luar kereta cepat""".split())

tabel_excel: dict[str, pd.DataFrame] = {}


def simpan(nama: str, df: pd.DataFrame, judul_sheet: str) -> pd.DataFrame:
    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES / f"{nama}.csv", index=False, encoding="utf-8")
    tabel_excel[judul_sheet[:31]] = df
    return df


def pct(a, b) -> float:
    return 100 * a / b if b else np.nan


# --------------------------------------------------------------------------- data
def muat():
    lab, spans, teks = A.muat()
    asp = lab[lab["category"].notna()].copy()
    rev = lab.drop_duplicates("review_id").copy()
    rev = rev.merge(teks[["review_id", "has_photo", "owner_response"]], on="review_id", how="left")
    spans = spans.merge(lab.drop_duplicates("review_id")[["review_id", "rating", "periode"]], on="review_id", how="left")
    return lab, asp, rev, spans, teks


def polaritas_review(g: pd.DataFrame) -> str:
    s = set(g["sentiment"])
    ada_neg = bool(s & {"negative", "mixed"})
    ada_pos = bool(s & {"positive", "mixed"})
    if ada_neg and ada_pos:
        return "campuran (ada positif & negatif)"
    if ada_neg:
        return "negatif saja"
    if ada_pos:
        return "positif saja"
    return "netral saja"


# --------------------------------------------------------------------------- E1
def e1_jumlah(asp, rev, spans, md):
    n_asp = len(asp)
    # (a) per aspek, jumlah absolut
    baris = []
    for a in A.ASPEK:
        g = asp[asp["category"] == a]
        c = g["sentiment"].value_counts()
        n = len(g)
        baris.append({"aspek": A.NAMA[a], "total": n,
                      **{f"n_{LABEL_SENT[s]}": int(c.get(s, 0)) for s in SENT},
                      **{f"%_{LABEL_SENT[s]}": pct(c.get(s, 0), n) for s in SENT},
                      "net": pct(c.get("positive", 0) - c.get("negative", 0), n),
                      "share_of_voice_%": pct(n, n_asp)})
    t = pd.DataFrame(baris).sort_values("total", ascending=False)
    tot = asp["sentiment"].value_counts()
    t.loc[len(t)] = {"aspek": "SEMUA ASPEK", "total": n_asp,
                     **{f"n_{LABEL_SENT[s]}": int(tot.get(s, 0)) for s in SENT},
                     **{f"%_{LABEL_SENT[s]}": pct(tot.get(s, 0), n_asp) for s in SENT},
                     "net": pct(tot.get("positive", 0) - tot.get("negative", 0), n_asp), "share_of_voice_%": 100.0}
    simpan("E1a_sentimen_per_aspek_jumlah", t, "E1a Sentimen per aspek")

    # (b) level span dan (c) level review
    sp = spans["sentiment"].value_counts()
    rel = rev[rev["relevant"]]
    pol = asp.groupby("review_id").apply(polaritas_review, include_groups=False)
    pol_c = pol.value_counts()
    ringkas = pd.DataFrame([
        {"tingkat": "Span (setiap kutipan)", "total": len(spans), **{LABEL_SENT[s]: int(sp.get(s, 0)) for s in SENT}},
        {"tingkat": "Review × aspek", "total": n_asp, **{LABEL_SENT[s]: int(tot.get(s, 0)) for s in SENT}},
    ])
    simpan("E1b_sentimen_per_tingkat", ringkas, "E1b Sentimen per tingkat")
    pol_t = pd.DataFrame({"polaritas review": pol_c.index, "jumlah review": pol_c.values,
                          "% dari review relevan": 100 * pol_c.values / len(rel)})
    simpan("E1c_polaritas_review", pol_t, "E1c Polaritas review")

    md += ["## E1. Jumlah sentimen (angka absolut)", "",
           f"Dasar: {len(rev)} review bertekstual → {len(rel)} relevan → {n_asp} pasangan review×aspek → {len(spans)} span/kutipan.", "",
           "### E1a. Per aspek (jumlah & persen)", "", A.tabel(t.round(1)), "",
           "*share of voice* = porsi aspek dari seluruh penyebutan aspek.", "",
           "### E1b. Per tingkat analisis", "", A.tabel(ringkas), "",
           "### E1c. Polaritas per review (gabungan semua aspek dalam satu review)", "", A.tabel(pol_t.round(1)), ""]
    return t


# --------------------------------------------------------------------------- E2 Pareto
def e2_pareto(asp, md):
    neg = asp[asp["sentiment"].isin(["negative", "mixed"])]
    c = neg["category"].value_counts()
    t = pd.DataFrame({"aspek": [A.NAMA[a] for a in c.index], "keluhan": c.values})
    t["%_dari_total_keluhan"] = 100 * t["keluhan"] / t["keluhan"].sum()
    t["kumulatif_%"] = t["%_dari_total_keluhan"].cumsum()
    simpan("E2_pareto_keluhan", t, "E2 Pareto keluhan")
    plt = A.plt_()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    A.gaya(ax)
    x = np.arange(len(t))
    ax.bar(x, t["keluhan"], color=A.WARNA["negative"], width=0.62, edgecolor=A.SURFACE, linewidth=2)
    for xi, n, cum in zip(x, t["keluhan"], t["kumulatif_%"]):
        ax.text(xi, n + 0.8, f"{n}\n(kum. {cum:.0f}%)", ha="center", fontsize=7.5, color=A.TEKS2)
    ax.set_xticks(x, t["aspek"], rotation=30, ha="right")
    ax.set_ylabel("jumlah keluhan (negatif + campuran)")
    ax.set_ylim(0, t["keluhan"].max() * 1.25)
    ax.grid(axis="y", color=A.GRID, lw=0.8)
    ax.set_axisbelow(True)
    n80 = int((t["kumulatif_%"] < 80).sum()) + 1
    ax.set_title(f"Pareto keluhan: {n80} aspek teratas menyumbang ≥80% keluhan", loc="left", fontsize=11, color=A.TEKS)
    fig.tight_layout()
    fig.savefig(FIGURES / "05_pareto_keluhan.png", dpi=150)
    plt.close(fig)
    md += ["## E2. Pareto keluhan", "", f"Total keluhan (review×aspek negatif/campuran): {int(t['keluhan'].sum())}."
           f" **{n80} aspek teratas menyumbang ≥ 80%** keluhan.", "", A.tabel(t.round(1)), "",
           "![](figures/05_pareto_keluhan.png)", ""]


# --------------------------------------------------------------------------- E3 issue tags
def e3_tags(spans, md):
    s = spans.assign(tag=spans["issue_tags"].fillna("").str.split(";")).explode("tag").reset_index(drop=True)
    s = s[s["tag"].fillna("") != ""]
    t = (pd.crosstab(s["tag"], s["sentiment"]).reindex(columns=SENT, fill_value=0)
         .rename(columns=LABEL_SENT))
    t["total"] = t.sum(axis=1)
    t = t.sort_values("total", ascending=False).reset_index()
    simpan("E3a_issue_tag_x_sentimen", t, "E3a Tag x sentimen")
    m = pd.crosstab(s["category"].map(A.NAMA), s["tag"])
    m = m.loc[:, m.sum().sort_values(ascending=False).index]
    simpan("E3b_matriks_aspek_x_tag", m.reset_index().rename(columns={"category": "aspek"}), "E3b Aspek x tag")
    # heatmap (sekuensial satu hue: biru)
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("biru", ["#f4f8fd", "#9ec5f4", "#2a78d6", "#104281"])
    plt = A.plt_()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    im = ax.imshow(m.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(m.shape[1]), m.columns, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(m.shape[0]), m.index, fontsize=8.5)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            if v:
                ax.text(j, i, v, ha="center", va="center", fontsize=7.5,
                        color="white" if v > m.values.max() * 0.55 else A.TEKS)
    ax.set_title("Jumlah span per aspek × issue tag", loc="left", fontsize=11, color=A.TEKS)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    fig.tight_layout()
    fig.savefig(FIGURES / "06_heatmap_aspek_tag.png", dpi=150)
    plt.close(fig)
    md += ["## E3. Issue tags", "", "### E3a. Jumlah per tag × sentimen (level span)", "", A.tabel(t), "",
           "### E3b. Matriks aspek × tag", "", "![](figures/06_heatmap_aspek_tag.png)", "",
           "Tabel lengkap: `tables/E3b_matriks_aspek_x_tag.csv`.", ""]


# --------------------------------------------------------------------------- E4 prioritas
def e4_prioritas(asp, t_e1, md):
    import statsmodels.api as sm

    rev_all = pd.read_csv(A.INTERIM / "reviews_text.csv", encoding="utf-8")[["review_id", "rating"]].dropna()
    dampak = {}
    for a in A.ASPEK:
        ids = asp.loc[(asp["category"] == a) & asp["sentiment"].isin(["negative", "mixed"]), "review_id"]
        if ids.nunique() >= 5:
            X = sm.add_constant(rev_all["review_id"].isin(ids).astype(int))
            dampak[a] = sm.OLS(rev_all["rating"], X).fit(cov_type="HC3").params.iloc[1]
    t = t_e1[t_e1["aspek"] != "SEMUA ASPEK"][["aspek", "total", "n_negatif", "net"]].copy()
    kode = {v: k for k, v in A.NAMA.items()}
    t["dampak_rating_keluhan"] = t["aspek"].map(lambda x: dampak.get(kode[x], np.nan))
    med = t["total"].median()
    t["kuadran"] = np.select(
        [(t["total"] >= med) & (t["net"] < 0), (t["total"] < med) & (t["net"] < 0),
         (t["total"] >= med) & (t["net"] >= 0)],
        ["PRIORITAS UTAMA (sering & negatif)", "Pantau (jarang & negatif)", "Pertahankan (sering & positif)"],
        default="Kekuatan minor (jarang & positif)")
    t = t.sort_values(["kuadran", "net"])
    simpan("E4_matriks_prioritas", t, "E4 Matriks prioritas")
    plt = A.plt_()
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    A.gaya(ax)
    ax.axhline(0, color=A.TEKS2, lw=1)
    ax.axvline(med, color=A.TEKS2, lw=1, ls="--")
    for _, r in t.iterrows():
        c = A.WARNA["negative"] if r["net"] < 0 else A.WARNA["positive"]
        size = 40 + 70 * (abs(r["dampak_rating_keluhan"]) if not np.isnan(r["dampak_rating_keluhan"]) else 0)
        ax.scatter(r["total"], r["net"], s=size, color=c, edgecolor=A.SURFACE, linewidth=2, zorder=3)
        geser = (6, -13) if r["aspek"] == A.NAMA["JARAK_LOKASI"] else (6, 4)  # hindari tabrakan dgn Parkir
        ax.annotate(r["aspek"], (r["total"], r["net"]), xytext=geser, textcoords="offset points",
                    fontsize=8, color=A.TEKS)
    ax.text(0.99, 0.03, "PRIORITAS UTAMA\n(sering & negatif)", transform=ax.transAxes, ha="right",
            fontsize=8, color=A.WARNA["negative"], weight="bold")
    ax.text(0.99, 0.97, "Pertahankan\n(sering & positif)", transform=ax.transAxes, ha="right", va="top",
            fontsize=8, color=A.WARNA["positive"], weight="bold")
    ax.text(0.02, 0.30, "Pantau\n(jarang & negatif)", transform=ax.transAxes, fontsize=8, color=A.TEKS2)
    ax.set_xlim(-2, t["total"].max() * 1.22)  # ruang untuk label titik paling kanan
    ax.set_xlabel(f"volume (pasangan review×aspek); garis putus = median {med:.0f}")
    ax.set_ylabel("net sentiment (%pos − %neg)")
    ax.set_ylim(-110, 70)
    ax.grid(color=A.GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("Matriks prioritas perbaikan (ukuran titik = besar penurunan rating saat dikeluhkan)",
                 loc="left", fontsize=10, color=A.TEKS)
    fig.tight_layout()
    fig.savefig(FIGURES / "07_matriks_prioritas.png", dpi=150)
    plt.close(fig)
    md += ["## E4. Matriks prioritas perbaikan", "",
           "Sumbu x = seberapa sering dibahas; sumbu y = net sentiment; *dampak_rating_keluhan* = selisih rata-rata"
           " bintang review yang mengeluhkan aspek tsb vs sisanya (OLS univariat, asosiasi).", "",
           A.tabel(t.round(2)), "", "![](figures/07_matriks_prioritas.png)", ""]


# --------------------------------------------------------------------------- E5 kookurensi
def e5_kookurensi(asp, md):
    per = asp.groupby("review_id")["category"].apply(lambda x: sorted(set(x)))
    pas = Counter(p for lst in per for p in combinations(lst, 2))
    per_neg = asp[asp["sentiment"].isin(["negative", "mixed"])].groupby("review_id")["category"].apply(lambda x: sorted(set(x)))
    pas_neg = Counter(p for lst in per_neg for p in combinations(lst, 2))
    top = pd.DataFrame([{"aspek 1": A.NAMA[a], "aspek 2": A.NAMA[b], "review (semua sentimen)": n,
                         "review (keduanya dikeluhkan)": pas_neg.get((a, b), 0)} for (a, b), n in pas.most_common(15)])
    simpan("E5_kookurensi_aspek", top, "E5 Kookurensi")
    m = pd.DataFrame(0, index=A.ASPEK, columns=A.ASPEK)
    for (a, b), n in pas.items():
        m.loc[a, b] = m.loc[b, a] = n
    for a in A.ASPEK:
        m.loc[a, a] = int((per.map(lambda l: a in l)).sum())
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("biru", ["#f4f8fd", "#9ec5f4", "#2a78d6", "#104281"])
    plt = A.plt_()
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    off = m.values.astype(float).copy()
    np.fill_diagonal(off, np.nan)
    ax.imshow(off, cmap=cmap)
    lab = [A.NAMA[a] for a in A.ASPEK]
    ax.set_xticks(range(10), lab, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(10), lab, fontsize=8)
    for i in range(10):
        for j in range(10):
            v = m.values[i, j]
            ax.text(j, i, v if i != j else f"({v})", ha="center", va="center", fontsize=7.5,
                    color=A.TEKS2 if i == j else ("white" if v > np.nanmax(off) * 0.55 else A.TEKS))
    ax.set_title("Kookurensi aspek dalam satu review\n(diagonal dalam kurung = total review per aspek)",
                 loc="left", fontsize=10, color=A.TEKS)
    fig.tight_layout()
    fig.savefig(FIGURES / "08_kookurensi_aspek.png", dpi=150)
    plt.close(fig)
    dist = per.map(len).value_counts().sort_index()
    md += ["## E5. Kookurensi aspek (dibahas dalam review yang sama)", "", A.tabel(top), "",
           "![](figures/08_kookurensi_aspek.png)", ""]
    return dist


# --------------------------------------------------------------------------- E6 rating
def e6_rating(asp, rev, md):
    x = asp.merge(rev[["review_id"]], on="review_id")
    x = x[x["sentiment"].isin(["negative", "positive", "neutral"])]
    t = (x.groupby(["category", "sentiment"])["rating"]
          .agg(n="size", rata2="mean", median="median", **{f"{b}★": (lambda s, b=b: int((s == b).sum())) for b in range(1, 6)})
          .reset_index())
    t["category"] = t["category"].map(A.NAMA)
    t["sentiment"] = t["sentiment"].map(LABEL_SENT)
    simpan("E6a_rating_per_aspek_sentimen", t, "E6a Rating aspek x sentimen")
    low = rev[rev["rating"] <= 2]
    low_ids = set(low["review_id"])
    k = asp[asp["review_id"].isin(low_ids) & asp["sentiment"].isin(["negative", "mixed"])]
    t2 = (k.groupby("category")["review_id"].nunique().sort_values(ascending=False)
            .rename("review 1-2★ yang mengeluhkan").reset_index())
    t2["% dari review 1-2★ bertekstual"] = 100 * t2.iloc[:, 1] / len(low)
    t2["category"] = t2["category"].map(A.NAMA)
    n_low_konek = low["relevant"].sum()
    simpan("E6b_komposisi_review_bintang_rendah", t2, "E6b Review 1-2 bintang")
    dist = pd.crosstab(rev["relevant"].map({True: "relevan konektivitas", False: "tidak relevan"}),
                       rev["rating"]).reset_index().rename(columns={"relevant": "kelompok"})
    simpan("E6c_distribusi_bintang", dist, "E6c Distribusi bintang")
    md += ["## E6. Rating", "", "### E6a. Rating per aspek × sentimen", "", A.tabel(t.round(2)), "",
           f"### E6b. Apa isi review bintang 1–2? ({len(low)} review bertekstual; {int(n_low_konek)} ="
           f" {pct(n_low_konek, len(low)):.0f}% membahas konektivitas)", "", A.tabel(t2.round(1)), "",
           "### E6c. Distribusi bintang (kelompok 'tidak relevan' hanya sebagai pembanding)", "", A.tabel(dist), ""]


# --------------------------------------------------------------------------- E7 profil review
def e7_profil(dist_aspek, rev, md):
    t = pd.DataFrame({"jumlah aspek dalam review": dist_aspek.index, "jumlah review": dist_aspek.values})
    t["%"] = 100 * t["jumlah review"] / t["jumlah review"].sum()
    simpan("E7_jumlah_aspek_per_review", t, "E7 Aspek per review")
    rel = rev[rev["relevant"]]
    md += ["## E7. Profil review relevan", "",
           f"- Rata-rata aspek per review relevan: {np.average(t['jumlah aspek dalam review'], weights=t['jumlah review']):.2f}",
           f"- Panjang teks median: relevan {rel['text_original'].str.len().median():.0f} karakter vs tidak relevan"
           f" {rev.loc[~rev['relevant'], 'text_original'].str.len().median():.0f} karakter", "", A.tabel(t.round(1)), ""]


# --------------------------------------------------------------------------- E8 listing & bahasa
def e8_segmen(asp, md):
    out = []
    for kol, nama, kode in [("place_name", "listing", "E8a"), ("language", "bahasa", "E8b")]:
        n = pd.crosstab(asp[kol], asp["category"].map(A.NAMA))
        neg = pd.crosstab(asp[kol], asp["category"].map(A.NAMA),
                          values=asp["sentiment"].isin(["negative", "mixed"]).astype(int), aggfunc="sum").fillna(0)
        gab = n.astype(str) + " (" + (100 * neg / n.replace(0, np.nan)).round(0).fillna(0).astype(int).astype(str) + "% neg)"
        gab = gab.where(n > 0, "–")
        gab.insert(0, "total", n.sum(axis=1))
        gab = gab.sort_values("total", ascending=False).reset_index().rename(columns={kol: nama})
        simpan(f"{kode}_{nama}_x_aspek", gab, f"{kode} {nama.title()} x aspek")
        out.append((nama, gab))
    md += ["## E8. Segmen: listing × aspek dan bahasa × aspek", "", "Isi sel: jumlah review×aspek (persen keluhan).", ""]
    for nama, g in out:
        md += [f"### {nama.title()}", "", A.tabel(g), ""]


# --------------------------------------------------------------------------- E9 periode
def e9_periode(asp, md):
    x = asp[asp["periode"].notna()]
    vol = pd.crosstab(x["category"].map(A.NAMA), x["periode"]).reindex(columns=A.PERIODE, fill_value=0)
    share = (100 * vol / vol.sum()).round(1)
    t = vol.astype(str) + " (" + share.astype(str) + "%)"
    t = t.reset_index().rename(columns={"category": "aspek"})
    simpan("E9_volume_periode_x_aspek", t, "E9 Periode x aspek")
    tot = pd.DataFrame({"periode": A.PERIODE, "review×aspek": vol.sum().values,
                        "%neg": [pct(x[(x["periode"] == p) & x["sentiment"].isin(["negative", "mixed"])].shape[0],
                                     x[x["periode"] == p].shape[0]) for p in A.PERIODE]})
    simpan("E9b_ringkas_periode", tot, "E9b Ringkas periode")
    md += ["## E9. Pergeseran topik per periode", "",
           "Isi sel: jumlah review×aspek (porsi dari seluruh penyebutan pada periode itu). Periode relatif karena"
           " tanggal Google hanya \"x bulan/tahun lalu\".", "", A.tabel(t), "", A.tabel(tot.round(1)), ""]


# --------------------------------------------------------------------------- E10 moda
def e10_moda(asp, md):
    x = asp[asp["category"].isin(MODA)]
    baris = []
    for k, nama in MODA.items():
        g = x[x["category"] == k]
        c = g["sentiment"].value_counts()
        baris.append({"moda": nama, "review": g["review_id"].nunique(),
                      "% dari review relevan": pct(g["review_id"].nunique(), asp["review_id"].nunique()),
                      "positif": int(c.get("positive", 0)), "negatif": int(c.get("negative", 0)),
                      "netral": int(c.get("neutral", 0)), "campuran": int(c.get("mixed", 0)),
                      "net": pct(c.get("positive", 0) - c.get("negative", 0), len(g))})
    t = pd.DataFrame(baris).sort_values("review", ascending=False)
    simpan("E10_moda_dibahas", t, "E10 Moda")
    md += ["## E10. Moda yang dibahas (proksi cara datang/pulang)", "",
           "Bukan survei moda; hanya moda yang disebut pengulas.", "", A.tabel(t.round(1)), ""]


# --------------------------------------------------------------------------- E11 saran
def e11_saran(spans, md):
    s = spans[spans["evidence"].fillna("").str.contains(RE_SARAN)].copy()
    t = s.groupby("category").agg(permintaan=("evidence", "size")).sort_values("permintaan", ascending=False).reset_index()
    t["category"] = t["category"].map(A.NAMA)
    simpan("E11a_permintaan_per_aspek", t, "E11a Permintaan per aspek")
    daftar = s[["category", "sentiment", "issue_tags", "evidence", "likes"]].sort_values(["category", "likes"], ascending=[True, False])
    daftar["category"] = daftar["category"].map(A.NAMA)
    simpan("E11b_daftar_permintaan", daftar, "E11b Daftar permintaan")
    md += ["## E11. Permintaan / saran perbaikan dari pengulas", "",
           f"Span yang mengandung kata permintaan (tolong, mohon, perlu, semoga, sebaiknya, ditambah, please, should, …):"
           f" **{len(s)}**. Deteksi berbasis kata kunci (perkiraan; bisa ada salah tangkap).", "", A.tabel(t), ""]
    for a, g in daftar.groupby("category"):
        md.append(f"- **{a}**: " + " · ".join(f"\"{e[:80]}\"" for e in g["evidence"].head(3)))
    md.append("")


# --------------------------------------------------------------------------- E12 kata
def e12_kata(spans, md):
    baris = []
    for a in A.ASPEK:
        g = spans[(spans["category"] == a) & spans["sentiment"].isin(["negative", "mixed"])]
        tok = Counter()
        for e in g["evidence"].fillna(""):
            w = [x for x in re.findall(r"[a-zA-ZÀ-ɏ]+", e.lower()) if x not in STOP and len(x) > 2]
            tok.update(w)
            tok.update(" ".join(p) for p in zip(w, w[1:]))
        if tok:
            baris.append({"aspek": A.NAMA[a], "n keluhan": len(g),
                          "kata/frasa teratas": ", ".join(f"{k} ({v})" for k, v in tok.most_common(10) if v >= 2)})
    t = pd.DataFrame(baris)
    simpan("E12_kata_teratas_keluhan", t, "E12 Kata keluhan")
    md += ["## E12. Kata & frasa teratas dalam keluhan per aspek", "", A.tabel(t), ""]


# --------------------------------------------------------------------------- E13 foto & likes
def e13_foto_likes(asp, rev, md):
    rel = rev[rev["relevant"]]
    pol = asp.groupby("review_id").apply(polaritas_review, include_groups=False)
    rel = rel.assign(ada_keluhan=rel["review_id"].map(pol).isin(["negatif saja", "campuran (ada positif & negatif)"]))
    t = rel.groupby(rel["has_photo"].map({True: "dengan foto", False: "tanpa foto"})).agg(
        review=("review_id", "size"), pct_ada_keluhan=("ada_keluhan", lambda s: 100 * s.mean()),
        rata2_rating=("rating", "mean"), rata2_likes=("likes", "mean")).reset_index().rename(columns={"has_photo": "kelompok"})
    simpan("E13a_foto_vs_keluhan", t, "E13a Foto")
    w = asp.assign(bobot=asp["likes"] + 1)  # +1 agar review tanpa like tetap dihitung
    baris = []
    for a in A.ASPEK:
        g = w[w["category"] == a]
        if len(g):
            baris.append({"aspek": A.NAMA[a], "n": len(g), "total likes": int(g["likes"].sum()),
                          "net biasa": pct((g["sentiment"] == "positive").sum() - (g["sentiment"] == "negative").sum(), len(g)),
                          "net berbobot likes": pct(g.loc[g["sentiment"] == "positive", "bobot"].sum()
                                                    - g.loc[g["sentiment"] == "negative", "bobot"].sum(), g["bobot"].sum())})
    t2 = pd.DataFrame(baris).sort_values("total likes", ascending=False)
    simpan("E13b_net_berbobot_likes", t2, "E13b Likes")
    md += ["## E13. Foto & likes", "", "### E13a. Review relevan dengan/tanpa foto", "", A.tabel(t.round(2)), "",
           "### E13b. Net sentiment berbobot likes (bobot = likes + 1)", "", A.tabel(t2.round(1)), ""]


# --------------------------------------------------------------------------- E14 balasan
def e14_balasan(rev, md):
    tanpa = pd.read_csv(A.INTERIM / "reviews_no_text.csv", encoding="utf-8")
    n_bal = int(rev["owner_response"].notna().sum()) + int(tanpa["owner_response"].notna().sum())
    n_all = len(rev) + len(tanpa)
    md += ["## E14. Balasan pengelola", "",
           f"Review dengan balasan pemilik/pengelola: **{n_bal} dari {n_all}** ({pct(n_bal, n_all):.1f}%) di kelima listing."
           " Tidak ada satu pun keluhan konektivitas yang ditanggapi di Google Maps.", ""]
    simpan("E14_balasan_pengelola", pd.DataFrame([{"review": n_all, "dibalas": n_bal}]), "E14 Balasan")


# --------------------------------------------------------------------------- E15 katalog
def e15_katalog(spans, md):
    k = spans[["review_id", "place_name", "periode", "rating", "language", "likes", "category", "sentiment",
               "issue_tags", "ragu", "evidence", "catatan"]].copy()
    k["category"] = k["category"].map(A.NAMA)
    k["sentiment"] = k["sentiment"].map(LABEL_SENT)
    k["review_id"] = k["review_id"].map(kode_ulasan)  # kode samaran, bukan ID Google
    k = k.rename(columns={"review_id": "kode_ulasan"})
    k = k.sort_values(["category", "sentiment", "likes"], ascending=[True, True, False])
    simpan("E15_katalog_kutipan", k, "E15 Katalog kutipan")
    md += ["## E15. Katalog kutipan", "",
           f"{len(k)} kutipan (span) lengkap dengan aspek, sentimen, tag, rating, listing, periode, dan likes →"
           " sheet **E15 Katalog kutipan** di `whoosh_absa_hasil.xlsx` (bisa difilter).", ""]


def tulis_excel() -> None:
    path = OUTPUT / "whoosh_absa_hasil.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        info = pd.DataFrame({"Keterangan": [
            "Hasil ABSA konektivitas transportasi Stasiun Whoosh Tegalluar (review Google Maps, scraping 2026-09-25).",
            "Label aspek & sentimen dibuat LLM (Claude, 2 pass + adjudikasi) TANPA validasi manusia.",
            "Satu sheet per analisis; lihat output/analysis_extended.md untuk penjelasan tiap tabel."]})
        info.to_excel(xw, sheet_name="Baca dulu", index=False)
        for nama, df in tabel_excel.items():
            df.to_excel(xw, sheet_name=nama, index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                lebar = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, lebar + 2), 70)
    print(f"Excel: {path.relative_to(ROOT)} ({len(tabel_excel)} sheet)")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    lab, asp, rev, spans, teks = muat()
    md = ["# Analisis lanjutan — ABSA konektivitas Stasiun Whoosh Tegalluar", "",
          "> Turunan dari label final (LLM, tanpa validasi manusia; lihat evaluation.md). Semua tabel tersedia di"
          " `tables/*.csv` dan `whoosh_absa_hasil.xlsx`.", ""]
    t_e1 = e1_jumlah(asp, rev, spans, md); print("E1")
    e2_pareto(asp, md); print("E2")
    e3_tags(spans, md); print("E3")
    e4_prioritas(asp, t_e1, md); print("E4")
    dist = e5_kookurensi(asp, md); print("E5")
    e6_rating(asp, rev, md); print("E6")
    e7_profil(dist, rev, md); print("E7")
    e8_segmen(asp, md); print("E8")
    e9_periode(asp, md); print("E9")
    e10_moda(asp, md); print("E10")
    e11_saran(spans, md); print("E11")
    e12_kata(spans, md); print("E12")
    e13_foto_likes(asp, rev, md); print("E13")
    e14_balasan(rev, md); print("E14")
    e15_katalog(spans, md); print("E15")
    (OUTPUT / "analysis_extended.md").write_text("\n".join(md), encoding="utf-8")
    tulis_excel()
    print("Tersimpan: output/analysis_extended.md, output/tables/, output/figures/05-08_*.png")


if __name__ == "__main__":
    main()
