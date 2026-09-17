#!/usr/bin/env python3
"""Side-by-side: production models vs challengers, on real Kyros requests.

    python scripts/bakeoff.py run      # generate challenger outputs (spends Modal time)
    python scripts/bakeoff.py sheet    # contact sheets + results table, no spend

Each case is a shipped visual. The production output already exists in its
project's assets/ai (same prompt, size, seed, frames) — it is reused, never
regenerated. Only the challenger is called, with the identical request.
Results go to bakeoff/<date>/ (media gitignored; results.json is the record).
"""
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modal_client  # noqa: E402
import visuals as vz  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "bakeoff" / date.today().isoformat()

CASES = [  # (slug, visual id, what it tests)
    ("pcos-gut-health", "l5", "food — idli (failed once as momos)"),
    ("pcos-belly-fat", "t1", "anatomy — skin/fat/muscle layers"),
    ("pcos-glp1-medications", "v2", "object in hands — injector pen"),
    ("pcos-stress", "v1", "person, modest body shot"),
    ("pcos-supplements", "v2", "person in a real Indian setting"),
    ("pcos-gut-health", "v4", "video — water pouring"),
    ("pcos-gut-health", "v3", "video — woman walking, wide"),
    ("pcos-glp1-medications", "v3", "video — 3D medical animation"),
]
CHALLENGER = {  # production tool -> (challenger tool, endpoint env, GPU $/s, label)
    "flux2": ("qwen_image", "MODAL_QWEN_IMAGE_ENDPOINT_URL", 0.000694, "Qwen-Image-2512 (A100-80GB)"),
    "ltx2": ("ltx25", "MODAL_LTX25_ENDPOINT_URL", 0.000694, "LTX-2.5 distilled + Gemma 4 (A100-80GB)"),
}


def load_case(slug, vid):
    p = ROOT / "projects" / slug
    brief = vz.load_brief(p)
    beats = {b["id"]: b for b in vz.beats_of(brief)}
    req = vz.request_of(beats[vid], brief, p)
    item = vz.load_manifest(p)["items"][vid]
    base = p / item["file"]
    side = json.loads(base.with_suffix(".json").read_text())
    return req, base, side


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    rec_path = OUT / "results.json"
    results = json.loads(rec_path.read_text()) if rec_path.exists() else []
    done = {(r["slug"], r["id"]) for r in results if r.get("ok")}
    for slug, vid, what in CASES:
        if (slug, vid) in done:
            print(f"  {slug}/{vid}: already done")
            continue
        req, base, side = load_case(slug, vid)
        tool, env, rate, label = CHALLENGER[req["tool"]]
        ext = "mp4" if req["tool"] == "ltx2" else "png"
        out = OUT / f"{slug}-{vid}-challenger.{ext}"
        print(f"  {slug}/{vid} ({what}): {label} …", flush=True)
        t0 = time.time()
        res = modal_client.generate(tool, req, out, env, 1500)
        row = {"slug": slug, "id": vid, "what": what, "kind": ext,
               "request": {k: req.get(k) for k in ("width", "height", "seed", "numFrames", "fps")},
               "production": {"file": str(base.relative_to(ROOT)), "model": side.get("model"),
                              "elapsedSec": side.get("elapsedSec"),
                              "costEstimateUsd": side.get("costEstimateUsd")},
               "challenger": {"file": str(out.relative_to(ROOT)), "model": label,
                              "elapsedSec": round(res["elapsedSec"], 2),
                              "costEstimateUsd": round(res["elapsedSec"] * rate, 4),
                              "server": res.get("server")},
               "ok": res["ok"], "error": res["error"], "at": time.strftime("%H:%M:%S")}
        results = [r for r in results if (r["slug"], r["id"]) != (slug, vid)] + [row]
        rec_path.write_text(json.dumps(results, indent=2))
        print(f"    {'ok' if res['ok'] else 'FAILED: ' + str(res['error'])[:160]} "
              f"in {time.time() - t0:.0f}s (est. ${row['challenger']['costEstimateUsd']})", flush=True)


def sheet():
    results = json.loads((OUT / "results.json").read_text())
    for r in results:
        if not r["ok"]:
            continue
        prod, chal = ROOT / r["production"]["file"], ROOT / r["challenger"]["file"]
        dst = OUT / f"{r['slug']}-{r['id']}-sheet.jpg"
        if r["kind"] == "png":
            vf = "[0]scale=-2:640[a];[1]scale=-2:640[b];[a][b]hstack=2"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(prod), "-i", str(chal),
                            "-filter_complex", vf, "-frames:v", "1", str(dst)], check=False)
        else:  # 4 frames each, production row over challenger row
            rows = []
            for i, src in enumerate((prod, chal)):
                tmp = OUT / f"_row{i}.jpg"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf",
                                "select='eq(n,0)+eq(n,20)+eq(n,40)+eq(n,60)',scale=-2:240,tile=4x1",
                                "-frames:v", "1", str(tmp)], check=False)
                rows.append(tmp)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(rows[0]), "-i", str(rows[1]),
                            "-filter_complex", "[0][1]vstack=2", str(dst)], check=False)
            for t in rows:
                t.unlink(missing_ok=True)
        print(dst.relative_to(ROOT))
    print("\ncase | production s / $ | challenger s / $")
    for r in results:
        p, c = r["production"], r["challenger"]
        print(f"{r['slug']}/{r['id']} | {p['elapsedSec']} / {p['costEstimateUsd']} | "
              f"{c['elapsedSec']} / {c['costEstimateUsd']} {'' if r['ok'] else 'FAILED ' + str(r['error'])[:80]}")


if __name__ == "__main__":
    {"run": run, "sheet": sheet}[sys.argv[1] if len(sys.argv) > 1 else "sheet"]()
