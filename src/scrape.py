"""Tahap 1 — Scraping review Google Maps (gratis, tanpa API) dengan Playwright + Chromium.

Pemakaian:
  python src/scrape.py --login          # sekali saja: login Google manual di jendela browser
  python src/scrape.py --limit 20       # uji coba link pertama (disimpan di data/raw/sample/)
  python src/scrape.py                  # semua link, resumable
  python src/scrape.py --only 2         # hanya link ke-2 (1-5)
  python src/scrape.py --merge-only     # gabungkan CSV per tempat -> data/raw/all_reviews.csv
  python src/scrape.py --update         # INKREMENTAL: ambil review baru saja (urut Terbaru, berhenti
                                        # setelah 20 review lama berturut-turut); log di data/raw/runs/
  python src/scrape.py --update --full  # inkremental + scroll sampai habis untuk mendeteksi review hilang

Mode --update menambah kolom first_seen (waktu run saat review pertama terlihat) dan seen_after
(waktu run sebelumnya untuk listing itu): review baru pasti ditulis di antara keduanya.

Catatan:
- Tanpa login, Google Maps kini hanya menampilkan ~5 review ("tampilan terbatas").
  Sesi login disimpan di folder lokal .browser_profile/ (JANGAN dibagikan / di-commit).
- Privasi (UU PDP): nama reviewer, foto, dan link profil TIDAK disimpan.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote_plus

import pandas as pd
from playwright.async_api import BrowserContext, Page, async_playwright

# --------------------------------------------------------------------------- konfigurasi
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROFILE_DIR = ROOT / ".browser_profile"
STATE_FILE = RAW / "_scrape_state.json"

LINKS = [
    "https://maps.app.goo.gl/RVeUwckH69V2AXit8",
    "https://maps.app.goo.gl/qSH4xZkqkBoF3FzP7",
    "https://maps.app.goo.gl/tWh3hbaB6Ypk5Zqt5",
    "https://maps.app.goo.gl/sT2KabtsJ7ywaAQY9",
    "https://maps.app.goo.gl/vddqzKDfdVzJMnEh7",
]

# Selektor: tiap entri adalah daftar kandidat, dicoba berurutan (class CSS dulu,
# lalu fallback berbasis role/aria-label/teks). Perbarui di sini jika Google mengubah DOM.
SEL = {
    "tab_ulasan": ['button[role="tab"][aria-label^="Ulasan"]',
                   'button[role="tab"][aria-label^="Reviews"]',
                   'button[role="tab"]:has-text("Ulasan")'],
    "total_ulasan": ["div.jANrlb .fontBodySmall", 'button[jsaction*="reviewChart"]'],
    "tombol_urutkan": ['button[aria-label="Urutkan ulasan"]', 'button[aria-label="Sort reviews"]',
                       'button[data-value="Urutkan"]'],
    "menu_terbaru": ['[role="menuitemradio"]:has-text("Terbaru")', '[role="menuitemradio"]:has-text("Newest")',
                     'div[role="menu"] >> text=Terbaru'],
    "panel_scroll": ["div.m6QErb.DxyBCb.kA9KIf.dS8AEf", 'div[role="main"] div[tabindex="-1"].m6QErb'],
    "tutup_modal_login": ['button:has-text("Tutup")', 'button:has-text("Close")'],
    "consent_terima": ['button[aria-label*="Terima semua"]', 'button[aria-label*="Accept all"]',
                       'form[action*="consent"] button'],
}
# Dipakai di dalam JavaScript (querySelector), jadi berupa string CSS murni.
JS_SEL = {
    "review": "div.jftiEf[data-review-id], div[data-review-id][aria-label]",
    "teks": "span.wiI7pd",
    "blok_teks": "div.MyEned",
    "lainnya": 'button.w8nwRe[aria-expanded="false"], button[aria-label="Lihat lainnya"], button[aria-label="See more"]',
    "rating": 'span.kvMYJc[role="img"], span[role="img"][aria-label*="bintang"], span[role="img"][aria-label*="star"]',
    "tanggal": "span.rsqaWe, span.xRkPPb",
    "suka": "button.gllhef span.pkWtMe, button[aria-label^='Suka'] span",
    "foto": "button.Tya61d, button[data-photo-index]",  # BUKAN foto profil (button.WEBjve)
    "balasan_pemilik": "div.CDe7pd",
}
RE_VERSI_ASLI = r"(Lihat (versi |teks )?asli|Tampilkan (versi )?asli|See original|Show original)"
RE_TAMPILAN_TERBATAS = r"(tampilan terbatas|limited view)"

JEDA = (1.0, 3.0)  # detik, jeda acak antar-aksi
MAKS_SCROLL_KOSONG = 3
MAKS_KENAL_BERTURUT = 20  # mode --update: berhenti setelah N review lama berturut-turut
RUNS = RAW / "runs"
MIN_PANJANG_NEAR_DUP = 20  # karakter; teks lebih pendek tidak dicek near-duplicate


# --------------------------------------------------------------------------- utilitas
def slugify(teks: str) -> str:
    teks = unicodedata.normalize("NFKD", teks).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", teks.lower()).strip("-")


async def jeda() -> None:
    await asyncio.sleep(random.uniform(*JEDA))


async def cari(page: Page, kunci: str, timeout: int = 0):
    """Kembalikan locator pertama yang ada dari daftar selektor SEL[kunci], atau None."""
    for _ in range(max(1, timeout // 500)):
        for s in SEL[kunci]:
            loc = page.locator(s)
            if await loc.count():
                return loc.first
        if timeout:
            await page.wait_for_timeout(500)
    return None


def info_dari_url(url: str) -> dict:
    """Ambil nama tempat, feature id, dan koordinat dari URL final Google Maps."""
    nama = re.search(r"/maps/place/([^/@]+)", url)
    fid = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    # !3d/!4d = koordinat titik tempat; @lat,lng = pusat peta (fallback)
    koord = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url) or re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    return {
        "place_name": unquote_plus(nama.group(1)) if nama else None,
        "feature_id": fid.group(1) if fid else None,
        "lat": float(koord.group(1)) if koord else None,
        "lng": float(koord.group(2)) if koord else None,
    }


def tambah_hl(url: str) -> str:
    url = re.sub(r"([?&])hl=[^&]*&?", r"\1", url).rstrip("?&")
    return url + ("&" if "?" in url else "?") + "hl=id"


# --------------------------------------------------------------------------- tanggal
SATUAN = {
    "menit": ("day", 0), "minute": ("day", 0), "jam": ("day", 0), "hour": ("day", 0),
    "hari": ("day", 1), "day": ("day", 1), "kemarin": ("day", 1), "yesterday": ("day", 1),
    "minggu": ("week", 7), "week": ("week", 7),
    "bulan": ("month", 30), "month": ("month", 30),
    "tahun": ("year", 365), "year": ("year", 365),
}


def estimasi_tanggal(relatif: str | None, scraped_at: datetime) -> tuple[str | None, str | None]:
    """'2 bulan lalu' -> (tanggal perkiraan ISO, presisi day/week/month/year)."""
    if not relatif:
        return None, None
    t = relatif.lower().replace("diedit", "").replace("edited", "").strip()
    m = re.search(r"(\d+|se|a|an|one)\s*-?\s*(menit|jam|hari|minggu|bulan|tahun|minute|hour|day|week|month|year)", t)
    if m:
        angka = 1 if m.group(1) in ("se", "a", "an", "one") else int(m.group(1))
        presisi, hari = SATUAN[m.group(2)]
    elif "kemarin" in t or "yesterday" in t:
        angka, (presisi, hari) = 1, SATUAN["kemarin"]
    else:
        return None, None
    tanggal = scraped_at - timedelta(days=angka * hari)
    return tanggal.date().isoformat(), presisi


# --------------------------------------------------------------------------- JavaScript di halaman
# Klik semua "Lainnya" (teks penuh).
JS_KLIK_LAINNYA = r"""
(S) => { let n = 0; document.querySelectorAll(S.review).forEach(el =>
  el.querySelectorAll(S.lainnya).forEach(b => { b.click(); n++; })); return n; }
"""

# Jika ada "Lihat versi asli": simpan teks terjemahan (yang sudah ter-expand) di data-atribut,
# lalu klik tombolnya agar teks ASLI yang tampil. Kartu yang masih terpotong dilewati dulu.
JS_KLIK_ASLI = r"""
([S, reAsli]) => {
  const re = new RegExp(reAsli, 'i');
  let n = 0;
  document.querySelectorAll(S.review).forEach(el => {
    if (el.dataset.asliDiklik || el.querySelector(S.lainnya)) return;
    const tombol = Array.from(el.querySelectorAll('button, span[role="button"]'))
                        .find(b => re.test(b.innerText || b.getAttribute('aria-label') || ''));
    if (tombol) {
      el.dataset.terjemahan = el.querySelector(S.teks)?.innerText ?? '';
      el.dataset.asliDiklik = '1';
      tombol.click();
      n++;
    }
  });
  return n;
}
"""


async def expand_semua(page: Page) -> None:
    """Urutan: Lainnya -> (tunggu) -> Lihat versi asli -> (tunggu) -> Lainnya lagi -> (tunggu)."""
    if await page.evaluate(JS_KLIK_LAINNYA, JS_SEL):
        await page.wait_for_timeout(800)
    if await page.evaluate(JS_KLIK_ASLI, [JS_SEL, RE_VERSI_ASLI]):
        await page.wait_for_timeout(1500)
        if await page.evaluate(JS_KLIK_LAINNYA, JS_SEL):
            await page.wait_for_timeout(800)


JS_EKSTRAK = r"""
(S) => Array.from(document.querySelectorAll(S.review))
  .filter(el => el.querySelector(S.tanggal))            // hanya kartu review utama
  .map(el => {
    const q = (s) => el.querySelector(s);
    const teks = q(S.blok_teks)?.querySelector(S.teks)?.innerText ?? q(S.teks)?.innerText ?? null;
    const pemilik = q(S.balasan_pemilik);
    const suka = q(S.suka);
    return {
      review_id: el.getAttribute('data-review-id'),
      rating_label: q(S.rating)?.getAttribute('aria-label') ?? '',
      date_relative: q(S.tanggal)?.innerText?.trim() ?? null,
      text_displayed: teks,
      text_translated_saved: el.dataset.terjemahan ?? null,
      masih_terpotong: !!el.querySelector(S.lainnya),
      lang_google: q(S.blok_teks)?.getAttribute('lang') ?? null,
      likes: suka ? suka.innerText.trim() : '',
      owner_response: pemilik ? (pemilik.querySelector(S.teks)?.innerText ?? pemilik.innerText) : null,
      has_photo: !!el.querySelector(S.foto),
    };
  })
"""


def rapikan(r: dict, place: dict, scraped_at: datetime) -> dict:
    """Ubah hasil mentah JS menjadi satu baris CSV sesuai skema Tahap 1."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", r["rating_label"] or "")
    tgl, presisi = estimasi_tanggal(r["date_relative"], scraped_at)
    diterjemahkan = r["text_translated_saved"] is not None
    return {
        "place_name": place["place_name"],
        "place_url": place["place_url"],
        "review_id": r["review_id"],
        "rating": float(m.group(1).replace(",", ".")) if m else None,
        "date_relative": r["date_relative"],
        "date_estimated": tgl,
        "date_precision": presisi,
        # Jika tombol "Lihat versi asli" diklik: teks sekarang = asli, teks tersimpan = terjemahan.
        "text_original": r["text_displayed"],
        "text_translated": r["text_translated_saved"] if diterjemahkan else None,
        "lang_google": r["lang_google"],
        "likes": int(re.sub(r"\D", "", r["likes"])) if re.search(r"\d", r["likes"] or "") else 0,
        "owner_response": r["owner_response"],
        "has_photo": r["has_photo"],
        "text_truncated": r["masih_terpotong"],
        "scraped_at": scraped_at.isoformat(timespec="seconds"),
        "first_seen": scraped_at.isoformat(timespec="seconds"),
        "seen_after": None,  # diisi pada mode --update (waktu run sebelumnya)
    }


# --------------------------------------------------------------------------- langkah-langkah
async def resolve(page: Page, short_url: str) -> dict:
    """Buka short link, tunggu redirect ke URL /maps/place/, catat nama, URL, koordinat."""
    await page.goto(short_url, wait_until="domcontentloaded")
    await tangani_consent(page)
    await page.wait_for_url(re.compile(r"/maps/place/"), timeout=30000)
    await page.wait_for_timeout(1500)  # URL masih bisa berubah (zoom/koordinat)
    final = page.url
    info = info_dari_url(final)
    info.update(short_url=short_url, place_url=tambah_hl(final))
    return info


async def tangani_consent(page: Page) -> None:
    if "consent.google" in page.url:
        tombol = await cari(page, "consent_terima", timeout=5000)
        if tombol:
            await tombol.click()
            await page.wait_for_load_state("domcontentloaded")


async def tutup_modal_login(page: Page) -> None:
    tombol = await cari(page, "tutup_modal_login")
    if tombol and await tombol.is_visible():
        await tombol.click()
        await page.wait_for_timeout(500)


async def buka_ulasan(page: Page, place: dict) -> int | None:
    """Buka tab Ulasan, baca total ulasan di Google, lalu urutkan Terbaru."""
    for percobaan in range(3):
        await page.goto(place["place_url"], wait_until="domcontentloaded")
        await tangani_consent(page)
        tab = await cari(page, "tab_ulasan", timeout=15000)
        if tab:
            break
        print(f"   tab Ulasan belum muncul, muat ulang ({percobaan + 1}/3)")
    else:
        raise RuntimeError("Tab 'Ulasan' tidak ditemukan")
    await tab.click()
    await page.wait_for_selector(JS_SEL["review"], timeout=30000)
    await jeda()
    await tutup_modal_login(page)

    total = None
    el_total = await cari(page, "total_ulasan")
    if el_total:
        m = re.search(r"([\d.,]+)\s*(ulasan|review)", await el_total.inner_text())
        total = int(re.sub(r"[.,]", "", m.group(1))) if m else None

    urutkan = await cari(page, "tombol_urutkan")
    if urutkan:
        await urutkan.click()
        terbaru = await cari(page, "menu_terbaru", timeout=5000)
        if terbaru:
            await terbaru.click()
            await page.wait_for_timeout(2500)
        else:
            await tutup_modal_login(page)
            print("   ! Menu 'Terbaru' tidak muncul (biasanya karena belum login). Urutan default dipakai.")
    return total


async def scrape_tempat(page: Page, place: dict, limit: int | None, sudah_ada: set[str],
                        simpan_batch, lama: dict[str, dict] | None = None, update: bool = False,
                        full: bool = False, seen_after: str | None = None) -> dict:
    """Ambil review satu tempat.

    Mode biasa: scroll sampai habis, simpan review yang belum ada.
    Mode update: urutan Terbaru; berhenti setelah MAKS_KENAL_BERTURUT review lama berturut-turut
    (kecuali full=True). Review lama yang terlihat dibandingkan dengan data tersimpan (lama) untuk
    mencatat perubahan teks/rating/likes.
    """
    total_google = await buka_ulasan(page, place)
    terbatas = bool(re.search(RE_TAMPILAN_TERBATAS, await page.inner_text("body"), re.I))
    if terbatas:
        print("   ! Google menampilkan 'tampilan terbatas' (belum login): hanya sebagian kecil review"
              " yang bisa diambil. Jalankan: python src/scrape.py --login")
    print(f"   total ulasan menurut Google: {total_google}")

    scraped_at = datetime.now()
    hasil: dict[str, dict] = {}
    diproses: set[str] = set()  # review_id (baru maupun lama) yang sudah diperiksa
    berubah: list[dict] = []
    kenal_berturut = 0
    berhenti_dini = False
    scroll_kosong = 0
    while True:
        await expand_semua(page)
        baris_baru = []
        ada_kartu_baru = False
        for r in await page.evaluate(JS_EKSTRAK, JS_SEL):
            rid = r["review_id"]
            if not rid or rid in diproses or r["masih_terpotong"]:
                continue  # kartu terpotong ditunggu sampai "Lainnya" terbuka
            diproses.add(rid)
            ada_kartu_baru = True
            if rid in sudah_ada:
                kenal_berturut += 1
                if lama is not None and rid in lama:
                    sekarang = rapikan(dict(r), place, scraped_at)
                    for kol in ("text_original", "rating", "likes"):
                        a, b = lama[rid].get(kol), sekarang.get(kol)
                        if pd.isna(a) and b in (None, ""):
                            continue
                        if kol in ("rating", "likes"):
                            sama = not pd.isna(a) and b is not None and float(a) == float(b)
                        else:
                            sama = str(a) == str(b)
                        if not sama:
                            berubah.append({"review_id": rid, "place_name": place["place_name"], "kolom": kol,
                                            "lama": a, "baru": b,
                                            "terlihat": scraped_at.isoformat(timespec="seconds")})
                continue
            kenal_berturut = 0
            rec = rapikan(r, place, scraped_at)
            rec["seen_after"] = seen_after
            hasil[rid] = rec
            baris_baru.append(rec)
        if baris_baru:
            simpan_batch(baris_baru)
        if limit and len(hasil) >= limit:
            break
        if update and not full and kenal_berturut >= MAKS_KENAL_BERTURUT:
            berhenti_dini = True
            print(f"   berhenti: {MAKS_KENAL_BERTURUT} review lama berturut-turut")
            break
        scroll_kosong = 0 if ada_kartu_baru else scroll_kosong + 1
        if scroll_kosong >= MAKS_SCROLL_KOSONG:
            break
        await page.evaluate(
            "(sels) => { for (const s of sels) { const p = document.querySelector(s);"
            " if (p) { p.scrollTop = p.scrollHeight; return; } } }", SEL["panel_scroll"])
        await jeda()
        if ada_kartu_baru and len(diproses) // 100 != (len(diproses) - 1) // 100:
            print(f"   ... {len(diproses)} review diperiksa, {len(hasil)} baru")

    # Kartu yang masih terpotong di akhir (jarang): coba expand sekali lagi, lalu ambil apa adanya
    # (kolom text_truncated = True menandainya).
    await expand_semua(page)
    for r in await page.evaluate(JS_EKSTRAK, JS_SEL):
        rid = r["review_id"]
        if rid and rid not in diproses and rid not in sudah_ada and not (limit and len(hasil) >= limit):
            diproses.add(rid)
            rec = rapikan(r, place, scraped_at)
            rec["seen_after"] = seen_after
            hasil[rid] = rec
            simpan_batch([rec])
    hilang = sorted(sudah_ada - diproses) if (update and full and not terbatas) else []
    return {"total_google": total_google, "n_baru": len(hasil), "tampilan_terbatas": terbatas,
            "baru": list(hasil.values()), "berubah": berubah, "hilang": hilang,
            "n_diperiksa": len(diproses), "berhenti_dini": berhenti_dini,
            "scraped_at": scraped_at.isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- penyimpanan
KOLOM = ["place_name", "place_url", "review_id", "rating", "date_relative", "date_estimated",
         "date_precision", "text_original", "text_translated", "lang_google", "likes",
         "owner_response", "has_photo", "text_truncated", "scraped_at", "first_seen", "seen_after"]


def migrasi_kolom(path: Path) -> None:
    """CSV lama (sebelum mode --update) belum punya first_seen/seen_after.
    Data awal diberi first_seen = scraped_at dan seen_after kosong (= data baseline, tanggal tulis
    tidak diketahui)."""
    if not path.exists():
        return
    df = pd.read_csv(path, encoding="utf-8")
    if "first_seen" in df.columns:
        return
    df["first_seen"] = df["scraped_at"]
    df["seen_after"] = None
    df[KOLOM].to_csv(path, index=False, encoding="utf-8")
    print(f"   migrasi kolom first_seen/seen_after: {path.name} ({len(df)} baris)")


def tulis_append(path: Path, baris: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(baris, columns=KOLOM)
    df.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8")


def muat_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}


def simpan_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def normalisasi_dedup(teks) -> str:
    if not isinstance(teks, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", teks)).strip().lower()


def gabungkan(folder: Path, keluaran: Path) -> pd.DataFrame:
    """Gabungkan CSV per tempat, dedup review_id, tandai near-duplicate lintas listing."""
    file = sorted(p for p in folder.glob("*.csv") if p.name not in ("all_reviews.csv", "scrape_report.csv") and not p.name.startswith("_"))
    if not file:
        print("Tidak ada CSV per tempat untuk digabung.")
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(p, encoding="utf-8") for p in file], ignore_index=True)
    n0 = len(df)
    df = df.drop_duplicates("review_id", keep="first").reset_index(drop=True)
    print(f"Gabung {len(file)} file: {n0} baris -> {len(df)} setelah dedup review_id")

    # Near-duplicate: teks + rating + tanggal relatif sama, di listing BERBEDA.
    # Teks pendek generik ("Bagus", "Mantap") diabaikan karena kebetulan sama, bukan duplikat.
    teks_norm = df["text_original"].map(normalisasi_dedup)
    df["_kunci"] = teks_norm + "|" + df["rating"].astype(str) + "|" + df["date_relative"].astype(str)
    df["near_dup_group"] = None
    df["is_near_dup"] = False
    layak = teks_norm.str.len() >= MIN_PANJANG_NEAR_DUP
    i = 0
    for _, g in df[layak].groupby("_kunci"):
        if g["place_name"].nunique() < 2:
            continue
        df.loc[g.index, "near_dup_group"] = f"nd{i:04d}"
        # baris pertama per listing dianggap asli; salinan di listing lain ditandai
        df.loc[g.index[g["place_name"].duplicated() | (g.index != g.index[0])], "is_near_dup"] = True
        i += 1
    df = df.drop(columns="_kunci")
    df.to_csv(keluaran, index=False, encoding="utf-8")
    print(f"Near-duplicate lintas listing: {df['near_dup_group'].nunique()} grup,"
          f" {int(df['is_near_dup'].sum())} baris ditandai is_near_dup")
    print(f"Tersimpan: {keluaran.relative_to(ROOT)}")
    return df


def laporan_kelengkapan(state: dict, df: pd.DataFrame, keluaran: Path) -> None:
    baris = []
    for slug, s in state.items():
        n = int((df["place_name"] == s["place_name"]).sum()) if len(df) else 0
        tot = s.get("total_google")
        baris.append({"no": s["no"], "place_name": s["place_name"], "feature_id": s.get("feature_id"),
                      "lat": s.get("lat"), "lng": s.get("lng"), "n_scraped": n, "total_google": tot,
                      "kelengkapan_%": round(100 * n / tot, 1) if tot else None,
                      "selesai": s.get("selesai"), "tampilan_terbatas": s.get("tampilan_terbatas")})
    rep = pd.DataFrame(baris).sort_values("no")
    rep.to_csv(keluaran, index=False, encoding="utf-8")
    print("\n=== Kelengkapan scraping (per listing) ===")
    print(rep.to_string(index=False))
    fids = rep["feature_id"].dropna()
    if fids.duplicated().any():
        print("! Ada link yang menunjuk ke feature id yang SAMA:", fids[fids.duplicated()].tolist())


# --------------------------------------------------------------------------- main
async def buka_browser(p, headless: bool) -> BrowserContext:
    return await p.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=headless, locale="id-ID", timezone_id="Asia/Jakarta",
        viewport={"width": 1280, "height": 1000})


async def mode_login() -> None:
    async with async_playwright() as p:
        ctx = await buka_browser(p, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://accounts.google.com/ServiceLogin?hl=id&continue=https://www.google.com/maps")
        print("Silakan login di jendela browser. Setelah Google Maps terbuka, TUTUP jendela browser.")
        await page.wait_for_event("close", timeout=0)
        await ctx.close()
    print(f"Sesi tersimpan di {PROFILE_DIR.relative_to(ROOT)}/")


async def main_async(args) -> None:
    if args.login:
        await mode_login()
        return
    folder = RAW / "sample" if args.limit else RAW
    state = {} if args.limit else muat_state()
    targets = list(enumerate(LINKS, 1))
    if args.limit and not args.only:
        targets = targets[:1]  # uji coba: link pertama saja
    if args.only:
        targets = [t for t in targets if t[0] == args.only]

    laporan_run: list[dict] = []
    async with async_playwright() as p:
        ctx = await buka_browser(p, headless=args.headless)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        for no, link in targets:
            print(f"\n[{no}/{len(LINKS)}] {link}")
            place = await resolve(page, link)
            slug = slugify(place["place_name"] or f"tempat-{no}")
            print(f"   {place['place_name']}  ({place['lat']}, {place['lng']})  fid={place['feature_id']}")
            s = state.get(slug, {})
            if s.get("selesai") and not (args.force or args.update):
                print("   sudah selesai sebelumnya, dilewati (pakai --force untuk ulang)")
                continue
            path = folder / f"{slug}.csv"
            if args.limit and path.exists():
                path.unlink()
            lama = None
            if args.update:
                migrasi_kolom(path)
                lama = (pd.read_csv(path, encoding="utf-8").set_index("review_id").to_dict("index")
                        if path.exists() else {})
            sudah_ada = set(pd.read_csv(path, usecols=["review_id"])["review_id"]) if path.exists() else set()
            if sudah_ada:
                print(f"   {'update' if args.update else 'lanjutkan'}: {len(sudah_ada)} review sudah tersimpan")
            # seen_after = waktu pengambilan terakhir yang BERHASIL untuk listing ini: dari state (run
            # update sukses) atau, bila belum ada, waktu scraping terbaru di CSV listing tsb.
            seen_after = s.get("terakhir_update")
            if not seen_after and path.exists():
                kol = pd.read_csv(path, usecols=["scraped_at"])["scraped_at"].dropna()
                seen_after = kol.max() if len(kol) else None
            hasil = await scrape_tempat(page, place, args.limit, sudah_ada,
                                        simpan_batch=lambda b, pth=path: tulis_append(pth, b),
                                        lama=lama, update=args.update, full=args.full, seen_after=seen_after)
            if args.update:
                laporan_run.append({"slug": slug, "no": no, **place, **hasil})
            state[slug] = {"no": no, "short_url": link, **{k: place[k] for k in
                           ("place_name", "place_url", "feature_id", "lat", "lng")},
                           "total_google": hasil["total_google"],
                           "tampilan_terbatas": hasil["tampilan_terbatas"],
                           "selesai": not args.limit and not hasil["tampilan_terbatas"],
                           "diperbarui": datetime.now().isoformat(timespec="seconds"),
                           "terakhir_update": (hasil["scraped_at"] if not hasil["tampilan_terbatas"]
                                               else s.get("terakhir_update"))}
            if not args.limit:
                simpan_state(state)
            print(f"   +{hasil['n_baru']} review baru -> {path.relative_to(ROOT)}")
            await jeda()
        await ctx.close()

    df = gabungkan(folder, folder / "all_reviews.csv")
    laporan_kelengkapan(state, df, folder / "scrape_report.csv")
    if args.update:
        tulis_log_run(laporan_run, args.full)


def tulis_log_run(laporan: list[dict], full: bool) -> None:
    """Simpan log satu run inkremental: review baru, perubahan, review hilang, dan ringkasan."""
    waktu = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = RUNS / waktu
    folder.mkdir(parents=True, exist_ok=True)
    baru = [r for l in laporan for r in l["baru"]]
    berubah = [r for l in laporan for r in l["berubah"]]
    hilang = [{"review_id": rid, "place_name": l["place_name"]} for l in laporan for rid in l["hilang"]]
    pd.DataFrame(baru, columns=KOLOM).to_csv(folder / "new_reviews.csv", index=False, encoding="utf-8")
    pd.DataFrame(berubah, columns=["review_id", "place_name", "kolom", "lama", "baru", "terlihat"]).to_csv(
        folder / "changed.csv", index=False, encoding="utf-8")
    if full:
        pd.DataFrame(hilang, columns=["review_id", "place_name"]).to_csv(
            folder / "missing.csv", index=False, encoding="utf-8")
    ringkas = {"run": waktu, "mode": "full" if full else "cepat",
               "listing": [{"no": l["no"], "place_name": l["place_name"], "total_google": l["total_google"],
                            "baru": l["n_baru"], "diperiksa": l["n_diperiksa"], "berubah": len(l["berubah"]),
                            "hilang": len(l["hilang"]) if full else None, "berhenti_dini": l["berhenti_dini"],
                            "tampilan_terbatas": l["tampilan_terbatas"]} for l in laporan]}
    (folder / "summary.json").write_text(json.dumps(ringkas, ensure_ascii=False, indent=2), encoding="utf-8")
    idx = RUNS / "runs_index.csv"
    baris = pd.DataFrame([{"run": waktu, "mode": ringkas["mode"], "review_baru": len(baru),
                           "berubah": len(berubah), "hilang": len(hilang) if full else None,
                           "listing_terbatas": sum(l["tampilan_terbatas"] for l in laporan)}])
    baris.to_csv(idx, mode="a", header=not idx.exists(), index=False, encoding="utf-8")
    print(f"\n=== Run inkremental {waktu} ===")
    for l in ringkas["listing"]:
        print(f"  #{l['no']} {l['place_name']}: baru {l['baru']}, diperiksa {l['diperiksa']},"
              f" berubah {l['berubah']}" + (f", hilang {l['hilang']}" if full else "")
              + (" [TAMPILAN TERBATAS]" if l["tampilan_terbatas"] else ""))
    print(f"  Total: {len(baru)} review baru -> {folder.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, help="uji coba: maksimal N review (default link pertama saja)")
    ap.add_argument("--only", type=int, help="hanya link ke-N (1-5)")
    ap.add_argument("--force", action="store_true", help="ulangi tempat yang sudah selesai")
    ap.add_argument("--headless", action="store_true", help="sembunyikan browser (default: tampil)")
    ap.add_argument("--login", action="store_true", help="buka browser untuk login Google manual (sekali)")
    ap.add_argument("--merge-only", action="store_true", help="hanya gabungkan CSV yang sudah ada")
    ap.add_argument("--update", action="store_true",
                    help="inkremental: ambil review baru saja (urut Terbaru, berhenti dini)")
    ap.add_argument("--full", action="store_true",
                    help="dengan --update: scroll sampai habis untuk mendeteksi review yang hilang")
    args = ap.parse_args()
    if args.merge_only:
        state = muat_state()
        laporan_kelengkapan(state, gabungkan(RAW, RAW / "all_reviews.csv"), RAW / "scrape_report.csv")
        return
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
