"""Tahap 5 (varian) — Pelabelan oleh Claude: 2 pass independen + adjudikasi.

Keputusan peneliti (2026-09-26): Claude melabeli semua task; peneliti melabeli buta sampel gold
(label_prep.py --gold) untuk mengukur akurasi label Claude.

Langkah:
  python src/claude_label.py prep                 # batch input pass1 & pass2 (urutan acak berbeda)
  (Claude menulis data/labels/claude/pass{1,2}/batch_XX.out.jsonl)
  python src/claude_label.py check --pass 1       # validasi skema + evidence (ulangi sampai bersih)
  python src/claude_label.py compare              # kesepakatan pass1 vs pass2 + daftar adjudikasi
  (Claude menulis data/labels/claude/adjudicated.jsonl untuk item yang tidak sepakat)
  python src/claude_label.py finalize             # -> data/labels/export/claude_labels.json (format Label Studio)

Retag (opsional): data/labels/claude/retag.jsonl berisi {"k", "aspek", "evidence", "issue_tags"} untuk
mengganti issue_tags span tertentu (mis. setelah tag baru disetujui). Label asli pass1/pass2 tidak diubah.

Input batch TIDAK memuat rating, asal filter, maupun prediksi baseline (menghindari bias).
Format satu baris output:
  {"k": "r0001", "relevan": "ya", "spans": [{"aspek": "PARKIR", "sentimen": "negative",
    "evidence": "<substring persis text_original>", "issue_tags": ["tarif_mahal"], "ragu": false, "catatan": ""}]}
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "labels"
KERJA = LABELS / "claude"
EXPORT = LABELS / "export"
CONFIG = ROOT / "config"
UKURAN_BATCH = 45
SEED = {1: 111, 2: 222}

TAX = yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))
ASPEK = set(TAX["aspects"])
SENTIMEN = set(TAX["sentiments"])
TAGS = set(TAX["issue_tags"])


# --------------------------------------------------------------------------- IO
def baca_jsonl(path: Path) -> list[dict]:
    baris = []
    for i, l in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if l.strip():
            try:
                baris.append(json.loads(l))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path.name}:{i}: JSON tidak valid ({e})")
    return baris


def tulis_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def peta_kunci() -> pd.DataFrame:
    return pd.read_csv(KERJA / "kunci.csv", encoding="utf-8")


def teks_per_kunci() -> dict[str, str]:
    tasks = json.loads((LABELS / "tasks_main.json").read_text(encoding="utf-8"))
    rid2teks = {t["data"]["review_id"]: t["data"]["text_original"] for t in tasks}
    return {k: rid2teks[r] for k, r in zip(peta_kunci()["k"], peta_kunci()["review_id"])}


# --------------------------------------------------------------------------- prep
def prep() -> None:
    tasks = json.loads((LABELS / "tasks_main.json").read_text(encoding="utf-8"))
    kunci = pd.DataFrame({"k": [f"r{i:04d}" for i in range(1, len(tasks) + 1)],
                          "review_id": [t["data"]["review_id"] for t in tasks]})
    KERJA.mkdir(parents=True, exist_ok=True)
    kunci.to_csv(KERJA / "kunci.csv", index=False, encoding="utf-8")
    item = []
    for k, t in zip(kunci["k"], tasks):
        d = t["data"]
        it = {"k": k, "bahasa": d["language"], "teks": d["text_original"]}
        if not d["text_translated"].startswith("(tidak ada"):
            it["terjemahan"] = d["text_translated"]
        item.append(it)
    for p in (1, 2):
        acak = item[:]
        random.Random(SEED[p]).shuffle(acak)
        for b in range(0, len(acak), UKURAN_BATCH):
            tulis_jsonl(KERJA / f"pass{p}" / f"batch_{b // UKURAN_BATCH + 1:02d}.in.jsonl", acak[b:b + UKURAN_BATCH])
    n_batch = (len(item) + UKURAN_BATCH - 1) // UKURAN_BATCH
    print(f"{len(item)} item -> {n_batch} batch per pass di data/labels/claude/pass1, pass2")


# --------------------------------------------------------------------------- check
def validasi_baris(r: dict, teks: dict[str, str]) -> list[str]:
    err = []
    k = r.get("k")
    if k not in teks:
        return [f"kunci tidak dikenal: {k}"]
    if r.get("relevan") not in ("ya", "tidak"):
        err.append(f"{k}: relevan harus 'ya'/'tidak'")
    spans = r.get("spans", [])
    if r.get("relevan") == "ya" and not spans:
        err.append(f"{k}: relevan=ya tetapi tanpa span")
    if r.get("relevan") == "tidak" and spans:
        err.append(f"{k}: relevan=tidak tetapi punya span")
    for s in spans:
        if s.get("aspek") not in ASPEK:
            err.append(f"{k}: aspek tidak valid {s.get('aspek')!r}")
        if s.get("sentimen") not in SENTIMEN:
            err.append(f"{k}: sentimen tidak valid {s.get('sentimen')!r}")
        bad = [t for t in s.get("issue_tags", []) if t not in TAGS]
        if bad:
            err.append(f"{k}: issue_tags tidak valid {bad}")
        ev = s.get("evidence", "")
        if not ev or ev not in teks[k]:
            err.append(f"{k}: evidence bukan substring persis teks: {ev!r}")
        if "lainnya" in s.get("issue_tags", []) and not s.get("catatan"):
            err.append(f"{k}: issue_tags 'lainnya' wajib catatan")
    return err


def check(p: int, batch: list[int] | None = None) -> bool:
    teks = teks_per_kunci()
    folder = KERJA / f"pass{p}"
    semua_err, dilabel = [], []
    for fin in sorted(folder.glob("batch_*.in.jsonl")):
        if batch and int(fin.name[6:8]) not in batch:
            continue
        fout = fin.with_name(fin.name.replace(".in.", ".out."))
        harap = [r["k"] for r in baca_jsonl(fin)]
        if not fout.exists():
            semua_err.append(f"{fout.name}: belum ada")
            continue
        out = baca_jsonl(fout)
        ks = [r.get("k") for r in out]
        if sorted(ks) != sorted(harap):
            kurang, lebih = set(harap) - set(ks), set(ks) - set(harap)
            dup = {k for k in ks if ks.count(k) > 1}
            semua_err.append(f"{fout.name}: kurang={sorted(kurang)} lebih={sorted(lebih)} duplikat={sorted(dup)}")
        for r in out:
            semua_err += [f"{fout.name}: {e}" for e in validasi_baris(r, teks)]
        dilabel += ks
    print(f"pass{p}{' batch ' + str(batch) if batch else ''}: {len(set(dilabel))} item berlabel;"
          f" {len(semua_err)} masalah")
    for e in semua_err[:60]:
        print("  -", e)
    return not semua_err


# --------------------------------------------------------------------------- compare
def muat_pass(p: int) -> dict[str, dict]:
    return {r["k"]: r for f in sorted((KERJA / f"pass{p}").glob("batch_*.out.jsonl")) for r in baca_jsonl(f)}


def ringkas(r: dict) -> tuple[str, dict[str, str]]:
    """(relevan, {aspek: sentimen gabungan})."""
    per = {}
    for s in r.get("spans", []):
        per.setdefault(s["aspek"], set()).add(s["sentimen"])
    gab = {}
    for a, ss in per.items():
        if len(ss) == 1:
            gab[a] = next(iter(ss))
        elif "mixed" in ss or {"positive", "negative"} <= ss:
            gab[a] = "mixed"
        else:
            gab[a] = next(iter(ss - {"neutral"}))
    return r["relevan"], gab


def compare() -> None:
    from sklearn.metrics import cohen_kappa_score

    p1, p2 = muat_pass(1), muat_pass(2)
    teks = teks_per_kunci()
    ks = sorted(set(p1) & set(p2))
    rel1 = [ringkas(p1[k])[0] for k in ks]
    rel2 = [ringkas(p2[k])[0] for k in ks]
    print(f"Item dibandingkan: {len(ks)}")
    print(f"Relevansi: setuju {sum(a == b for a, b in zip(rel1, rel2))}/{len(ks)}"
          f"  kappa={cohen_kappa_score(rel1, rel2):.3f}")
    print("Aspek (ada/tidak) per kode:")
    for a in sorted(ASPEK):
        x = [a in ringkas(p1[k])[1] for k in ks]
        y = [a in ringkas(p2[k])[1] for k in ks]
        if sum(x) + sum(y):
            kap = cohen_kappa_score(x, y) if len(set(x + y)) > 1 else float("nan")
            print(f"  {a:22} p1={sum(x):3} p2={sum(y):3}  kappa={kap:.3f}")
    s1, s2 = [], []
    for k in ks:
        g1, g2 = ringkas(p1[k])[1], ringkas(p2[k])[1]
        for a in set(g1) & set(g2):
            s1.append(g1[a]); s2.append(g2[a])
    if s1:
        print(f"Sentimen pada aspek yang sama: setuju {sum(a == b for a, b in zip(s1, s2))}/{len(s1)}"
              f"  kappa={cohen_kappa_score(s1, s2):.3f}")
    beda = []
    for k in ks:
        r1, r2 = ringkas(p1[k]), ringkas(p2[k])
        if r1 != r2:
            beda.append({"k": k, "teks": teks[k], "pass1": p1[k], "pass2": p2[k]})
    tulis_jsonl(KERJA / "adjudication_input.jsonl", beda)
    print(f"Tidak sepakat: {len(beda)} item -> data/labels/claude/adjudication_input.jsonl")


# --------------------------------------------------------------------------- finalize
def ke_format_labelstudio(k: str, rid: str, r: dict, teks: str) -> dict:
    hasil = [{"id": "rel", "from_name": "relevan", "to_name": "text", "type": "choices",
              "value": {"choices": [r["relevan"]]}}]
    for i, s in enumerate(r.get("spans", [])):
        start = teks.find(s["evidence"])
        end = start + len(s["evidence"])
        sid = f"{k}_{i}"
        pos = {"start": start, "end": end, "text": s["evidence"]}
        hasil.append({"id": sid, "from_name": "aspek", "to_name": "text", "type": "labels",
                      "value": {**pos, "labels": [s["aspek"]]}})
        hasil.append({"id": sid, "from_name": "sentimen", "to_name": "text", "type": "choices",
                      "value": {**pos, "choices": [s["sentimen"]]}})
        if s.get("issue_tags"):
            hasil.append({"id": sid, "from_name": "issue_tags", "to_name": "text", "type": "choices",
                          "value": {**pos, "choices": s["issue_tags"]}})
        if s.get("ragu"):
            hasil.append({"id": sid, "from_name": "ragu", "to_name": "text", "type": "choices",
                          "value": {**pos, "choices": ["ragu"]}})
        if s.get("catatan"):
            hasil.append({"id": sid, "from_name": "catatan", "to_name": "text", "type": "textarea",
                          "value": {**pos, "text": [s["catatan"]]}})
    return {"data": {"review_id": rid}, "annotations": [{"result": hasil, "was_cancelled": False,
            "completed_by": "claude", "updated_at": r.get("_sumber", "")}]}


def finalize() -> None:
    p1, p2 = muat_pass(1), muat_pass(2)
    adj_file = KERJA / "adjudicated.jsonl"
    adj = {r["k"]: r for r in baca_jsonl(adj_file)} if adj_file.exists() else {}
    teks = teks_per_kunci()
    kunci = peta_kunci()
    beda = {r["k"] for r in baca_jsonl(KERJA / "adjudication_input.jsonl")}
    belum = sorted(beda - set(adj))
    if belum:
        raise SystemExit(f"{len(belum)} item tidak sepakat belum diadjudikasi, mis. {belum[:5]}")
    err = [e for k, r in adj.items() for e in validasi_baris(r, teks)]
    if err:
        raise SystemExit("adjudicated.jsonl tidak valid:\n  " + "\n  ".join(err[:30]))
    retag_file = KERJA / "retag.jsonl"
    retag = {(r["k"], r["aspek"], r["evidence"]): r["issue_tags"] for r in baca_jsonl(retag_file)} if retag_file.exists() else {}
    bad = [t for v in retag.values() for t in v if t not in TAGS]
    if bad:
        raise SystemExit(f"retag.jsonl memuat tag tidak valid: {sorted(set(bad))}")
    terpakai = set()
    tasks, sumber = [], {"pass1 (sepakat)": 0, "adjudikasi": 0}
    for k, rid in zip(kunci["k"], kunci["review_id"]):
        if k in adj:
            r, asal = adj[k], "adjudikasi"
        elif k in p1 and k in p2:
            r, asal = p1[k], "pass1 (sepakat)"
        else:
            raise SystemExit(f"{k} belum dilabel di kedua pass")
        spans = []
        for sp in r.get("spans", []):
            kunci_retag = (k, sp["aspek"], sp["evidence"])
            if kunci_retag in retag:
                sp = {**sp, "issue_tags": retag[kunci_retag]}
                terpakai.add(kunci_retag)
            spans.append(sp)
        r = {**r, "spans": spans, "_sumber": asal}
        sumber[asal] += 1
        tasks.append(ke_format_labelstudio(k, rid, r, teks[k]))
    tak_cocok = set(retag) - terpakai
    if tak_cocok:
        raise SystemExit(f"{len(tak_cocok)} entri retag tidak cocok dengan span mana pun, mis. {sorted(tak_cocok)[:3]}")
    if retag:
        print(f"Retag diterapkan: {len(terpakai)} span")
    EXPORT.mkdir(parents=True, exist_ok=True)
    (EXPORT / "claude_labels.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Final: {len(tasks)} review -> data/labels/export/claude_labels.json  {sumber}")
    print("Lanjut: python src/label_merge.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("langkah", choices=["prep", "check", "compare", "finalize"])
    ap.add_argument("--pass", dest="p", type=int, choices=[1, 2], default=1)
    ap.add_argument("--batch", type=int, nargs="*", help="hanya cek batch tertentu (mis. --batch 1 2 3)")
    args = ap.parse_args()
    if args.langkah == "prep":
        prep()
    elif args.langkah == "check":
        sys.exit(0 if check(args.p, args.batch) else 1)
    elif args.langkah == "compare":
        compare()
    else:
        finalize()


if __name__ == "__main__":
    main()
