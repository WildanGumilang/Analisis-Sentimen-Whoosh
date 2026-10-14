"""Dashboard ABSA konektivitas transportasi Stasiun Whoosh Tegalluar.

Jalankan dari root project:
    .venv/Scripts/streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts as C  # noqa: E402
import data as D  # noqa: E402

st.set_page_config(page_title="Konektivitas Whoosh Tegalluar", page_icon="🚉", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 2rem; max-width: 1250px;}
  .catatan {background:#F3F2EF; border-left:4px solid #8F8E88; padding:.7rem 1rem; border-radius:4px; font-size:.92rem;}
  .kini {background:#EAF2FC; border-left:4px solid #2A78D6; padding:.7rem 1rem; border-radius:4px;}
  .konteks {background:#FDF5E3; border-left:4px solid #EDA100; padding:.7rem 1rem; border-radius:4px;}
  .kutipan {border-left:3px solid #B7D3F6; padding:.35rem .9rem; margin:.45rem 0; font-size:.95rem;}
  .kutipan .meta {color:#7A7974; font-size:.8rem;}
  div[data-testid="stMetricValue"] {color:#104281;}
</style>""", unsafe_allow_html=True)

DATA = D.muat()
LAB_ALL, TEKS_ALL, SPANS_ALL = DATA["lab"], DATA["teks"], DATA["spans"]
# Teks ulasan lengkap hanya tersedia di komputer lokal; versi publik (GitHub) hanya memuat kutipan.
ADA_TEKS = DATA["ada_teks_lengkap"]

# --------------------------------------------------------------------------- filter global
with st.sidebar:
    st.markdown("### Filter")
    f_periode = st.multiselect("Periode ulasan ditulis", D.URUT_PERIODE, default=D.URUT_PERIODE,
                               format_func=lambda p: f"{p} ({D.KET_PERIODE[p]})",
                               help="Ditentukan dari teks tanggal yang ditampilkan Google pada setiap ulasan. "
                                    "Lihat penjelasan di bawah.")
    f_bahasa = st.radio("Bahasa ulasan", ["Semua", "Indonesia", "Lainnya"], horizontal=True)
    FILTER = {"periode": f_periode, "bahasa": f_bahasa}
    st.divider()
    st.caption("Label aspek & sentimen dibuat oleh AI (2 putaran + adjudikasi) **tanpa validasi manusia**. "
               "Data ulasan per 25 September 2026.")

LAB = D.terapkan_filter(LAB_ALL, FILTER)
TEKS = D.terapkan_filter(TEKS_ALL, FILTER)
SPANS = D.terapkan_filter(SPANS_ALL, FILTER)


def info_filter():
    aktif = []
    if set(FILTER["periode"]) != set(D.URUT_PERIODE):
        aktif.append("periode: " + ", ".join(f"{p} ({D.KET_PERIODE[p]})" for p in FILTER["periode"])
                     if FILTER["periode"] else "periode: (kosong)")
    if FILTER["bahasa"] != "Semua":
        aktif.append(f"bahasa: {FILTER['bahasa']}")
    if aktif:
        st.caption("Filter aktif: " + " · ".join(aktif))


def metrik(kol, label: str, nilai: str, ket: str | None = None):
    """Metrik dengan keterangan biasa (tanpa panah naik/turun yang menyesatkan)."""
    kol.metric(label, nilai)
    if ket:
        kol.caption(ket)


def kutipan_html(ev: str, meta: str, lengkap: str | None = None) -> str:
    return f"<div class='kutipan'>“{ev}”<br><span class='meta'>{meta}</span></div>"


def cukup(df: pd.DataFrame, minimal: int = 1) -> bool:
    if len(df) < minimal:
        st.info("Tidak ada data untuk kombinasi filter ini.")
        return False
    return True


# ============================================================================ halaman
def hal_ringkasan():
    st.title("Konektivitas Transportasi Stasiun Whoosh Tegalluar")
    st.markdown("Apa yang dialami penumpang saat **menuju dan meninggalkan** stasiun, menurut ulasan Google Maps.")
    info_filter()
    rel = TEKS[TEKS["review_id"].isin(LAB.loc[LAB["relevant"], "review_id"])]
    tidak = TEKS[~TEKS["review_id"].isin(rel["review_id"])]
    c = st.columns(4)
    c[0].metric("Ulasan bertekstual", f"{len(TEKS):,}".replace(",", "."))
    metrik(c[1], "Membahas konektivitas", f"{len(rel)}", f"{D.fmt(100 * len(rel) / max(1, len(TEKS)))}% dari bertekstual")
    metrik(c[2], "Rata-rata bintang", D.fmt(rel["rating"].mean(), 2) if len(rel) else "–",
                f"vs {D.fmt(tidak['rating'].mean(), 2)} ulasan lain" if len(tidak) else None)
    metrik(c[3], "Ulasan dibalas pengelola", "0", "dari 1.191 ulasan")

    t = D.ringkas_aspek(LAB)
    if cukup(t):
        tot = t[["Negatif", "Campuran", "Netral", "Positif"]].sum()
        n = int(tot.sum())
        pol = D.polaritas_review(LAB).value_counts()
        st.markdown(f"Dari **{n} penyebutan** aspek konektivitas: **{int(tot['Negatif'])} negatif "
                    f"({D.fmt(100 * tot['Negatif'] / n, 0)}%)**, {int(tot['Positif'])} positif "
                    f"({D.fmt(100 * tot['Positif'] / n, 0)}%), {int(tot['Netral'])} netral, dan {int(tot['Campuran'])} campuran. "
                    f"Per ulasan: {int(pol.get('Negatif saja', 0))} hanya berisi keluhan, "
                    f"{int(pol.get('Positif saja', 0))} hanya pujian, {int(pol.get('Campuran', 0))} berisi keduanya.")

    st.subheader("Lima hal yang terjadi sekarang")
    st.caption("Disusun dari seluruh data (tidak terpengaruh filter), membandingkan 11 bulan terakhir dengan masa awal operasi.")
    temuan = [
        ("Keluhan utama sekarang: jalan dan jarak.",
         "Dalam 11 bulan terakhir jarak/lokasi menjadi topik paling sering (31% penyebutan), disusul akses jalan (23%). "
         "Dari 19 penyebutan soal jalan, 14 negatif: jalan sempit lewat kampung, gelap di malam hari, akses tol yang tidak pasti, rute membingungkan."),
        ("Parkir naik menjadi sumber keluhan ketiga.",
         "10 dari 15 penyebutan terbaru negatif: lahan panas tanpa atap, kapasitas sempit (95 lot mobil vs 630 di Halim), "
         "alur drop-off yang membuat pengantar tetap membayar, dan cara pembayaran."),
        ("Angkutan umum reguler belum ada.",
         "Pilihannya hanya DAMRI, shuttle Summarecon, taksi, dan ojek daring. Padalarang, dengan kereta penghubung gratis ke pusat kota, "
         "dipuji dalam 5 dari 6 penyebutan terbaru."),
        ("Konflik ojek pangkalan vs ojek daring sudah tidak muncul.",
         "Keluhan paling keras di masa awal (24 ulasan) tidak disebut lagi sejak periode menengah. "
         "Sisa keluhan ojek daring kini soal tarif dan pesanan yang lama lalu dibatalkan."),
        ("Pengelola tidak menanggapi.", "Tidak satu pun dari 1.191 ulasan di kelima listing pernah dibalas."),
    ]
    for i, (judul, isi) in enumerate(temuan, 1):
        st.markdown(f"**{i}. {judul}** {isi}")
    st.markdown("<div class='catatan'><b>Perlu diketahui.</b> Penandaan topik dan nada setiap ulasan dilakukan oleh model AI "
                "dalam dua putaran terpisah, tetapi <b>belum dicocokkan dengan penilaian manusia</b>. Tanggal ulasan hanya "
                "perkiraan karena Google menampilkan keterangan seperti “setahun lalu”. Baca angka sebagai pola, bukan ukuran presisi.</div>",
                unsafe_allow_html=True)


def hal_aspek():
    st.title("Aspek & Sentimen")
    st.markdown("Komposisi penilaian untuk sepuluh aspek konektivitas. Satu **penyebutan** = satu aspek dalam satu ulasan.")
    info_filter()
    t = D.ringkas_aspek(LAB)
    if not cukup(t):
        return
    tab1, tab2, tab4, tab5, tab3 = st.tabs(["Komposisi sentimen", "Net sentiment", "Jenis masalah",
                                             "Keluhan yang muncul bersama", "Tabel angka"])
    with tab4:
        m = D.tag_matriks(SPANS)
        if len(m):
            st.plotly_chart(C.heatmap(m, "jenis masalah / pujian"), use_container_width=True)
            st.caption("Jumlah kutipan per aspek dan jenis masalah. Makin gelap, makin sering disebut.")
    with tab5:
        st.plotly_chart(C.heatmap(D.kookurensi(LAB), tinggi=520), use_container_width=True)
        st.caption("Jumlah ulasan yang membahas dua aspek sekaligus. Contoh: ojol dan angkot/opang adalah dua sisi "
                   "konflik yang sama; akses jalan dan jarak sering muncul bersama karena jarak terasa jauh akibat jalannya.")
    with tab1:
        st.plotly_chart(C.komposisi(t), use_container_width=True)
        st.caption("Diurutkan dari net sentiment terendah (paling banyak dikeluhkan) ke tertinggi.")
    with tab2:
        st.plotly_chart(C.net_sentiment(t), use_container_width=True)
        st.caption("Net = % positif − % negatif. Garis horizontal adalah rentang ketidakpastian 95% (Wilson/MOVER): "
                   "dua aspek yang garisnya tumpang tindih belum tentu benar-benar berbeda.")
    with tab3:
        tampil = t.drop(columns=["kode", "Net_lo", "Net_hi"]).sort_values("n", ascending=False)
        st.dataframe(tampil, hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="%.1f") for c in tampil.columns
                                    if c.startswith("%") or c in ("Net", "Porsi %")})
        st.download_button("Unduh CSV", tampil.to_csv(index=False).encode("utf-8"), "sentimen_per_aspek.csv", "text/csv")


def hal_terkini():
    st.title("Fenomena Terkini")
    st.markdown("Apa yang dibicarakan **11 bulan terakhir** dibandingkan masa awal operasi. "
                "Halaman ini sengaja membandingkan periode, jadi **filter periode tidak berlaku** di sini.")
    lab = D.terapkan_filter(LAB_ALL, FILTER, pakai_periode=False)
    pp = D.per_periode(lab)
    if not cukup(lab):
        return
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Topik bergeser")
        st.plotly_chart(C.banding_periode(pp), use_container_width=True)
    with c2:
        teks = D.terapkan_filter(TEKS_ALL, FILTER, pakai_periode=False)
        st.subheader("Perhatian terhadap konektivitas")
        for per in D.URUT_PERIODE:
            tp = teks[teks["periode"] == per]
            rel = tp["review_id"].isin(lab.loc[lab["relevant"], "review_id"])
            metrik(st, f"{per} · {D.KET_PERIODE[per]} · Google: {D.TEKS_GOOGLE[per]}",
                      f"{D.fmt(100 * rel.mean() if len(tp) else np.nan, 0)}% ulasan",
                      f"{int(rel.sum())} dari {len(tp)} · rata-rata {D.fmt(tp.loc[rel, 'rating'].mean(), 2)}★")
        st.markdown("<div class='kini'><b>Kondisi sekarang.</b> Pengguna berkendaraan pribadi berhadapan dengan jalan sempit, "
                    "gelap, dan macet, lalu parkir yang panas dan terbatas. Pengguna tanpa kendaraan bergantung pada DAMRI, "
                    "shuttle, taksi, atau ojek daring karena tidak ada angkutan umum reguler.</div>", unsafe_allow_html=True)
    st.divider()
    c3, c4 = st.columns(2)
    t = D.ringkas_aspek(lab)
    with c3:
        st.subheader("Mana yang paling mendesak")
        st.plotly_chart(C.prioritas(t), use_container_width=True)
        st.caption("Kuadran kanan bawah: sering dibahas dan negatif. Seluruh periode.")
    with c4:
        st.subheader("Pareto keluhan")
        pr = D.pareto(lab)
        if len(pr):
            st.plotly_chart(C.pareto(pr), use_container_width=True)
            n80 = int((pr["Kumulatif %"] < 80).sum()) + 1
            st.caption(f"{n80} aspek teratas menyumbang ≥ 80% dari {int(pr['Keluhan'].sum())} keluhan.")


def hal_tema():
    st.title("Detail Tema")
    info_filter()
    pilihan = {D.NAMA[a]: a for a in D.ASPEK}
    nama = st.selectbox("Pilih aspek", list(pilihan), index=list(pilihan).index("Akses jalan & macet"))
    kode = pilihan[nama]
    g = LAB[LAB["category"] == kode]
    s = SPANS[SPANS["category"] == kode]
    if not cukup(g):
        return
    c = g["sentiment"].value_counts()
    n = len(g)
    k = st.columns(4)
    k[0].metric("Penyebutan", n)
    metrik(k[1], "Negatif", f"{D.fmt(100 * c.get('negative', 0) / n, 0)}%", f"{int(c.get('negative', 0))} penyebutan")
    metrik(k[2], "Positif", f"{D.fmt(100 * c.get('positive', 0) / n, 0)}%", f"{int(c.get('positive', 0))} penyebutan")
    k[3].metric("Net sentiment", f"{100 * (c.get('positive', 0) - c.get('negative', 0)) / n:+.0f}".replace(".", ","))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Jenis masalah / pujian")
        tag = s.assign(tag=s["issue_tags"].fillna("").str.split(";")).explode("tag")
        tag = tag[tag["tag"].fillna("") != ""]
        if len(tag):
            vc = (tag.groupby(["tag", "sentiment"]).size().unstack(fill_value=0)
                  .reindex(columns=D.SENT, fill_value=0))
            vc["total"] = vc.sum(axis=1)
            vc = vc.sort_values("total", ascending=False).head(10)
            fig = C.go.Figure()
            for sen in D.SENT:
                if vc[sen].sum():
                    fig.add_bar(y=vc.index, x=vc[sen], orientation="h", name=D.LABEL_SENT[sen], marker_color=D.WARNA[sen])
            fig.update_layout(barmode="stack")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(C.gaya(fig, tinggi=80 + 32 * len(vc)), use_container_width=True)
        else:
            st.caption("Belum ada label jenis masalah.")
    with c2:
        st.subheader("Persentase negatif per periode")
        lab_np = D.terapkan_filter(LAB_ALL, FILTER, pakai_periode=False)
        st.plotly_chart(C.tren(D.per_periode(lab_np), kode), use_container_width=True)
        st.caption("Masa awal = Okt 2023–Sep 2024, Menengah = Okt 2024–Sep 2025, Terkini = Okt 2025–Sep 2026 (perkiraan). "
                   "Periode dengan kurang dari 10 penyebutan disembunyikan. Filter periode tidak berlaku pada grafik ini.")

    st.subheader("Kutipan dari ulasan")
    st.caption("Teks asli persis seperti ditulis pengulas (termasuk salah ketik). Diurutkan dari periode terkini, "
               "lalu jumlah ‘suka’. Identitas pengulas tidak disimpan.")
    urut = st.radio("Tampilkan", ["Negatif", "Positif", "Netral", "Campuran"], horizontal=True)
    sen = {v: k for k, v in D.LABEL_SENT.items()}[urut]
    sub = (s[s["sentiment"] == sen].assign(_p=lambda d: d["periode"].map(D.PRIORITAS_PERIODE))
           .sort_values(["_p", "likes"], ascending=[True, False]))
    if sub.empty:
        st.caption("Tidak ada kutipan dengan sentimen ini.")
    for _, r in sub.head(40).iterrows():
        meta = f"{r['periode']} · {r['date_relative']} · {int(r['rating']) if pd.notna(r['rating']) else '–'}★ · {int(r['likes'])} suka · {r['place_name']}"
        if isinstance(r["issue_tags"], str):
            meta += f" · {r['issue_tags'].replace(';', ', ')}"
        st.markdown(kutipan_html(r["evidence"], meta), unsafe_allow_html=True)
        if ADA_TEKS:
            with st.expander("Ulasan lengkap", expanded=False):
                st.write(r["text_original"])
                if isinstance(r["text_translated"], str):
                    st.caption("Terjemahan Google: " + r["text_translated"])
    if len(sub) > 40:
        st.caption(f"Menampilkan 40 dari {len(sub)} kutipan. Semua kutipan ada di halaman Katalog Kutipan.")


def hal_pemicu():
    st.title("Pemicu Ketidakpuasan")
    info_filter()
    st.subheader("Keluhan dan penurunan bintang")
    t = D.ols_rating(LAB, TEKS)
    if t is None:
        st.info("Data terlalu sedikit untuk regresi dengan filter ini.")
    else:
        st.plotly_chart(C.ols(t), use_container_width=True)
        st.caption(f"Regresi linier bintang terhadap kombinasi aspek×sentimen (minimal 5 ulasan), n = {t.attrs['n']} ulasan, "
                   f"R² = {D.fmt(t.attrs['r2'], 2)}. Angka menunjukkan keterkaitan, bukan sebab-akibat.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Isi ulasan bintang 1–2")
        rendah = TEKS[TEKS["rating"] <= 2]
        k = LAB[LAB["review_id"].isin(rendah["review_id"]) & LAB["sentiment"].isin(["negative", "mixed"])]
        vc = k.groupby("category")["review_id"].nunique().sort_values(ascending=False)
        if len(rendah) and len(vc):
            konek = rendah["review_id"].isin(LAB.loc[LAB["relevant"], "review_id"]).sum()
            st.caption(f"{len(rendah)} ulasan bintang 1–2 bertekstual; {konek} ({D.fmt(100 * konek / len(rendah), 0)}%) membahas konektivitas.")
            st.plotly_chart(C.bar_sederhana([D.NAMA[x] for x in vc.index], vc.values.tolist(), D.WARNA["negative"],
                                            "jumlah ulasan bintang 1–2"), use_container_width=True)
        else:
            st.caption("Tidak ada ulasan bintang 1–2 dengan filter ini.")
    with c2:
        st.subheader("Keluhan yang paling didukung pembaca")
        neg = SPANS[SPANS["sentiment"] == "negative"].sort_values("likes", ascending=False).drop_duplicates("review_id")
        neg = neg[neg["likes"] > 0].head(8)
        if neg.empty:
            st.caption("Tidak ada keluhan yang mendapat ‘suka’ dengan filter ini.")
        for _, r in neg.iterrows():
            st.markdown(kutipan_html(r["evidence"], f"{int(r['likes'])} suka · {D.NAMA[r['category']]} · {r['periode']}"),
                        unsafe_allow_html=True)


def hal_katalog():
    st.title("Katalog Kutipan")
    st.markdown("Seluruh kutipan yang menjadi dasar penilaian, dalam **teks asli**."
                + (" Pilih satu baris untuk membaca ulasan lengkapnya." if ADA_TEKS else ""))
    info_filter()
    c = st.columns([2, 2, 2, 3])
    asp = c[0].multiselect("Aspek", [D.NAMA[a] for a in D.ASPEK], placeholder="Semua aspek")
    sen = c[1].multiselect("Sentimen", list(D.LABEL_SENT.values()), placeholder="Semua sentimen")
    semua_tag = sorted({t for v in SPANS["issue_tags"].dropna() for t in v.split(";") if t})
    tag = c[2].multiselect("Jenis masalah", semua_tag, placeholder="Semua")
    cari = c[3].text_input("Cari kata", placeholder="mis. parkir inap, damri, gelap")
    df = (SPANS.assign(_p=SPANS["periode"].map(D.PRIORITAS_PERIODE))
          .sort_values(["_p", "likes"], ascending=[True, False]))
    df["issue_tags"] = df["issue_tags"].fillna("").str.replace(";", ", ")
    df["Aspek"] = df["category"].map(D.NAMA)
    df["Sentimen"] = df["sentiment"].map(D.LABEL_SENT)
    if asp:
        df = df[df["Aspek"].isin(asp)]
    if sen:
        df = df[df["Sentimen"].isin(sen)]
    if tag:
        df = df[df["issue_tags"].apply(lambda v: any(t in v.split(", ") for t in tag))]
    if cari:
        cocok = df["evidence"].str.contains(cari, case=False, na=False)
        if ADA_TEKS:
            cocok |= df["text_original"].str.contains(cari, case=False, na=False)
        df = df[cocok]
    tampil = df[["Aspek", "Sentimen", "evidence", "issue_tags", "periode", "rating", "likes", "place_name", "review_id"]].rename(
        columns={"evidence": "Kutipan (teks asli)", "issue_tags": "Jenis masalah", "periode": "Periode", "rating": "Bintang",
                 "likes": "Suka", "place_name": "Listing"}).reset_index(drop=True)
    st.caption(f"{len(tampil)} kutipan")
    pilih = st.dataframe(tampil.drop(columns="review_id"), hide_index=True, use_container_width=True, height=460,
                         on_select="rerun" if ADA_TEKS else "ignore", selection_mode="single-row",
                         column_config={"Kutipan (teks asli)": st.column_config.TextColumn(width="large"),
                                        "Bintang": st.column_config.NumberColumn(format="%d★")})
    baris = pilih.selection.rows if ADA_TEKS and pilih and pilih.selection else []
    if baris:
        r = df.reset_index(drop=True).iloc[baris[0]]
        st.markdown(f"<div class='kini'><b>Ulasan lengkap</b> · {r['place_name']} · {r['date_relative']} · "
                    f"{int(r['rating']) if pd.notna(r['rating']) else '–'}★ · {int(r['likes'])} suka<br><br>{r['text_original']}</div>",
                    unsafe_allow_html=True)
        if isinstance(r["text_translated"], str):
            st.caption("Terjemahan Google: " + r["text_translated"])
    st.download_button("Unduh hasil filter (CSV)", tampil.to_csv(index=False).encode("utf-8"), "katalog_kutipan.csv", "text/csv")


def hal_kebijakan():
    st.title("Konteks Kebijakan")
    st.markdown("Peristiwa resmi dan pemberitaan yang membantu menjelaskan kondisi saat ini. Kecocokan waktu dengan isi "
                "ulasan **bukan bukti sebab-akibat**, karena tanggal ulasan hanya perkiraan.")
    ev = DATA["events"].copy()
    kat = st.multiselect("Kategori", sorted(ev["kategori"].unique()), placeholder="Semua kategori")
    if kat:
        ev = ev[ev["kategori"].isin(kat)]
    st.dataframe(ev.rename(columns={"date": "Tanggal", "event": "Peristiwa", "kategori": "Kategori",
                                    "aspek_terkait": "Aspek", "sumber": "Sumber", "status": "Status"}),
                 hide_index=True, use_container_width=True,
                 column_config={"Sumber": st.column_config.LinkColumn(display_text="buka sumber"),
                                "Peristiwa": st.column_config.TextColumn(width="large")})
    st.subheader("Apa artinya bagi kondisi sekarang")
    poin = [
        ("Akses tol tidak permanen", "Exit Gedebage KM 149 awalnya hanya buka 07.00–17.00; perpanjangan jam dan akses KM 149 A/151 A "
         "hanya untuk masa liburan, dan exit sempat ditutup (Jan 2024). Ini menjelaskan keluhan jalan yang tidak mereda."),
        ("Parkir: kapasitas kecil, tarif membingungkan", "Kapasitas resmi hanya 95 lot mobil (Halim 630). Tarif resmi selalu punya "
         "batas maksimal harian, tetapi pengulas melaporkan sebaliknya: tanda informasi tarif belum tersampaikan jelas."),
        ("Konflik ojek mereda setelah area pick-up resmi", "Insiden pemalakan ojol oleh opang (Okt 2023), lalu area pick-up "
         "transportasi daring disiapkan (Feb 2024). Keluhan opang tidak muncul lagi setelah masa awal."),
        ("Efek Padalarang", "KA Feeder gratis Padalarang–Bandung beroperasi sejak 18 Okt 2023; Tegalluar tidak punya layanan setara."),
    ]
    for j, isi in poin:
        st.markdown(f"<div class='konteks' style='margin-bottom:.6rem'><b>{j}.</b> {isi}</div>", unsafe_allow_html=True)


def hal_metode():
    st.title("Data & Metode")
    st.subheader("Sumber data: lima listing Google Maps")
    li = DATA["listing"]
    tab = pd.DataFrame({"Listing": li["place_name"], "Tautan": li["short_url"], "Ulasan terkumpul": li["ulasan_terkumpul"],
                        "Koordinat": li["lat"].round(5).astype(str) + ", " + li["lng"].round(5).astype(str),
                        "ID tempat Google": li["feature_id"]})
    st.dataframe(tab, hide_index=True, use_container_width=True,
                 column_config={"Tautan": st.column_config.LinkColumn()})
    st.caption("Ulasan terkumpul = jumlah ulasan yang diambil pada 25 September 2026 (bertekstual + hanya bintang). "
               "Kelima titik berjarak 23–206 m (kompleks stasiun yang sama); tidak ada ulasan ganda antar-listing. "
               "Nama, foto, dan tautan profil pengulas tidak disimpan.")
    st.subheader("Cara kerja analisis")
    langkah = [
        ("Mengumpulkan", "Semua ulasan dari lima listing (1.191; 673 bertekstual), beserta bintang, tanggal relatif, ‘suka’, foto."),
        ("Memilah", "Mengenali bahasa, memecah kalimat menjadi klausa, menyaring ulasan yang mungkin menyinggung transportasi. "
                    "Pengecekan: tidak ada ulasan relevan yang tersaring keluar."),
        ("Menandai", "Setiap ulasan ditandai relevan/tidak, aspek, sentimen, kutipan bukti, dan jenis masalah oleh AI dalam dua putaran "
                     "terpisah; 35 perbedaan diputuskan satu per satu."),
        ("Menghitung", "Persentase per aspek, rentang ketidakpastian (Wilson), perubahan antar-periode, regresi bintang (OLS, HC3)."),
        ("Menafsirkan", "Membaca ulang 447 kutipan dan mencocokkan dengan pengumuman resmi dan pemberitaan."),
    ]
    for i, (j, isi) in enumerate(langkah, 1):
        st.markdown(f"**{i}. {j}.** {isi}")
    st.subheader("Kualitas label")
    c = st.columns(4)
    metrik(c[0], "Kesepakatan relevansi", "0,99", "kappa antar-putaran AI")
    metrik(c[1], "Kesepakatan sentimen", "0,94", "kappa antar-putaran AI")
    metrik(c[2], "Model pembanding: aspek", "0,61", "F1 terhadap label")
    metrik(c[3], "Model pembanding: sentimen", "0,43", "macro-F1 terhadap label")
    st.markdown("<div class='catatan'><b>Keterbatasan.</b> Label belum dicocokkan dengan penilaian manusia (kesepakatan tinggi antar-putaran "
                "berasal dari model yang sama, jadi bukan bukti akurasi). 74% ulasan konektivitas hanya bertanggal “setahun/2 tahun lalu”. "
                "Pengulas Google tidak mewakili seluruh penumpang. Sebagian besar aspek punya kurang dari 75 penyebutan.</div>",
                unsafe_allow_html=True)


def hal_unduhan():
    st.title("Unduhan")
    st.markdown("Laporan lengkap dan data pendukung.")
    berkas = [
        ("Laporan lengkap (Word)", "output/Laporan_Konektivitas_Whoosh_Tegalluar.docx",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("Laporan lengkap (PDF)", "output/Laporan_Konektivitas_Whoosh_Tegalluar.pdf", "application/pdf"),
        ("Semua tabel analisis (Excel, 24 lembar)", "output/whoosh_absa_hasil.xlsx",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("Label per ulasan × aspek (CSV)", "data/processed/final_labels.csv", "text/csv"),
        ("Linimasa kebijakan (CSV)", "config/events.csv", "text/csv"),
    ]
    for judul, rel, mime in berkas:
        p = D.ROOT / rel
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"**{judul}**  \n`{rel}`")
        if p.exists():
            c2.download_button("Unduh", p.read_bytes(), p.name, mime, key=rel, use_container_width=True)
        else:
            c2.caption("berkas belum ada")


pg = st.navigation([
    st.Page(hal_ringkasan, title="Ringkasan", icon=":material/home:", default=True),
    st.Page(hal_aspek, title="Aspek & Sentimen", icon=":material/bar_chart:"),
    st.Page(hal_terkini, title="Fenomena Terkini", icon=":material/trending_up:"),
    st.Page(hal_tema, title="Detail Tema", icon=":material/search:"),
    st.Page(hal_pemicu, title="Pemicu Ketidakpuasan", icon=":material/star_half:"),
    st.Page(hal_katalog, title="Katalog Kutipan", icon=":material/format_quote:"),
    st.Page(hal_kebijakan, title="Konteks Kebijakan", icon=":material/gavel:"),
    st.Page(hal_metode, title="Data & Metode", icon=":material/info:"),
    st.Page(hal_unduhan, title="Unduhan", icon=":material/download:"),
])
pg.run()
