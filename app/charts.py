"""Grafik Plotly untuk dashboard. Warna polaritas mengikuti laporan:
negatif merah, positif biru, netral abu-abu (titik tengah), campuran kuning."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from data import KET_PERIODE, LABEL_SENT, SENT, URUT_PERIODE, WARNA

TEKS, TEKS2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BIRU, ABU_MUDA = "#2a78d6", "#b7b6b0"
FONT = dict(family="Source Sans Pro, Calibri, sans-serif", size=13, color=TEKS)


def gaya(fig: go.Figure, tinggi: int = 420, legenda: bool = True) -> go.Figure:
    fig.update_layout(height=tinggi, font=FONT, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=10, r=20, t=30, b=10), showlegend=legenda,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      hoverlabel=dict(bgcolor="white", font_size=13))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=TEKS2, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, linecolor=GRID)
    return fig


def komposisi(t: pd.DataFrame) -> go.Figure:
    """Bar 100% bertumpuk per aspek: negatif di kiri, positif di kanan."""
    t = t.sort_values("Net")
    fig = go.Figure()
    for s in SENT:
        lab = LABEL_SENT[s]
        fig.add_bar(y=t["Aspek"], x=t[f"% {lab}"], name=lab, orientation="h", marker_color=WARNA[s],
                    marker_line=dict(color="white", width=1.5), customdata=t[[lab, "n"]].values,
                    text=[f"{v:.0f}%" if v >= 9 else "" for v in t[f"% {lab}"]], textposition="inside",
                    insidetextanchor="middle",
                    hovertemplate=f"<b>%{{y}}</b><br>{lab}: %{{x:.1f}}% (%{{customdata[0]}} dari %{{customdata[1]}})<extra></extra>")
    fig.update_layout(barmode="stack", xaxis=dict(title="% penyebutan", range=[0, 100]),
                      yaxis=dict(ticksuffix="  "))
    for y, n in zip(t["Aspek"], t["n"]):
        fig.add_annotation(x=100, y=y, text=f"n={n}", showarrow=False, xanchor="left", xshift=6,
                           font=dict(size=11, color=TEKS2))
    gaya(fig, tinggi=60 + 38 * len(t))
    fig.update_layout(margin=dict(r=70))
    return fig


def net_sentiment(t: pd.DataFrame, min_n: int = 10) -> go.Figure:
    t = t.sort_values("Net")
    warna = [WARNA["negative"] if v < 0 else WARNA["positive"] for v in t["Net"]]
    kecil = t["n"] < min_n
    fig = go.Figure(go.Scatter(
        x=t["Net"], y=t["Aspek"], mode="markers",
        marker=dict(size=12, color=["white" if k else w for k, w in zip(kecil, warna)],
                    line=dict(color=warna, width=2)),
        error_x=dict(type="data", symmetric=False, array=t["Net_hi"] - t["Net"], arrayminus=t["Net"] - t["Net_lo"],
                     color="#9a9994", thickness=2, width=0),
        customdata=np.stack([t["Net_lo"], t["Net_hi"], t["n"]], axis=1),
        hovertemplate="<b>%{y}</b><br>Net: %{x:+.0f}<br>CI 95%: %{customdata[0]:+.0f} s.d. %{customdata[1]:+.0f}"
                      "<br>n = %{customdata[2]}<extra></extra>"))
    fig.add_vline(x=0, line_color=TEKS2, line_width=1)
    fig.update_xaxes(range=[-105, 105], title="net sentiment = % positif − % negatif (garis = CI 95%; titik berongga: n < 10)")
    return gaya(fig, tinggi=60 + 38 * len(t), legenda=False)


def banding_periode(pp: pd.DataFrame, awal: str = "Masa awal", akhir: str = "Terkini") -> go.Figure:
    a = pp[pp["Periode"] == awal].set_index("Aspek")
    b = pp[pp["Periode"] == akhir].set_index("Aspek")
    urut = b["Porsi %"].sort_values().index
    fig = go.Figure()
    fig.add_bar(y=urut, x=a.loc[urut, "Porsi %"], name=f"{awal}, {KET_PERIODE[awal]} ({int(a['total_periode'].iloc[0])} penyebutan)",
                orientation="h", marker_color=ABU_MUDA, customdata=a.loc[urut, ["n", "negatif"]].values,
                hovertemplate="<b>%{y}</b><br>Porsi: %{x:.1f}%<br>%{customdata[0]} penyebutan, %{customdata[1]} negatif<extra></extra>")
    fig.add_bar(y=urut, x=b.loc[urut, "Porsi %"], name=f"{akhir}, {KET_PERIODE[akhir]} ({int(b['total_periode'].iloc[0])} penyebutan)",
                orientation="h", marker_color=BIRU, customdata=b.loc[urut, ["n", "negatif"]].values,
                text=[f"{v:.0f}% · {ng}/{n} neg" if n else "0%" for v, n, ng in
                      zip(b.loc[urut, "Porsi %"], b.loc[urut, "n"], b.loc[urut, "negatif"])],
                textposition="outside", textfont=dict(size=11, color=TEKS2),
                hovertemplate="<b>%{y}</b><br>Porsi: %{x:.1f}%<br>%{customdata[0]} penyebutan, %{customdata[1]} negatif<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05,
                      xaxis=dict(title="porsi dari seluruh penyebutan pada periode tsb (%)",
                                 range=[0, max(5, float(b["Porsi %"].max()), float(a["Porsi %"].max())) * 1.35]),
                      legend=dict(traceorder="reversed"))
    return gaya(fig, tinggi=520)


# Posisi label titik di matriks prioritas (menghindari tabrakan antar-label yang berdekatan)
POSISI_LABEL = {"Jarak & lokasi": "bottom center", "Parkir & antar-jemput": "top left",
                "Akses jalan & macet": "bottom right", "Konektivitas umum": "bottom center", "Ojol": "top right"}


def prioritas(t: pd.DataFrame) -> go.Figure:
    med = float(t["n"].median())
    warna = [WARNA["negative"] if v < 0 else WARNA["positive"] for v in t["Net"]]
    fig = go.Figure(go.Scatter(
        x=t["n"], y=t["Net"], mode="markers+text", text=t["Aspek"],
        textposition=[POSISI_LABEL.get(a, "top right") for a in t["Aspek"]],
        textfont=dict(size=12), marker=dict(size=14, color=warna, line=dict(color="white", width=2)),
        hovertemplate="<b>%{text}</b><br>Volume: %{x} penyebutan<br>Net: %{y:+.0f}<extra></extra>"))
    fig.add_hline(y=0, line_color=TEKS2, line_width=1)
    fig.add_vline(x=med, line_color=TEKS2, line_width=1, line_dash="dash")
    xmax = float(t["n"].max()) * 1.3
    fig.add_annotation(x=xmax, y=-100, text="<b>PRIORITAS UTAMA</b><br>sering & negatif", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(color=WARNA["negative"], size=12))
    fig.add_annotation(x=xmax, y=100, text="<b>Pertahankan</b><br>sering & positif", showarrow=False,
                       xanchor="right", yanchor="top", font=dict(color=WARNA["positive"], size=12))
    fig.update_xaxes(range=[0, xmax], title=f"volume (penyebutan); garis putus = median {med:.0f}")
    fig.update_yaxes(range=[-110, 110], title="net sentiment")
    return gaya(fig, tinggi=520, legenda=False)


def pareto(t: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=t["Aspek"], y=t["Keluhan"], marker_color=WARNA["negative"],
        text=[f"{n}<br>kum. {c:.0f}%" for n, c in zip(t["Keluhan"], t["Kumulatif %"])], textposition="outside",
        textfont=dict(size=11, color=TEKS2),
        hovertemplate="<b>%{x}</b><br>%{y} keluhan<extra></extra>"))
    fig.update_yaxes(title="jumlah keluhan (negatif + campuran)", range=[0, float(t["Keluhan"].max()) * 1.3])
    fig.update_xaxes(tickangle=-30)
    return gaya(fig, tinggi=440, legenda=False)


def tren(pp: pd.DataFrame, kode: str, min_n: int = 10) -> go.Figure:
    g = pp[pp["kode"] == kode].set_index("Periode").reindex(URUT_PERIODE)
    ok = g["n"] >= min_n
    y = g["% negatif"].where(ok)
    fig = go.Figure(go.Scatter(
        x=URUT_PERIODE, y=y, mode="lines+markers", line=dict(color=WARNA["negative"], width=3),
        marker=dict(size=11), connectgaps=False,
        error_y=dict(type="data", symmetric=False, array=(g["hi"] - g["% negatif"]).where(ok),
                     arrayminus=(g["% negatif"] - g["lo"]).where(ok), color="#e8a3a2", thickness=2),
        customdata=g[["n", "negatif"]].values,
        hovertemplate="<b>%{x}</b><br>%{y:.0f}% negatif (%{customdata[1]} dari %{customdata[0]})<extra></extra>"))
    for per, n, o in zip(URUT_PERIODE, g["n"], ok):
        fig.add_annotation(x=per, y=108, text=f"n={int(n)}" + ("" if o else " (disembunyikan)"),
                           showarrow=False, font=dict(size=11, color=TEKS2))
    fig.update_yaxes(range=[0, 115], title="% negatif")
    fig.update_xaxes(tickvals=URUT_PERIODE, ticktext=[f"{p}<br><span style='font-size:11px'>{KET_PERIODE[p]}</span>"
                                                      for p in URUT_PERIODE])
    return gaya(fig, tinggi=350, legenda=False)


def heatmap(m: pd.DataFrame, judul_x: str = "", tinggi: int = 460) -> go.Figure:
    skala = [[0, "#f4f8fd"], [0.35, "#9ec5f4"], [0.7, "#2a78d6"], [1, "#104281"]]
    z = m.values.astype(float)
    teks = np.where(z > 0, z.astype(int).astype(str), "")
    fig = go.Figure(go.Heatmap(z=z, x=list(m.columns), y=list(m.index), colorscale=skala, text=teks,
                               texttemplate="%{text}", textfont=dict(size=11), xgap=2, ygap=2,
                               hovertemplate="%{y} × %{x}: %{z:.0f}<extra></extra>", showscale=False))
    fig.update_xaxes(tickangle=-40, title=judul_x, showgrid=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return gaya(fig, tinggi=tinggi, legenda=False)


def ols(t: pd.DataFrame) -> go.Figure:
    lab = [f"{a} · {s.lower()} (n={int(n)})" for a, s, n in zip(t["Aspek"], t["Sentimen"], t["n"])]
    warna = [WARNA["negative"] if s == "Negatif" else WARNA["positive"] for s in t["Sentimen"]]
    fig = go.Figure(go.Scatter(
        x=t["koef"], y=lab, mode="markers", marker=dict(size=11, color=warna, line=dict(color="white", width=2)),
        error_x=dict(type="data", symmetric=False, array=t["hi"] - t["koef"], arrayminus=t["koef"] - t["lo"],
                     color="#9a9994", thickness=2, width=0),
        customdata=np.stack([t["lo"], t["hi"], t["p"]], axis=1),
        hovertemplate="<b>%{y}</b><br>%{x:+.2f} bintang<br>CI 95%: %{customdata[0]:+.2f} s.d. %{customdata[1]:+.2f}"
                      "<br>p = %{customdata[2]:.3f}<extra></extra>"))
    fig.add_vline(x=0, line_color=TEKS2, line_width=1)
    fig.update_xaxes(title="perubahan bintang dibanding ulasan tanpa aspek×sentimen tsb (CI 95%, HC3)")
    return gaya(fig, tinggi=60 + 34 * len(t), legenda=False)


def bar_sederhana(label, nilai, warna: str = BIRU, judul_x: str = "", tinggi: int | None = None) -> go.Figure:
    fig = go.Figure(go.Bar(x=nilai, y=label, orientation="h", marker_color=warna, text=nilai,
                           textposition="outside", hovertemplate="%{y}: %{x}<extra></extra>"))
    fig.update_xaxes(title=judul_x, range=[0, max(nilai) * 1.25 if len(nilai) else 1])
    fig.update_yaxes(autorange="reversed")
    return gaya(fig, tinggi=tinggi or 60 + 30 * len(label), legenda=False)
