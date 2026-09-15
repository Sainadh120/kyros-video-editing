#!/usr/bin/env python3
"""Supporting visuals — plan, generate, cache, place, stage, verify.

    python3 scripts/visuals.py plan     projects/<slug>
    python3 scripts/visuals.py approve  projects/<slug> all|v1,v2
    python3 scripts/visuals.py reject   projects/<slug> v3
    python3 scripts/visuals.py generate projects/<slug> [--only v1,v2] [--retry]
    python3 scripts/visuals.py preview  projects/<slug>
    python3 scripts/visuals.py summary  projects/<slug>

Normally reached through `reels.py visuals <slug>`. The editorial rules — when
a beat earns a visual, which treatment, how to prompt — live in the
kyros-doctor-reels skill, references/visuals.md.

The doctor is the reel. A visual shows what she is saying on that beat, as
realistically as possible, and it is a hazard like any burned-in graphic: it
has a window and a rectangle, and the captions, plate, mark and doctor bubble
answer to it. Generation runs through the claude-code-video-toolkit on Modal
and only ever produces files; Remotion only ever plays them.

Everything here is opt-in. A brief without an enabled `visuals` block never
reaches this module from `build`, and rebuilds byte-identical.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
WIDTH, HEIGHT = 1080, 1920


def f(s):
    return int(round(s * FPS))


def ms(m):
    return int(round(m / 1000 * FPS))


# ---- engines --------------------------------------------------------------
# One entry per toolkit tool. The GPU is the one the toolkit's Modal app
# actually requests (docker/modal-*/app.py) — the toolkit's own cost table
# lists image_edit on an A10G, but the app asks for an A100-80GB — and the
# rate is Modal's published per-second price for it.
TOOLS = {
    "flux2": {"script": "tools/flux2.py", "app": "docker/modal-flux2/app.py",
              "model": "black-forest-labs/FLUX.2-klein-4B", "label": "FLUX.2",
              "provider": "modal", "gpu": "A10G", "usdPerSec": 0.000306,
              "endpointEnv": "MODAL_FLUX2_ENDPOINT_URL", "kind": "image",
              "ext": "png", "typicalSec": (6, 45), "timeout": 900},
    "image_edit": {"script": "tools/image_edit.py", "app": "docker/modal-image-edit/app.py",
                   "model": "Qwen/Qwen-Image-Edit-2511", "label": "Qwen image edit",
                   "provider": "modal", "gpu": "A100-80GB", "usdPerSec": 0.000694,
                   "endpointEnv": "MODAL_IMAGE_EDIT_ENDPOINT_URL", "kind": "image",
                   "ext": "png", "typicalSec": (20, 420), "timeout": 1200},
    "ltx2": {"script": "tools/ltx2.py", "app": "docker/modal-ltx2/app.py",
             "model": "Lightricks/LTX-2.3-22B", "label": "LTX-2",
             "provider": "modal", "gpu": "A100-80GB", "usdPerSec": 0.000694,
             "endpointEnv": "MODAL_LTX2_ENDPOINT_URL", "kind": "video",
             "ext": "mp4", "typicalSec": (90, 360), "timeout": 1500},
}
PRICE_SOURCE = "modal.com/pricing, 2026-09-11"
MODE_TOOL = {"image": "flux2", "imageEdit": "image_edit", "video": "ltx2"}
MODES = ("graphic", "image", "imageEdit", "video")

# ---- treatments and their budgets ------------------------------------------
TREATMENTS = ("doctorBubble", "inset", "cutaway", "hookBackdrop", "listBuild")
FULL_FRAME = ("doctorBubble", "cutaway", "listBuild")   # she leaves full-frame
MAX_SECONDS = {"doctorBubble": 6.0, "inset": 6.0, "cutaway": 2.5, "hookBackdrop": 60.0,
               "listBuild": 9.0}   # five items at ~1.4s each, plus a beat with all of them
LIST_MIN_DWELL = 0.4        # a list item that would be on screen for less is dropped
LIST_TILE_FRAMES = ms(330)  # an item's move from centre stage to its tile
MIN_SECONDS = 1.2                                 # shorter reads as a flash
DOCTOR_RETURN_FRAMES = 45                         # 1.5s of her between full-frame visuals
MAX_AWAY_SHARE = 0.5                              # she is full-frame for >= half the answer
GRAPHIC_COVER_LIMIT = 0.75                        # same bar as a caption skip candidate
FADE_FRAMES = ms(400)
SHRINK_FRAMES = ms(470)
INSET_CLEAR_FRAMES = 9          # build_captions.ZONE_MARGIN + 1

VISUAL_STYLES = ["naturalLight", "goldenHour", "brightAiry", "documentary"]
BUBBLE_SHAPES = ["circle", "roundedSquare"]
GRAPHIC_TYPES = ("counter", "frequency", "ring", "checklist")
MOTIONS = {"pushIn": (1.0, 1.07, 0.0, 0.0), "pullOut": (1.07, 1.0, 0.0, 0.0),
           "panLeft": (1.08, 1.08, 0.025, -0.025), "panRight": (1.08, 1.08, -0.025, 0.025),
           "none": (1.0, 1.0, 0.0, 0.0)}

FLUX_SIZES = {"9:16": (1088, 1936), "16:9": (1344, 768), "4:5": (896, 1120), "1:1": (1024, 1024)}
LTX_SIZES = {"9:16": (768, 1344), "16:9": (1024, 576), "4:5": (640, 768), "1:1": (768, 768)}
LTX_FPS = 24
LTX_NEGATIVE = ("flickering, jitter, warping, distorted limbs, extra fingers, blurry, "
                "low quality, text, watermark, logo, cartoon")

# Generation quality. A supporting visual sits under captions inside a
# 1080x1920 master, so HD is enough (Niranjan, after the pilot) and roughly
# halves GPU time. "hd" also cuts a video to the length of its beat. "full" is
# what the pilot was generated at, kept so its cached pictures stay valid.
QUALITY = {
    "hd": {"flux": {"9:16": (720, 1280), "16:9": (1024, 576), "4:5": (768, 960),
                    "1:1": (768, 768)},
           "ltx": {"9:16": (576, 1024), "16:9": (1024, 576), "4:5": (512, 640),
                   "1:1": (576, 576)},
           "matchLength": True},
    "full": {"flux": FLUX_SIZES, "ltx": LTX_SIZES, "matchLength": False},
}
DEFAULT_QUALITY = "hd"
VIDEO_PAD_SECONDS = 0.4     # a little footage either side of the beat, for the fades

# Platform UI: the top band, the caption/username band at the bottom, and the
# like/comment/share column down the right side of the lower half.
SAFE = {"top": 288, "bottom": 1560, "right": WIDTH - 120, "rightFromY": 960}
RECT_PAD = 20
WASH_FLOOR = 45
WASH_MARGIN = 110          # px of soft glow above and below the words
WASH_EDGE_LOSS = 0.85      # the oval glow is ~85% of its peak at the text's edge
MARK_INK = "#0F3D2E"       # the lockup's forest
MARK_FLOOR = 45


# ---- small geometry, kept local so build_captions can import this module ---
def rect_overlap(a, b, pad=0):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (ax0 - pad) < bx1 and bx0 < (ax1 + pad) and (ay0 - pad) < by1 and by0 < (ay1 + pad)


def occupied_frac(windows, a, b):
    if b <= a:
        return 0.0
    covered = sum(max(0, min(b, w1) - max(a, w0)) for w0, w1 in windows)
    return covered / (b - a)


def overlap_frames(windows, a, b):
    return sum(max(0, min(b, w1) - max(a, w0)) for w0, w1 in windows)


def over(fg, bg, alpha):
    a = [int(fg[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(int(round(x * alpha + y * (1 - alpha))) for x, y in zip(a, b))


# ---- project files -------------------------------------------------------
def load_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def load_brief(project):
    return json.loads((Path(project) / "brief.json").read_text())


def save_brief(project, brief):
    (Path(project) / "brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False))


def load_words(project):
    d = load_json(Path(project) / "work" / "words.json")
    return d["words"] if d else []


def manifest_path(project):
    return Path(project) / "work" / "visuals.json"


def load_manifest(project):
    return load_json(manifest_path(project)) or {"items": {}, "runs": []}


def save_manifest(project, m):
    p = manifest_path(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False))


def ai_dir(project):
    return Path(project) / "assets" / "ai"


def enabled(brief):
    v = (brief or {}).get("visuals")
    return bool(v and v.get("enabled") and v.get("beats"))


def beats_of(brief):
    return list(((brief or {}).get("visuals") or {}).get("beats") or [])


def kind_of(v):
    mode = v.get("mode", "image")
    return {"graphic": "graphic", "video": "video"}.get(mode, "image")


# ---- beats and her words -------------------------------------------------
def _first_word(spec):
    return (spec.get("lead") or spec["key"])[0]


def beat_window(specs, words, n, video_frames, out_frames=ms(240)):
    """Frames of beat n (1-based), measured the way build_captions times a
    chunk: from its first word to the next beat's first word."""
    spec = specs[n - 1]
    start = words[_first_word(spec)]["startFrame"]
    if n < len(specs):
        end = words[_first_word(specs[n])]["startFrame"]
    else:
        end = min(words[spec["key"][-1]]["endFrame"] + ms(700), video_frames - out_frames)
    return start, end


def beat_text(specs, words, n):
    if not words or not specs or not n or not 1 <= n <= len(specs):
        return ""
    a = _first_word(specs[n - 1])
    b = _first_word(specs[n]) if n < len(specs) else specs[n - 1]["key"][-1] + 1
    return " ".join(w["word"] for w in words[a:b])


def text_between(words, a_frame, b_frame):
    return " ".join(w["word"] for w in words if a_frame <= w["startFrame"] < b_frame)


def said_for(v, specs, words):
    if v.get("at") and words:
        return text_between(words, f(v["at"][0]), f(v["at"][1]))
    return beat_text(specs, words, v.get("beat"))


def answer_start_of(brief, words):
    """Mirrors build_captions: her voice opens the answer, not the first caption."""
    specs = [s for s in brief.get("chunks") or [] if not s.get("skip")]
    q_span = {i for row in (brief.get("question") or {}).get("rows", [])
              for i in (row.get("words") or [])}
    first = words[_first_word(specs[0])]["startFrame"] if specs else 0
    speech = next((words[i]["startFrame"] for i in range(len(words)) if i not in q_span), first)
    return min(first, speech)


# ---- requests, the cache key -----------------------------------------------
def default_seed(prompt):
    return int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % (2 ** 31)


def ltx_frames(seconds, fps=LTX_FPS):
    """LTX-2 wants (n-1) % 8 == 0; 121 (~5s) is its sweet spot and our cap."""
    n = max(25, math.ceil(seconds * fps))
    n = ((n - 1 + 7) // 8) * 8 + 1
    return min(n, 121)


def gen_size(mode, treatment, aspect=None, quality=DEFAULT_QUALITY):
    if treatment == "listBuild":
        ar = aspect or "1:1"            # centre stage, then a tile — square crops both ways
    elif treatment in ("doctorBubble", "cutaway", "hookBackdrop"):
        ar = "9:16"
    else:
        ar = aspect or "16:9"
    table = QUALITY[quality]["ltx" if mode == "video" else "flux"]
    return table.get(ar, table["16:9"])


def quality_of(brief):
    q = ((brief or {}).get("visuals") or {}).get("quality") or DEFAULT_QUALITY
    return q if q in QUALITY else DEFAULT_QUALITY


def seconds_for(v, specs, words, video_frames):
    """How long a visual is on screen — what an HD video is generated to."""
    t = v.get("treatment", "doctorBubble")
    if v.get("at"):
        s = v["at"][1] - v["at"][0]
    elif v.get("beat") and words and 1 <= v["beat"] <= len(specs):
        a, b = beat_window(specs, words, v["beat"], video_frames)
        if t == "listBuild" and v.get("word") is not None and v["word"] < len(words):
            a = max(a, words[v["word"]]["startFrame"])
        s = (b - a) / FPS
    else:
        return None
    return min(s, MAX_SECONDS.get(t, 6.0))


def request_of(v, brief, project, siblings=None, words=None):
    """request_for with this reel's quality and, for video, its beat's length."""
    specs = brief.get("chunks") or []
    words = load_words(project) if words is None else words
    vf = (load_json(Path(project) / "work" / "clip.json", {}) or {}).get("frames30") \
        or (words[-1]["endFrame"] + 30 if words else 0)
    secs = seconds_for(v, specs, words, vf) if v.get("mode") == "video" else None
    sib = siblings if siblings is not None else {b["id"]: b for b in beats_of(brief)}
    return request_for(v, sib, project, quality_of(brief), secs)


def request_for(v, siblings=None, project=None, quality=DEFAULT_QUALITY, seconds=None):
    """Everything that determines the pixels, and nothing that doesn't. Beat,
    timing, treatment position and camera move are composition — they never
    change the request, so they never regenerate. (An HD video's length is
    pixels: it is generated to its beat.)"""
    mode = v.get("mode", "image")
    if mode == "graphic":
        return None
    tool = MODE_TOOL[mode]
    T = TOOLS[tool]
    w, h = gen_size(mode, v.get("treatment", "doctorBubble"), v.get("aspect"), quality)
    prompt = (v.get("prompt") or "").strip()
    req = {"tool": tool, "model": T["model"], "mode": mode, "prompt": prompt,
           "negative": None, "width": w, "height": h,
           "seed": v["seed"] if v.get("seed") is not None else default_seed(prompt),
           "steps": v.get("steps"), "guidance": v.get("guidance"), "input": None}
    if tool == "ltx2":
        req["negative"] = (v.get("negative") or LTX_NEGATIVE).strip()
        if QUALITY[quality]["matchLength"]:
            req["numFrames"] = ltx_frames((v.get("seconds") or seconds or 5.0)
                                          + VIDEO_PAD_SECONDS)
        else:
            req["numFrames"] = ltx_frames(v.get("seconds") or 5.0)
        req["fps"] = LTX_FPS
        req["quality"] = v.get("quality", "standard")
    elif tool == "image_edit":
        req["negative"] = (v.get("negative") or "").strip() or None
    inp = v.get("input") or {}
    if inp.get("visual"):
        other = (siblings or {}).get(inp["visual"])
        req["input"] = {"visual": request_hash(request_for(other, siblings, project, quality))
                        if other else inp["visual"]}
    elif inp.get("path"):
        p = Path(project or ".") / inp["path"]
        req["input"] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest()
                        if p.exists() else f"missing:{inp['path']}"}
    return req


def request_hash(req):
    return hashlib.sha256(json.dumps(req, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def asset_name(vid, h, ext):
    return f"{vid}-{h[:12]}.{ext}"


# ---- safety -------------------------------------------------------------
# Show what she says, never what she didn't. These are the things a generated
# picture could claim on her behalf.
BLOCK = [
    (r"\bbefore[\s-]*(and|&|/|vs\.?)?[\s-]*after\b", "before/after imagery"),
    (r"\btransformation\b|\bresults? (after|of)\b|\bweight[- ]loss (result|journey|progress)\b"
     r"|\blost \d+\s?(kg|kilos?|pounds|lbs)\b", "an outcome she did not show"),
    (r"\b(lab|blood|test|medical|diagnostic|hormone)\s+(report|result|record|panel)s?\b"
     r"|\bprescription\b|\bmri\b|\bct scan\b|\bx-?ray\b|\bultrasound (scan|image|report)\b"
     r"|\bscan results?\b|\bmedical chart\b|\bmedical journal\b|\bresearch paper\b"
     r"|\bclinical (study|trial)\b", "a record or evidence"),
    (r"\btestimonial\b|\bfive-star\b|\b5-star\b|\bstar rating\b|\bpatient\b"
     r"|\b(customer|patient) review\b", "a patient or a testimonial"),
    (r"\bdoctors?\b|\bphysicians?\b|\bnurses?\b|\bwhite coat\b|\bstethoscope\b"
     r"|\bclinicians?\b|\bsurgeons?\b|\bgynaecologists?\b|\bgynecologists?\b",
     "a clinician — the real doctor is the only one on screen"),
    (r"\bcure[ds]?\b|\bmiracle\b|\bguarantee", "a claim word"),
    (r"\bnude\b|\bnaked\b|\blingerie\b", "not for a clinic's feed"),
]
REVIEW = [
    (r"\b(ovar(y|ies)|uter(us|ine)|follicles?|insulin|hormones?|pancrea\w*|liver"
     r"|thyroid|anatom\w*|organs?|cells?|blood vessels?|3d medical|medical "
     r"(illustration|visuali[sz]ation))\b", "anatomy or physiology — check it shows what she said"),
    (r"\b(pills?|tablets?|capsules?|syringes?|injections?|medicines?|medications?)\b",
     "medicine — unbranded, no labels, no dosage"),
    (r"\b(child|children|kids?|baby|babies|infants?|teens?|teenagers?|minors?)\b", "a minor"),
]
WARN = [
    (r'"[^"]+"|\b(text|sign|label|poster|caption|lettering|logo|headline|signage)\b',
     "text in the image — Remotion sets every word; models misspell"),
]


def lint_prompt(prompt):
    p = (prompt or "").lower()
    out = []
    for level, rules in (("blocked", BLOCK), ("review", REVIEW), ("warn", WARN)):
        for pat, why in rules:
            if re.search(pat, p):
                out.append({"level": level, "rule": pat[:40], "why": why})
    return out


def risk(findings):
    levels = {x["level"] for x in findings}
    return "blocked" if "blocked" in levels else "review" if "review" in levels else "low"


NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45,
                "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100, "thousand": 1000,
                "once": 1, "twice": 2, "thrice": 3, "half": 0.5}


def spoken_numbers(text):
    t = (text or "").lower()
    t = re.sub(r"(\d)\s*,\s*(\d{3})", r"\1\2", t)       # "10 ,000" -> "10000"
    nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)}
    for w in re.findall(r"[a-z-]+", t):
        if w in NUMBER_WORDS:
            nums.add(float(NUMBER_WORDS[w]))
    if any(n >= 1000 for n in nums):                    # "8 to 10,000" means 8,000
        nums |= {n * 1000 for n in nums if n < 1000}
    return nums


def _graphic_numbers(g):
    vals = []
    for k in ("value", "from"):
        if isinstance(g.get(k), (int, float)):
            vals.append(float(g[k]))
    c = g.get("count")
    if isinstance(c, (int, float)):
        vals.append(float(c))
    elif isinstance(c, list):
        vals += [float(x) for x in c]
    texts = [str(g.get(k) or "") for k in ("label", "unit", "prefix", "suffix")]
    texts += [str(x) for x in (g.get("items") or [])]
    for t in texts:
        vals += [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", t)]
    return vals


def lint_graphic(g, said):
    """Problems with a text/number graphic. Empty means fine."""
    g = g or {}
    if g.get("type") not in GRAPHIC_TYPES:
        return [f"unknown graphic type {g.get('type')!r} — use one of {', '.join(GRAPHIC_TYPES)}"]
    out = []
    if g["type"] == "checklist":
        items = g.get("items") or []
        if not 1 <= len(items) <= 4:
            out.append("a checklist holds 1–4 items")
        if any(len(str(i).split()) > 3 for i in items):
            out.append("checklist items are 1–3 words")
    if g["type"] in ("counter", "ring") and not isinstance(g.get("value"), (int, float)):
        out.append(f"a {g['type']} needs a numeric value")
    if g["type"] == "frequency" and g.get("count") is None:
        out.append("a frequency needs a count")
    spoken = spoken_numbers(said)
    for n in _graphic_numbers(g):
        if n not in spoken:
            out.append(f"shows {n:g}, which she does not say on this beat")
    return out


# ---- timing ---------------------------------------------------------------
def resolve_timing(beats, specs, words, video_frames, answer_start, question_end,
                   top_win=None, asset_seconds=None):
    """Approved visuals -> frame windows, with every budget applied. Returns
    (items, report_lines). Pure: no files, no media.

    A spoken list (treatment listBuild: one visual per item, sharing a
    `group`) is timed as one unit — each item arrives on its own word, all of
    them hold to the end of the list, and the group counts once against her
    screen time. Hook pictures run in sequence inside the question and never
    reach the answer."""
    top_win, asset_seconds = top_win or [], asset_seconds or {}
    report, cands, hooks = [], [], []
    for v in beats:
        if v.get("status") != "approved":
            continue
        vid, t = v["id"], v.get("treatment", "doctorBubble")
        if t not in TREATMENTS:
            report.append(f"  {vid}: unknown treatment {t!r} — skipped")
            continue
        grouped = t == "listBuild"
        if t == "hookBackdrop":
            a, b = (f(v["at"][0]), f(v["at"][1])) if v.get("at") else (0, question_end)
            a, b = max(0, a), min(b, question_end)
        elif v.get("at"):
            a, b = f(v["at"][0]), f(v["at"][1])
        elif v.get("beat"):
            n = v["beat"]
            if not 1 <= n <= len(specs):
                report.append(f"  {vid}: beat {n} does not exist — skipped")
                continue
            a, b = beat_window(specs, words, n, video_frames)
            if grouped and v.get("word") is not None and 0 <= v["word"] < len(words):
                a = max(a, words[v["word"]]["startFrame"])
        else:
            report.append(f"  {vid}: no beat and no `at` window — skipped")
            continue
        if t != "hookBackdrop":
            if occupied_frac(top_win, a, b) >= GRAPHIC_COVER_LIMIT:
                report.append(f"  {vid}: a burned-in graphic already covers "
                              f"{occupied_frac(top_win, a, b):.0%} of this beat — "
                              f"the footage carries it, no visual")
                continue
            a = max(a, answer_start)
        if grouped:
            b = min(b, video_frames)
        else:
            b = min(b, a + f(MAX_SECONDS[t]), video_frames)
            if vid in asset_seconds:
                b = min(b, a + int(asset_seconds[vid] * FPS))
            if b - a < f(MIN_SECONDS):
                report.append(f"  {vid}: {((b - a) / FPS):.2f}s is too short — "
                              f"dropped rather than flashed")
                continue
        it = {"id": vid, "beat": v.get("beat"), "treatment": t, "mode": v.get("mode", "image"),
              "kind": kind_of(v), "fromFrame": a, "toFrame": b}
        for k in ("graphic", "motion", "aspect", "group", "label", "word"):
            if v.get(k) is not None:
                it[k] = v[k]
        if grouped and not it.get("group"):
            it["group"] = vid
        (hooks if t == "hookBackdrop" else cands).append(it)

    hooks.sort(key=lambda i: (i["fromFrame"], i["id"]))
    kept_hooks = []
    for h in hooks:
        if kept_hooks and h["fromFrame"] < kept_hooks[-1]["toFrame"]:
            h["fromFrame"] = kept_hooks[-1]["toFrame"]
        if h["toFrame"] - h["fromFrame"] < f(0.5):
            report.append(f"  {h['id']}: no room left in the question — dropped")
            continue
        kept_hooks.append(h)

    units, groups = [], {}
    for it in cands:
        if it["treatment"] == "listBuild":
            groups.setdefault(it["group"], []).append(it)
        else:
            units.append({"items": [it], "a": it["fromFrame"], "b": it["toFrame"],
                          "t": it["treatment"], "name": it["id"]})
    for g, mem in groups.items():
        mem.sort(key=lambda i: (i["fromFrame"], i["id"]))
        g0 = mem[0]["fromFrame"]
        g1 = min(max(m["toFrame"] for m in mem), g0 + f(MAX_SECONDS["listBuild"]))
        keep = [m for m in mem if m["fromFrame"] <= g1 - f(LIST_MIN_DWELL)]
        for m in mem:
            if m not in keep:
                report.append(f"  {m['id']}: dropped — it arrives too late in list {g} to be seen")
        if not keep or g1 - g0 < f(MIN_SECONDS):
            report.append(f"  list {g}: {((g1 - g0) / FPS):.2f}s is too short — dropped")
            continue
        for m in keep:
            m["toFrame"] = g1
        units.append({"items": keep, "a": g0, "b": g1, "t": "listBuild", "name": f"list {g}"})
    units.sort(key=lambda u: (u["a"], u["name"]))

    accepted = []
    for u in units:
        start, why = u["a"], ""
        for p in accepted:
            gap = DOCTOR_RETURN_FRAMES if p["t"] in FULL_FRAME and u["t"] in FULL_FRAME else 0
            if start < p["b"] + gap and u["b"] > p["a"]:
                start = p["b"] + gap
                why = (f"the doctor returns full-frame for {DOCTOR_RETURN_FRAMES / FPS:.1f}s "
                       f"after {p['name']}" if gap else f"it overlaps {p['name']}")
        if start != u["a"]:
            survivors = ([m for m in u["items"] if m["fromFrame"] >= start]
                         if u["t"] == "listBuild" else u["items"])
            if not survivors or u["b"] - start < f(MIN_SECONDS):
                for m in u["items"]:
                    report.append(f"  {m['id']}: dropped — {why}")
                continue
            for m in u["items"]:
                if m not in survivors:
                    report.append(f"  {m['id']}: dropped — {why}")
            u["items"] = survivors
            for m in survivors:
                m["fromFrame"] = max(m["fromFrame"], start)
            report.append(f"  {u['name']}: starts {(start - u['a']) / FPS:.2f}s later — {why}")
            u["a"] = start
        accepted.append(u)

    cap = int(MAX_AWAY_SHARE * (video_frames - answer_start))
    away = [u for u in accepted if u["t"] in FULL_FRAME]
    excess = sum(u["b"] - u["a"] for u in away) - cap
    for u in reversed(away):
        if excess <= 0:
            break
        dur = u["b"] - u["a"]
        if dur - excess < f(MIN_SECONDS):
            accepted.remove(u)
            excess -= dur
            report.append(f"  {u['name']}: dropped — she must be full-frame for at least "
                          f"{MAX_AWAY_SHARE:.0%} of the answer")
        else:
            u["b"] -= excess
            u["items"] = ([m for m in u["items"] if m["fromFrame"] <= u["b"] - f(LIST_MIN_DWELL)]
                          or u["items"][:1])
            for m in u["items"]:
                m["toFrame"] = u["b"]
            report.append(f"  {u['name']}: shortened {excess / FPS:.2f}s — she stays full-frame "
                          f"for at least {MAX_AWAY_SHARE:.0%} of the answer")
            excess = 0

    items = kept_hooks + [m for u in accepted for m in u["items"]]
    items.sort(key=lambda i: (i["fromFrame"], i["id"]))
    return items, report

# ---- geometry: the wall card and the bubble ---------------------------------
def inset_rect(head_top, layout, aspect="16:9"):
    """A card on the bare wall above her head — the one place in the frame the
    footage leaves empty. None when there isn't a card's worth of wall."""
    tz = layout["topZone"]
    y0 = max(SAFE["top"] + 16, tz["top"] + 16)
    y1 = min(head_top - 40, tz["top"] + tz["height"])
    x0, x1 = 70, WIDTH - 70
    if y1 - y0 < 240:
        return None
    aw, ah = (int(x) for x in aspect.split(":"))
    ar = aw / ah
    w = x1 - x0
    h = w / ar
    if h > y1 - y0:
        h = y1 - y0
        w = h * ar
    cx, cy = WIDTH / 2, (y0 + y1) / 2
    return (round(cx - w / 2), round(cy - h / 2), round(cx + w / 2), round(cy + h / 2))


LIST_ROWS = {1: [1], 2: [1, 1], 3: [1, 2], 4: [2, 2], 5: [2, 3], 6: [3, 3]}


def list_tiles(n, region, gap=14):
    """Where each item of a spoken list comes to rest, so that by the end all
    of them are on screen together. Rows fill a vertical frame: 2 stacked,
    3 as one wide over two, 4 as a 2x2, then rows of three."""
    rows = LIST_ROWS.get(n) or ([3] * (n // 3) + ([n % 3] if n % 3 else []))
    x0, y0, x1, y1 = region
    W, H = x1 - x0, y1 - y0
    rh = (H - gap * (len(rows) - 1)) / len(rows)
    tiles = []
    for r, k in enumerate(rows):
        ty0 = y0 + r * (rh + gap)
        tw = (W - gap * (k - 1)) / k
        for c in range(k):
            tx0 = x0 + c * (tw + gap)
            tiles.append((int(round(tx0)), int(round(ty0)),
                          int(round(tx0 + tw)), int(round(ty0 + rh))))
    return tiles[:n]


LIST_POP = 1.35    # how much larger an item arrives than the tile it settles into


def pop_rect(tile, region, scale=LIST_POP):
    """Where a list item arrives: its own tile, larger and centred on itself,
    kept inside the stage. Tiles already placed stay visible around it, so
    the grid visibly fills one item at a time (pcos-blood-tests: arriving over
    the whole stage hid every earlier tile until the last second)."""
    x0, y0, x1, y1 = tile
    rx0, ry0, rx1, ry1 = region
    w = min((x1 - x0) * scale, rx1 - rx0)
    h = min((y1 - y0) * scale, ry1 - ry0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    nx0 = min(max(cx - w / 2, rx0), rx1 - w)
    ny0 = min(max(cy - h / 2, ry0), ry1 - h)
    return (round(nx0), round(ny0), round(nx0 + w), round(ny0 + h))


def list_region(bubble_rect=None):
    """The stage a list plays on: the safe frame, minus her bubble's corner."""
    x0, y0, x1, y1 = 48, SAFE["top"] + 12, WIDTH - 48, 1180
    if bubble_rect:
        if bubble_rect[1] > (y0 + y1) / 2:
            y1 = min(y1, bubble_rect[1] - 28)
        else:
            y0 = max(y0, bubble_rect[3] + 28)
            y1 = SAFE["bottom"] - 20
    return (x0, y0, x1, y1)


def question_box(rows, layout, lead_size=78):
    """Where the question's words sit on the card — centred, as QuestionHook
    lays them out — so a picture under them is judged only where they are."""
    h = 0
    for i, r in enumerate(rows or []):
        if r.get("style") == "key":
            h += (r.get("size") or 180) * 0.92 * max(1, len(r.get("lines") or [1])) + 18
        else:
            h += lead_size * 1.18 + (14 if i else 0)
    h = max(h, 200)
    pad = layout["topZone"]["paddingX"]
    return (pad, round(HEIGHT / 2 - h / 2), WIDTH - pad, round(HEIGHT / 2 + h / 2))


def bubble_candidates(d=340, margin=56):
    top = SAFE["top"] + 24
    bottom = SAFE["bottom"] - 24
    return {"lower-left": (margin, bottom - d, margin + d, bottom),
            "upper-left": (margin, top, margin + d, top + d),
            "upper-right": (WIDTH - margin - d, top, WIDTH - margin, top + d),
            "lower-right": (WIDTH - margin - d, bottom - d, WIDTH - margin, bottom)}


def inside_safe_area(rect):
    x0, y0, x1, y1 = rect
    if y0 < SAFE["top"] or y1 > SAFE["bottom"] or x0 < 0 or x1 > WIDTH:
        return False
    if y1 > SAFE["rightFromY"] and x1 > SAFE["right"]:
        return False
    return True


def solve_bubble(window, hazards, shape="circle", diameter=340):
    """The corner her bubble sits in, for one window. `hazards` is
    [(label, rect, windows)]. Earliest preference that collides with nothing
    wins; otherwise the least collision, reported, never silent."""
    a, b = window
    best = None
    for pref, (corner, rect) in enumerate(bubble_candidates(diameter).items()):
        if not inside_safe_area(rect):
            continue
        hits = [(lbl, overlap_frames(wins, a, b)) for lbl, hr, wins in hazards
                if rect_overlap(rect, hr, RECT_PAD)]
        hits = [(l, n) for l, n in hits if n]
        score = (sum(n for _, n in hits), pref)
        if best is None or score < best[0]:
            best = (score, corner, rect, hits)
    _, corner, rect, hits = best
    return {"corner": corner, "rect": list(rect), "ok": not hits, "collisions": hits,
            "shape": shape}


def bubble_crop(face_box):
    """The circle of source frame that goes into the bubble: her face, a little
    of the hair above and the chin below."""
    x0, y0, x1, y1 = face_box
    w, h = x1 - x0, y1 - y0
    return {"cx": round((x0 + x1) / 2), "cy": round((y0 + y1) / 2 + 0.08 * h),
            "r": round(0.78 * max(w, h))}


def measure_face(clip, times, src_w=None, src_h=None):
    """Median face box over sampled frames, in 1080x1920 render space. None when
    OpenCV is unavailable or nothing is found — the caller estimates instead."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    W, H = 540, 960
    boxes = []
    for t in times:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
             "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
            capture_output=True).stdout
        if len(raw) < W * H:
            continue
        g = np.frombuffer(raw[:W * H], np.uint8).reshape(H, W)
        faces = casc.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(50, 50))
        if len(faces):
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            boxes.append((x * 2, y * 2, (x + w) * 2, (y + h) * 2))
    if not boxes:
        return None
    med = [sorted(b[i] for b in boxes)[len(boxes) // 2] for i in range(4)]
    return tuple(int(v) for v in med)


# ---- hazards handed to build_captions ------------------------------------
def top_block_windows(items):
    """An inset card owns the wall. To the captions it is a burned-in graphic,
    so that beat drops low."""
    return [[it["fromFrame"], it["toFrame"]] for it in items if it["treatment"] == "inset"]


def plate_hazards(items):
    """The plate names her. Never while she is off screen or in the bubble;
    an inset only where their rectangles meet."""
    out = []
    for it in items:
        if it["treatment"] == "hookBackdrop":
            continue
        rect = None if it["treatment"] in FULL_FRAME else tuple(it.get("rect") or (0, 0, WIDTH, HEIGHT))
        out.append((f"AI visual {it['id']} ({it['treatment']})", rect,
                    [(max(0, it["fromFrame"] - FADE_FRAMES), it["toFrame"] + FADE_FRAMES)]))
    return out


def mark_hazards(items):
    return [(f"AI visual {it['id']} (inset)", tuple(it["rect"]),
             [(it["fromFrame"], it["toFrame"] + FADE_FRAMES)])
            for it in items if it["treatment"] == "inset" and it.get("rect")]


def drop_overlapping(windows, items):
    busy = [(i["fromFrame"] - FADE_FRAMES, i["toFrame"] + FADE_FRAMES) for i in items
            if i["treatment"] != "hookBackdrop"]
    return [w for w in windows if not any(w[0] < b and w[1] > a for a, b in busy)]


# ---- legibility over a generated picture ---------------------------------
def wash_for(text_colors, bg_samples, floor=WASH_FLOOR):
    """Captions keep their measured colours; over a generated picture they may
    need a ground of their own. Smallest wash that clears the floor, or None."""
    import palette as palette_engine
    worst = min(abs(palette_engine.apca(t, b)) for t in text_colors for b in bg_samples)
    if worst >= floor:
        return None
    dark_text = all(palette_engine.is_dark(t) for t in text_colors)
    wash = "#FAF1E4" if dark_text else "#120C08"
    alpha = 0.3
    while alpha < 0.92:
        if all(abs(palette_engine.apca(t, over(wash, b, alpha))) >= floor
               for t in text_colors for b in bg_samples):
            break
        alpha = round(alpha + 0.04, 2)
    return {"color": wash, "opacity": min(alpha, 0.92)}


def text_box(chunk, layout):
    """Where a caption's words actually sit — its zone, but only the height
    of its own lead and payload, centred the way ChunkBlock centres them.
    Sampling the whole zone judged captions against a head or a tree they
    never touch."""
    z = layout["topZone"] if chunk["zone"] == "top" else layout["bottomZone"]
    lines = max(1, len(chunk.get("keyLines") or []))
    h = ((chunk.get("leadSize") or 60) * 1.25 if chunk.get("leadWords") else 0) \
        + 18 + lines * (chunk.get("keySize") or 120) * 0.95
    y0 = z["top"] + max(0, (z["height"] - h) / 2)
    return (z["paddingX"], round(y0), WIDTH - z["paddingX"], round(y0 + h))


def caption_washes(a, b, chunks, layout, samples_for):
    """A soft ground for each caption that shares [a, b) with a picture it
    would not read on. One per caption, measured under its own words, never
    spanning both zones and never mixing a light caption's needs with a dark
    one's. A caption only brushing the visual's fade gets none.
    `samples_for(box, seconds_into_visual)` returns colours under `box`."""
    out = []
    for c in chunks:
        a2, b2 = max(a, c["fromFrame"]), min(b, c["toFrame"])
        if b2 - a2 < FADE_FRAMES:
            continue
        texts = [x for x in (c.get("keyColor"), c.get("leadColor")) if x]
        box = text_box(c, layout)
        samples = samples_for(box, (a2 - a + (b2 - a2) / 2) / FPS)
        if not texts or not samples:
            continue
        w = wash_for(texts, samples)
        if w:
            out.append({"color": w["color"],
                        "opacity": round(min(0.95, w["opacity"] / WASH_EDGE_LOSS), 3),
                        "fromFrame": a2, "toFrame": b2, "zone": c["zone"],
                        "rect": [0, max(0, box[1] - WASH_MARGIN), WIDTH,
                                 min(HEIGHT, box[3] + WASH_MARGIN)]})
    return out


def mark_should_hide(samples, ink=MARK_INK, floor=MARK_FLOOR):
    """The mark is brand, so it stays over a picture — unless the picture
    under it would swallow it, in which case it steps aside as it does for a
    burned-in graphic."""
    import palette as palette_engine
    return bool(samples) and min(abs(palette_engine.apca(ink, s)) for s in samples) < floor


def sample_colors(path, box, at=None):
    """Dark, median and light colour under `box` (render space) of an image or
    a video frame, fitted the way Remotion fits it (cover)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={WIDTH}:{HEIGHT},crop={max(2, x1 - x0)}:{max(2, y1 - y0)}:{x0}:{y0},"
          f"scale=32:12,format=rgb24")
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{at:.2f}"] if at else []) + \
          ["-i", str(path), "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    px = [tuple(raw[i:i + 3]) for i in range(0, len(raw) - 2, 3)]
    if not px:
        return []
    px.sort(key=lambda p: 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2])
    pick = [px[int(q * (len(px) - 1))] for q in (0.05, 0.5, 0.95)]
    return ["#%02X%02X%02X" % p for p in pick]


# ---- assets: validate, cache, generate ------------------------------------
def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
    except Exception:
        return None
    vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
    if out.returncode != 0 or not vs:
        return None
    dur = d.get("format", {}).get("duration")
    return {"width": vs[0].get("width"), "height": vs[0].get("height"),
            "durationSec": float(dur) if dur not in (None, "N/A") else None,
            "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def validate_asset(path, kind):
    p = Path(path)
    if not p.exists():
        return False, "missing"
    if p.stat().st_size == 0:
        return False, "zero-byte file"
    info = probe(p)
    if not info or not info.get("width"):
        return False, "cannot decode"
    if kind == "video" and not info.get("durationSec"):
        return False, "cannot decode (no duration)"
    return True, info


def strip_audio(src, dst):
    """Her voice is the only audio. LTX-2 invents a soundtrack; it goes."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-c:v", "copy",
                        "-movflags", "+faststart", str(dst)], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-c:v", "libx264",
                        "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)],
                       check=True, capture_output=True)


def find_cached(project, h, ext):
    """This project's assets first, then any other clip's — the same request
    is the same picture."""
    project = Path(project)
    tag = f"-{h[:12]}.{ext}"
    roots = [project] + sorted(p for p in project.parent.iterdir()
                               if p.is_dir() and p != project)
    for r in roots:
        d = ai_dir(r)
        if not d.exists():
            continue
        for fp in sorted(d.glob(f"*{tag}")):
            meta = load_json(fp.with_suffix(".json"), {})
            if meta.get("status") == "complete" and meta.get("requestHash") == h \
                    and validate_asset(fp, meta.get("type", "image"))[0]:
                return fp, meta
    return None, None


def toolkit_commit(toolkit_dir):
    try:
        return subprocess.run(["git", "-C", str(toolkit_dir), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def toolkit_argv(tool, req, out_path, toolkit_dir, input_path=None):
    """The toolkit command for one request — always Modal, never another provider."""
    T = TOOLS[tool]
    argv = ["uv", "run", "--directory", str(toolkit_dir), "python", T["script"]]
    if tool == "flux2":
        argv += ["--prompt", req["prompt"], "--width", str(req["width"]),
                 "--height", str(req["height"]), "--seed", str(req["seed"])]
        if req.get("steps"):
            argv += ["--steps", str(req["steps"])]
        if req.get("guidance"):
            argv += ["--guidance", str(req["guidance"])]
        if input_path:
            argv += ["--input", str(input_path)]
    elif tool == "image_edit":
        argv += ["--input", str(input_path), "--prompt", req["prompt"], "--seed", str(req["seed"])]
        if req.get("negative"):
            argv += ["--negative", req["negative"]]
    elif tool == "ltx2":
        argv += ["--prompt", req["prompt"], "--width", str(req["width"]),
                 "--height", str(req["height"]), "--num-frames", str(req["numFrames"]),
                 "--fps", str(req["fps"]), "--seed", str(req["seed"]),
                 "--quality", req.get("quality", "standard"),
                 "--negative-prompt", req["negative"]]
        if req.get("steps"):
            argv += ["--steps", str(req["steps"])]
        if input_path:
            argv += ["--input", str(input_path)]
    return argv + ["--output", str(out_path), "--no-open", "--cloud", "modal",
                   "--progress", "json"]


def _read_env_file(p):
    env = {}
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class ToolkitRunner:
    """Runs one request through claude-code-video-toolkit on Modal."""

    def __init__(self, toolkit_dir=None):
        self.dir = Path(toolkit_dir or os.environ.get("KYROS_TOOLKIT_DIR")
                        or ROOT.parent / "claude-code-video-toolkit")

    def available(self, tool):
        T = TOOLS[tool]
        key = T["endpointEnv"]
        if not (os.environ.get(key) or _read_env_file(self.dir / ".env").get(key)):
            return False, (f"{key} is not set. In the toolkit ({self.dir}) run "
                           f"`uv run modal deploy {T['app']}` and put the printed URL in "
                           f"its .env as {key}=… (or run /setup there).")
        if not (self.dir / T["script"]).exists():
            return False, f"the toolkit is not at {self.dir} — clone it there or set KYROS_TOOLKIT_DIR"
        if not shutil.which("uv"):
            return False, "uv is not installed (brew install uv)"
        return True, ""

    def run(self, tool, request, out_path, input_path=None):
        argv = toolkit_argv(tool, request, out_path, self.dir, input_path)
        t0 = time.time()
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=TOOLS[tool]["timeout"])
        except subprocess.TimeoutExpired:
            return {"ok": False, "elapsedSec": time.time() - t0,
                    "error": f"timed out after {TOOLS[tool]['timeout']}s"}
        elapsed = time.time() - t0
        out = Path(out_path)
        ok = p.returncode == 0 and out.exists() and out.stat().st_size > 0
        err = None
        if not ok:
            msgs = []
            for line in (p.stderr or "").splitlines():
                try:
                    rec = json.loads(line)
                    if rec.get("stage") == "error":
                        msgs.append(rec.get("msg", ""))
                except ValueError:
                    pass
            tail = [l for l in ((p.stdout or "") + "\n" + (p.stderr or "")).splitlines() if l.strip()]
            err = (msgs[-1] if msgs else " | ".join(tail[-3:]) or
                   f"exit {p.returncode}, no output file")
        return {"ok": ok, "elapsedSec": elapsed, "error": err}


def _cost(tool, elapsed):
    T = TOOLS[tool]
    return round(elapsed * T["usdPerSec"], 6), (
        f"estimate: {elapsed:.1f}s wall-clock × ${T['usdPerSec']}/s ({T['gpu']}, "
        f"{PRICE_SOURCE}); includes cold start and transfer, excludes region multipliers")


def _order(beats):
    """Visuals that animate another visual's still go after it."""
    first = [b for b in beats if not (b.get("input") or {}).get("visual")]
    return first + [b for b in beats if b not in first]


def generate(project, runner=None, only=None, retry=False, log=print):
    """Generate every approved, missing asset. Returns a summary. Failures are
    recorded and never raise — the reel builds without that visual."""
    project = Path(project)
    runner = runner or ToolkitRunner()
    brief = load_brief(project)
    beats = beats_of(brief)
    siblings = {b["id"]: b for b in beats}
    specs, words = brief.get("chunks") or [], load_words(project)
    m = load_manifest(project)
    s = {"images": 0, "videos": 0, "graphics": 0, "reused": 0, "failed": 0,
         "skipped": 0, "costUsd": 0.0, "failedUpperUsd": 0.0}
    m.setdefault("ledger", [])
    out_dir = ai_dir(project)
    commit = toolkit_commit(getattr(runner, "dir", "")) if getattr(runner, "dir", None) else None

    for v in _order(beats):
        vid = v["id"]
        if only and vid not in only:
            continue
        if v.get("status") != "approved":
            continue
        entry = m["items"].get(vid, {})
        said = said_for(v, specs, words)
        if v.get("mode") == "graphic":
            problems = lint_graphic(v.get("graphic"), said)
            m["items"][vid] = ({"status": "blocked", "kind": "graphic", "reason": "; ".join(problems)}
                               if problems else {"status": "complete", "kind": "graphic"})
            if problems:
                log(f"  {vid}: graphic refused — {'; '.join(problems)}")
            else:
                s["graphics"] += 1
            continue
        findings = lint_prompt(v.get("prompt"))
        if risk(findings) == "blocked":
            m["items"][vid] = {"status": "blocked",
                               "reason": "; ".join(x["why"] for x in findings if x["level"] == "blocked")}
            log(f"  {vid}: blocked — {m['items'][vid]['reason']}")
            continue
        req = request_of(v, brief, project, siblings, words)
        h = request_hash(req)
        if v.get("approvedHash") and v["approvedHash"] != h:
            m["items"][vid] = {"status": "needs-approval", "requestHash": h,
                               "reason": "the prompt changed since approval — approve it again"}
            log(f"  {vid}: changed since approval — not generated")
            continue
        tool, T = req["tool"], TOOLS[req["tool"]]
        name = asset_name(vid, h, T["ext"])
        cached, meta = find_cached(project, h, T["ext"])
        if cached:
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / cached.name if cached.parent == out_dir else out_dir / name
            if cached.parent != out_dir and not target.exists():
                shutil.copy2(cached, target)
            side = target.with_suffix(".json")
            meta = dict(meta)
            meta["visualIds"] = sorted(set((meta.get("visualIds") or []) + [vid]))
            meta["sourceBeats"] = sorted(set((meta.get("sourceBeats") or []) + [v.get("beat")]),
                                         key=lambda x: (x is None, x or 0))
            meta["file"] = target.name
            if cached.parent != out_dir:
                meta["copiedFrom"] = str(cached.relative_to(project.parent))
            side.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
            m["items"][vid] = {"status": "complete", "kind": T["kind"], "requestHash": h,
                               "file": f"assets/ai/{target.name}", "reused": True,
                               "costEstimateUsd": 0.0}
            s["reused"] += 1
            log(f"  {vid}: cached — {target.name}")
            continue
        if entry.get("status") == "failed" and entry.get("requestHash") == h and not retry:
            s["skipped"] += 1
            log(f"  {vid}: failed last time ({entry.get('error')}) — use --retry")
            continue
        ok, why = runner.available(tool)
        if not ok:
            m["items"][vid] = {"status": "failed", "requestHash": h, "error": why,
                               "attempts": entry.get("attempts", 0)}
            s["failed"] += 1
            log(f"  {vid}: cannot run — {why}")
            continue

        input_path = None
        inp = v.get("input") or {}
        if inp.get("visual"):
            src = (m["items"].get(inp["visual"]) or {})
            if src.get("status") != "complete" or not src.get("file"):
                m["items"][vid] = {"status": "failed", "requestHash": h,
                                   "error": f"its input still {inp['visual']} is not generated yet"}
                s["failed"] += 1
                continue
            input_path = (project / src["file"]).resolve()
        elif inp.get("path"):
            input_path = (project / inp["path"]).resolve()

        out_dir.mkdir(parents=True, exist_ok=True)
        tmpdir = Path(tempfile.mkdtemp(prefix=f"kyros-{vid}-"))
        tmp = tmpdir / f"raw.{T['ext']}"
        log(f"  {vid}: generating on Modal ({T['label']}, {T['gpu']}) …")
        kw = {"input_path": input_path} if input_path else {}
        try:
            res = runner.run(tool, req, tmp, **kw)
        except Exception as e:                      # a runner bug must not end the batch
            res = {"ok": False, "elapsedSec": 0.0, "error": f"{type(e).__name__}: {e}"}
        elapsed = float(res.get("elapsedSec") or 0.0)
        err = res.get("error")
        final_tmp = tmp
        if res.get("ok"):
            good, info = validate_asset(tmp, T["kind"])
            if good and T["kind"] == "video":
                final_tmp = tmpdir / f"clean.{T['ext']}"
                try:
                    strip_audio(tmp, final_tmp)
                    good, info = validate_asset(final_tmp, "video")
                except subprocess.CalledProcessError as e:
                    good, info = False, f"could not strip audio: {e}"
            if not good:
                err = f"output {info}"
        else:
            good, info = False, None
        cost, basis = _cost(tool, elapsed)
        m["ledger"].append({"id": vid, "requestHash": h, "tool": tool, "ok": bool(good),
                            "elapsedSec": round(elapsed, 2), "costUsd": cost,
                            "at": datetime.now().isoformat(timespec="seconds")})
        if not good:
            shutil.rmtree(tmpdir, ignore_errors=True)
            # A failed call's wall-clock is mostly waiting — for a GPU, or for
            # a container that keeps crashing on start — not GPU time. It is an
            # upper bound, never folded into the generation estimate.
            m["items"][vid] = {"status": "failed", "requestHash": h, "error": err or "unknown",
                               "attempts": entry.get("attempts", 0) + 1,
                               "costUpperBoundUsd": cost,
                               "at": datetime.now().isoformat(timespec="seconds")}
            s["failed"] += 1
            s["failedUpperUsd"] += cost
            log(f"  {vid}: FAILED — {err}")
            continue
        target = out_dir / name
        if not target.exists():                    # never overwrite
            shutil.move(str(final_tmp), str(target))
        shutil.rmtree(tmpdir, ignore_errors=True)
        meta = {"assetId": target.stem, "file": target.name, "type": T["kind"],
                "provider": T["provider"], "tool": tool, "model": T["model"], "gpu": T["gpu"],
                "prompt": req["prompt"], "negative": req.get("negative"),
                "width": req["width"], "height": req["height"], "seed": req["seed"],
                "numFrames": req.get("numFrames"), "fps": req.get("fps"),
                "input": req.get("input"), "requestHash": h, "request": req,
                "visualIds": [vid], "sourceBeats": [v.get("beat")], "slug": brief.get("slug"),
                "treatment": v.get("treatment"), "why": v.get("_why", ""), "says": said,
                "createdAt": datetime.now().isoformat(timespec="seconds"),
                "elapsedSec": round(elapsed, 2), "costEstimateUsd": cost, "costBasis": basis,
                "durationSec": info.get("durationSec") if T["kind"] == "video" else None,
                "outputSize": [info.get("width"), info.get("height")],
                "toolkitCommit": commit, "status": "complete"}
        target.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        m["items"][vid] = {"status": "complete", "kind": T["kind"], "requestHash": h,
                           "file": f"assets/ai/{target.name}", "reused": False,
                           "costEstimateUsd": cost, "elapsedSec": round(elapsed, 2)}
        s["images" if T["kind"] == "image" else "videos"] += 1
        s["costUsd"] += cost
        log(f"  {vid}: done in {elapsed:.0f}s — {target.name}  (est. ${cost:.4f})")

    s["costUsd"] = round(s["costUsd"], 6)
    m["runs"].append(dict(s, at=datetime.now().isoformat(timespec="seconds")))
    save_manifest(project, m)
    return s


def approve(project, ids, log=print):
    """`all` approves every low-risk proposal; review items need their id;
    blocked ones never. Approval is bound to the request — edit the prompt and
    it needs approving again."""
    project = Path(project)
    brief = load_brief(project)
    beats = beats_of(brief)
    siblings = {b["id"]: b for b in beats}
    specs, words = brief.get("chunks") or [], load_words(project)
    for v in beats:
        explicit = ids != "all" and v["id"] in ids
        if not (ids == "all" or explicit) or v.get("status") == "rejected" and not explicit:
            continue
        if v.get("mode") == "graphic":
            problems = lint_graphic(v.get("graphic"), said_for(v, specs, words))
            if problems:
                log(f"  {v['id']}: not approved — {'; '.join(problems)}")
                continue
            v["status"] = "approved"
            continue
        r = risk(lint_prompt(v.get("prompt")))
        if r == "blocked":
            log(f"  {v['id']}: blocked — cannot be approved; rewrite the prompt")
            continue
        if r == "review" and not explicit:
            log(f"  {v['id']}: needs an explicit yes (review) — --approve {v['id']}")
            continue
        v["status"] = "approved"
        v["approvedHash"] = request_hash(request_of(v, brief, project, siblings, words))
    save_brief(project, brief)


def reject(project, ids):
    project = Path(project)
    brief = load_brief(project)
    for v in beats_of(brief):
        if v["id"] in ids:
            v["status"] = "rejected"
            v.pop("approvedHash", None)
    save_brief(project, brief)


def ready_assets(project):
    """Approved visuals that can actually be shown: id -> info. Everything
    else is listed in the report and left out — the reel ships as footage."""
    project = Path(project)
    brief = load_brief(project)
    specs, words = brief.get("chunks") or [], load_words(project)
    m = load_manifest(project)
    siblings = {b["id"]: b for b in beats_of(brief)}
    ready, report = {}, []
    for v in beats_of(brief):
        vid = v["id"]
        if v.get("status") != "approved":
            continue
        if v.get("mode") == "graphic":
            problems = lint_graphic(v.get("graphic"), said_for(v, specs, words))
            if problems:
                report.append(f"  {vid}: graphic refused ({'; '.join(problems)}) — footage only")
            else:
                ready[vid] = {"kind": "graphic", "src": None}
            continue
        e = m["items"].get(vid) or {}
        if e.get("status") != "complete" or not e.get("file"):
            why = e.get("error") or e.get("reason") or "not generated yet"
            report.append(f"  {vid}: {e.get('status', 'pending')} ({why}) — footage only")
            continue
        # The manifest remembers the last picture made for this id. If the
        # prompt has changed since, that picture is the rejected one — never
        # show it in place of the one that was asked for.
        if e.get("requestHash") != request_hash(request_of(v, brief, project, siblings, words)):
            report.append(f"  {vid}: its prompt changed since the last generation — "
                          f"run --generate --only {vid}; footage only until then")
            continue
        fp = project / e["file"]
        good, info = validate_asset(fp, e.get("kind", "image"))
        if not good:
            report.append(f"  {vid}: asset {info} — footage only")
            continue
        ready[vid] = {"kind": e.get("kind", "image"), "src": f"ai/{fp.name}", "file": fp,
                      "durationSec": info.get("durationSec") if e.get("kind") == "video" else None}
    return ready, report


# ---- build: phase A (before captions are zoned) and B (after the solvers) --
def plan_for_build(project, brief, words, video_frames, top_win, scene, layout, M):
    ready, report = ready_assets(project)
    beats = [b for b in beats_of(brief) if b.get("status") == "approved" and b["id"] in ready]
    answer_start = answer_start_of(brief, words)
    if answer_start < f(1.5) and any(b.get("treatment") == "hookBackdrop" for b in beats):
        # pcos-blood-tests: the interviewer's "Ma'am," sat outside question.rows,
        # so her answer "started" at 0.77s and the opening had no room.
        report.append(f"  hook: her answer appears to start at {answer_start / FPS:.2f}s — "
                      f"are the question's first words (e.g. \"Ma'am,\") in question.rows? "
                      f"A key row's `lines` set what is shown, so they can be included "
                      f"without being displayed")
    secs = {vid: r["durationSec"] for vid, r in ready.items() if r.get("durationSec")}
    items, rep = resolve_timing(beats, brief.get("chunks") or [], words, video_frames,
                                answer_start, answer_start, top_win, secs)
    report += rep
    head_top = (scene or {}).get("headTopPx") or 815
    keep = []
    for it in items:
        it["src"] = ready[it["id"]]["src"]
        if it["treatment"] == "inset":
            r = inset_rect(head_top, layout, it.get("aspect") or "16:9")
            if r is None:
                report.append(f"  {it['id']}: no room on the wall above her head for a card "
                              f"— use doctorBubble instead")
                continue
            it["rect"] = list(r)
            # The card shares the wall with the beats either side of it. Arrive
            # after the previous caption has left and leave before the next one
            # lands (build's ZONE_MARGIN), so only this beat's caption drops
            # low, not its neighbours too.
            inset_margin = INSET_CLEAR_FRAMES
            if it["toFrame"] - it["fromFrame"] - 2 * inset_margin >= f(MIN_SECONDS):
                it["fromFrame"] += inset_margin
                it["toFrame"] -= inset_margin
        keep.append(it)
    return {"items": keep, "report": report, "topBlock": top_block_windows(keep),
            "answerStart": answer_start, "ready": ready}


def _zone_box(layout, zone):
    z = layout["topZone"] if zone == "top" else layout["bottomZone"]
    return (0, z["top"], WIDTH, z["top"] + z["height"])


def _item_frames(g, said_words, a, b):
    """Checklist ticks land as she names each item."""
    items = g.get("items") or []
    frames = []
    for i, label in enumerate(items):
        key = str(label).split()[0].lower()[:5]
        hit = next((w["startFrame"] for w in said_words
                    if w["word"].lower().strip(",.?").startswith(key)
                    and w["startFrame"] >= (frames[-1] if frames else a)), None)
        frames.append(hit if hit is not None else a + FADE_FRAMES + i * ms(450))
    return [min(max(x, a + FADE_FRAMES // 2), b - FADE_FRAMES) for x in frames]


def finish_for_build(vplan, *, brief, chunks, layout, M, card, palette, logo, logo_hide,
                     logo_from, clip, words, video_frames, question_rows=None):
    """Everything that needs the solved captions, mark and plate: the bubble's
    corner and crop, the colours a graphic draws in, and a caption ground over
    any picture the captions would not read on."""
    import palette as palette_engine
    vis = (brief.get("visuals") or {})
    shape = vis.get("bubbleShape") if vis.get("bubbleShape") in BUBBLE_SHAPES else "circle"
    scrim = layout["captionScrim"]
    pad_in, pad_out = M["chunkInFrames"], M["chunkOutFrames"]
    report = list(vplan["report"])
    out = []
    ztop = palette["top"]
    wall = palette["scene"]["wall"]
    light_ground = palette_engine.ground_from(wall, "light")
    logo_rect = (WIDTH - logo["right"] - logo["width"], logo["y"],
                 WIDTH - logo["right"], logo["y"] + logo["width"] * 0.42)
    logo_enabled = True           # the Kyros cut; the partner cut carries no mark
    mark_hide = []
    face = None
    # A list is one unit: one bubble for the whole group, and each item knows
    # when the next arrives (that is when it moves to its tile).
    bubbles, gstart, members, next_from = {}, {}, {}, {}
    for it0 in vplan["items"]:
        if it0.get("group"):
            gstart[it0["group"]] = min(gstart.get(it0["group"], it0["fromFrame"]), it0["fromFrame"])
            members.setdefault(it0["group"], []).append(it0)
    for g, mem in members.items():
        mem.sort(key=lambda x: (x["fromFrame"], x["id"]))
        for m0, m1 in zip(mem, mem[1:]):
            next_from[m0["id"]] = m1["fromFrame"]
        members[g] = [m["id"] for m in mem]

    for it in vplan["items"]:
        a, b = it["fromFrame"], it["toFrame"]
        it = dict(it, fadeFrames=FADE_FRAMES)
        live = [c for c in chunks if c["fromFrame"] - pad_in < b and c["toFrame"] + pad_out > a]

        if it["kind"] == "image":
            s0, s1, x0, x1 = MOTIONS.get(it.get("motion") or "pushIn", MOTIONS["pushIn"])
            it["kenBurns"] = {"from": s0, "to": s1, "x0": x0, "x1": x1}

        if it["kind"] == "graphic":
            g = dict(it.get("graphic") or {})
            said = [w for w in words if a <= w["startFrame"] < b]
            if it["treatment"] == "inset":
                ink = ztop["rotation"][0]["hex"]
                g.update(ground=light_ground, groundOpacity=0.94, ink=ink,
                         accent=ztop["accent"]["hex"],
                         text=palette_engine.nearby_lead(ink, light_ground), texture="grain")
            else:
                g.update(ground=card["bg"], groundOpacity=1.0, ink=card["key"],
                         accent=card["key"], text=card["lead"], texture=card.get("texture"))
            if g.get("type") == "checklist":
                g["itemFrames"] = _item_frames(g, said, a, b)
            it["graphic"] = g

        if it["treatment"] in ("doctorBubble", "listBuild"):
            if face is None:
                span = max(1, video_frames)
                times = [t / FPS for t in (span * 0.2, span * 0.4, span * 0.6, span * 0.8)]
                face = measure_face(clip["clip"], times) or (
                    WIDTH * 0.39, 820, WIDTH * 0.61, 1150)
            hazards = []
            for c in live:
                hazards.append((f"{c['zone']} caption", _zone_box(layout, c["zone"]),
                                [(c["fromFrame"] - pad_in, c["toFrame"] + pad_out)]))
                if c["zone"] == "bottom" and scrim.get("enabled"):
                    hazards.append(("scrim", (0, scrim.get("top", HEIGHT), WIDTH, HEIGHT),
                                    [(c["fromFrame"] - pad_in, c["toFrame"] + pad_out)]))
            hazards.append(("mark", logo_rect, [(logo_from, video_frames)]))
            key = it.get("group") or it["id"]
            fresh = key not in bubbles
            if fresh:
                bubbles[key] = solve_bubble((gstart.get(it.get("group"), a), b), hazards, shape)
            got = bubbles[key]
            it["bubble"] = {"shape": shape, "corner": got["corner"], "rect": got["rect"],
                            "face": bubble_crop(face), "ring": "#FAF1E4", "ringWidth": 6,
                            "radius": 64, "shrinkFrames": SHRINK_FRAMES}
            if not got["ok"] and fresh:
                report.append(f"  {it['id']}: bubble has no fully clear corner — "
                              f"{got['corner']}, touching " +
                              ", ".join(f"{l} {n}f" for l, n in got["collisions"]))

        if it["kind"] == "graphic" and it["treatment"] in FULL_FRAME:
            # Content sits in whichever band the captions leave free, and
            # clear of her bubble.
            zones = {c["zone"] for c in live}
            box = ([90, 800, 990, 1150] if "top" in zones else
                   [90, 380, 990, 1110] if "bottom" in zones else [90, 560, 990, 1180])
            br = (it.get("bubble") or {}).get("rect")
            if br and rect_overlap(box, br, RECT_PAD):
                if br[1] < (box[1] + box[3]) / 2:
                    box[1] = br[3] + 40
                else:
                    box[3] = br[1] - 40
            it["rect"] = box

        if it["treatment"] == "listBuild":
            # Centre stage while she says it, then into its tile as the next
            # one arrives; the last settles with a beat to spare so the whole
            # list holds together before she moves on.
            g = it.get("group") or it["id"]
            mem = members.get(g, [it["id"]])
            k = mem.index(it["id"])
            region = list_region((it.get("bubble") or {}).get("rect"))
            tiles = list_tiles(len(mem), region)
            nxt = next_from.get(it["id"])
            settle = nxt if nxt is not None else min(b - f(1.0), a + f(1.2))
            it.update(rect=list(pop_rect(tiles[k], region)), stage=list(region),
                      tile=list(tiles[k]), index=k, count=len(mem),
                      settleFrame=max(a + 6, settle), tileFrames=LIST_TILE_FRAMES,
                      ground=card["bg"], labelColor=card["lead"], accent=card["key"],
                      texture=card.get("texture"), showLabels=bool(it.get("label")))

        if it["treatment"] in FULL_FRAME:
            if it["kind"] == "graphic":
                ground = it["graphic"]["ground"]

                def samples_for(box, at, ground=ground):
                    return [ground]
            else:
                fp = vplan["ready"][it["id"]]["file"]
                kind = it["kind"]

                def samples_for(box, at, fp=fp, kind=kind):
                    return sample_colors(fp, box, None if kind == "image" else max(0.1, at))
            washes = caption_washes(a, b, chunks, layout, samples_for)
            if washes:
                it["captionWashes"] = washes
            if it["treatment"] == "listBuild":
                # The list's stage covers the mark's corner for the whole list:
                # one hide, from the first item to the last frame, never a patchwork.
                if logo_enabled and it.get("index") == 0:
                    mark_hide.append([gstart.get(it.get("group"), a), b + FADE_FRAMES])
                    report.append(f"  list {it.get('group')}: the mark steps aside for the list")
            elif logo_enabled and mark_should_hide(
                    samples_for(logo_rect, (b - a) / 2 / FPS)):
                mark_hide.append([a, b + FADE_FRAMES])
                report.append(f"  {it['id']}: the mark steps aside — it would not read on this picture")

        out.append(it)

    # The opening. When the pictures cover the whole question they ARE the
    # hook — the dark card goes, and only the words get a soft ground,
    # measured against what is under them. If they leave a gap, the card stays
    # (thinned) so the doctor never peeks through mid-question.
    hooks = sorted((h for h in out if h["treatment"] == "hookBackdrop"),
                   key=lambda h: h["fromFrame"])
    if hooks:
        box = question_box(question_rows, layout)
        samples = []
        for h in hooks:
            fp = (vplan["ready"].get(h["id"]) or {}).get("file")
            if fp:
                samples += sample_colors(fp, box, None if h["kind"] == "image" else 0.5)
        answer0 = vplan["answerStart"]
        covered = (hooks[0]["fromFrame"] <= 0 and hooks[-1]["toFrame"] >= answer0 - 1
                   and all(n["fromFrame"] <= p["toFrame"] for p, n in zip(hooks, hooks[1:])))
        for h in hooks:
            h["fadeFrames"] = 0          # frame 1 is already the picture; cuts land on words
        if covered:
            glow = wash_for([card["lead"], card["key"]], samples) if samples else None
            for h in hooks:
                h["cardOpacity"] = 0.0
            if glow:
                hooks[0]["glow"] = {
                    "color": glow["color"],
                    "opacity": round(min(0.95, glow["opacity"] / WASH_EDGE_LOSS), 3),
                    "rect": [0, max(0, box[1] - WASH_MARGIN), WIDTH,
                             min(HEIGHT, box[3] + WASH_MARGIN)]}
        else:
            alpha = 0.72
            while alpha < 0.97 and samples and not all(
                    abs(palette_engine.apca(tc, over(card["bg"], s, alpha))) >= WASH_FLOOR
                    for tc in (card["lead"], card["key"]) for s in samples):
                alpha = round(alpha + 0.03, 2)
            for h in hooks:
                h["cardOpacity"] = min(alpha, 0.97)
            report.append("  hook: the pictures do not cover the whole question — "
                          "the card stays, thinned to keep the words legible")

    for g, ids in members.items():
        g_end = max((x["toFrame"] for x in out if x.get("group") == g), default=0)
        on = [c["id"] for c in chunks
              if min(g_end, c["toFrame"]) - max(gstart[g], c["fromFrame"]) >= FADE_FRAMES]
        if on:
            report.append(f"  list {g}: caption(s) {', '.join(on)} still on — the list carries "
                          f"the words; set \"skip\": true on that beat")

    return {"data": {"style": vis.get("style"), "bubbleShape": shape, "items": out},
            "report": report, "markHide": mark_hide}


# ---- stage and verify ---------------------------------------------------
def stage_assets(project, data, public_dir):
    """Copy exactly the files this build references into studio/public/ai.
    The folder only ever holds copies, so it is cleared first — a previous
    clip's pictures can never be picked up by this one."""
    public_dir = Path(public_dir)
    ai = public_dir / "ai"
    srcs = [it["src"] for it in ((data or {}).get("visuals") or {}).get("items", [])
            if it.get("src")]
    if ai.exists():
        shutil.rmtree(ai)
    if not srcs:
        return []
    ai.mkdir(parents=True)
    for s in srcs:
        shutil.copy2(Path(project) / "assets" / s, public_dir / s)
    return srcs


def verify_assets(project, data):
    """File-level checks on every visual a build references."""
    problems = []
    for it in ((data or {}).get("visuals") or {}).get("items", []):
        if it.get("kind") == "graphic":
            continue
        src = it.get("src")
        if not src:
            problems.append(f"{it['id']}: no src — the composition references nothing")
            continue
        fp = Path(project) / "assets" / src
        good, info = validate_asset(fp, it.get("kind", "image"))
        if not good:
            problems.append(f"{it['id']}: {src} {info}")
            continue
        need = (it["toFrame"] - it["fromFrame"]) / FPS
        if it.get("kind") == "video" and (info.get("durationSec") or 0) + 0.05 < need:
            problems.append(f"{it['id']}: video is {info['durationSec']:.2f}s, shorter than "
                            f"its {need:.2f}s window")
        if info.get("width") and min(info["width"], info["height"]) < 320:
            problems.append(f"{it['id']}: {info['width']}x{info['height']} is too small to show")
        meta = load_json(fp.with_suffix(".json"))
        if not meta or meta.get("status") != "complete":
            problems.append(f"{it['id']}: no metadata sidecar for {fp.name}")
    return problems


def verify_render(project, slug, data, cut="kyros"):
    """Proves each visual is actually in the rendered cut: its region must
    differ from the raw take at the same moment. Saves one frame per visual
    to out/previews/ — semantic quality is for a person to judge, not this."""
    project = Path(project)
    render = project / "out" / f"{slug}-{cut}.mp4"
    clip = load_json(project / "work" / "clip.json", {}).get("clip")
    items = ((data or {}).get("visuals") or {}).get("items", [])
    if not render.exists() or not items:
        return [], []
    prev = project / "out" / "previews"
    prev.mkdir(parents=True, exist_ok=True)
    problems, saved = [], []
    for it in items:
        if it["treatment"] == "hookBackdrop":
            continue
        t = (it["fromFrame"] + it["toFrame"]) / 2 / FPS
        box = it.get("rect") or [0, 0, WIDTH, HEIGHT]
        out = prev / f"{slug}-{cut}-{it['id']}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(render),
                        "-frames:v", "1", "-q:v", "3", str(out)], capture_output=True)
        saved.append(out)
        if clip and Path(clip).exists():
            def grab(path):
                x0, y0, x1, y1 = (int(v) for v in box)
                return subprocess.run(
                    ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                     "-vf", f"scale={WIDTH}:{HEIGHT},crop={x1 - x0}:{y1 - y0}:{x0}:{y0},"
                            f"scale=32:32,format=gray", "-f", "rawvideo", "-"],
                    capture_output=True).stdout
            r, c = grab(render), grab(clip)
            if len(r) == len(c) == 1024:
                diff = sum(abs(x - y) for x, y in zip(r, c)) / 1024
                if diff < 10:
                    problems.append(f"{it['id']}: at {t:.1f}s the render looks like the raw take "
                                    f"(mean diff {diff:.1f}) — the visual may not be showing")
    return problems, saved


def photoreal(brief):
    return any(v.get("status") == "approved" and v.get("mode") in ("image", "imageEdit", "video")
               for v in beats_of(brief))


# ---- reports -------------------------------------------------------------
def _est(tool):
    T = TOOLS[tool]
    lo, hi = T["typicalSec"]
    return lo * T["usdPerSec"], hi * T["usdPerSec"]


def _wrap(text, width=74, indent="            "):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return ("\n" + indent).join(lines)


def plan_text(project):
    project = Path(project)
    brief = load_brief(project)
    beats = beats_of(brief)
    siblings = {b["id"]: b for b in beats}
    specs, words = brief.get("chunks") or [], load_words(project)
    m = load_manifest(project)
    clip = load_json(project / "work" / "clip.json", {})
    vf = clip.get("frames30") or (words[-1]["endFrame"] + 30 if words else 0)
    vis = brief.get("visuals") or {}
    lines = [f"VISUAL PLAN — {brief.get('slug', project.name)}   "
             f"style {vis.get('style') or '(unset)'} · bubble {vis.get('bubbleShape') or '(unset)'}"
             f"{'' if vis.get('enabled') else '   [visuals.enabled is false — build ignores all of this]'}",
             ""]
    lo_total = hi_total = 0.0
    counts = {"image": 0, "video": 0, "graphic": 0, "cached": 0}

    def describe(v):
        nonlocal lo_total, hi_total
        mode = v.get("mode", "image")
        st = (v.get("status") or "proposed").upper()
        e = m["items"].get(v["id"]) or {}
        state = {"complete": "generated", "failed": f"FAILED: {e.get('error')}",
                 "blocked": f"BLOCKED: {e.get('reason')}",
                 "needs-approval": "changed since approval"}.get(e.get("status"), "")
        if e.get("reused"):
            state = "cached"
        if mode == "graphic":
            g = v.get("graphic") or {}
            probs = lint_graphic(g, said_for(v, specs, words))
            counts["graphic"] += 1
            head = (f"{v['id']}  TEXT ANIMATION ({g.get('type')}) · {v.get('treatment')} · "
                    f"Remotion · {st} · $0")
            body = [f"shows: {json.dumps({k: g[k] for k in g}, ensure_ascii=False)}"]
            if probs:
                body.append("PROBLEM: " + "; ".join(probs))
        else:
            tool = MODE_TOOL[mode]
            T = TOOLS[tool]
            findings = lint_prompt(v.get("prompt"))
            kind = {"image": "AI IMAGE", "imageEdit": "AI IMAGE EDIT", "video": "AI VIDEO"}[mode]
            if (v.get("input") or {}).get("visual"):
                kind += f" (animates {v['input']['visual']})"
            req = request_of(v, brief, project, siblings, words)
            h = request_hash(req)
            cached, _ = find_cached(project, h, T["ext"])
            if e.get("status") == "complete" and e.get("requestHash") != h:
                state = "prompt changed since the last generation — not generated yet"
            if cached or (e.get("status") == "complete" and e.get("requestHash") == h):
                cost = "$0 (cached)"
                counts["cached"] += 1
            else:
                lo, hi = _est(tool)
                if st == "APPROVED":
                    lo_total += lo
                    hi_total += hi
                cost = f"est. ${lo:.3f}–${hi:.3f}"
            counts["image" if mode != "video" else "video"] += 1
            head = (f"{v['id']}  {kind} · {v.get('treatment')} · {T['label']} on Modal {T['gpu']} · "
                    f"{st} · risk {risk(findings)} · {cost}")
            body = [f"prompt: {_wrap(v.get('prompt'))}"]
            if v.get("negative"):
                body.append(f"avoid:  {_wrap(v['negative'])}")
            for x in findings:
                body.append(f"{x['level'].upper()}: {x['why']}")
        if state:
            body.append(f"state:  {state}")
        if v.get("_why"):
            body.append(f"why:    {_wrap(v['_why'])}")
        return head, body

    by_beat = {}
    extra = []
    for v in beats:
        (by_beat.setdefault(v.get("beat"), []).append(v)
         if v.get("beat") and not v.get("at") else extra.append(v))
    for v in [x for x in extra if x.get("treatment") == "hookBackdrop"]:
        head, body = describe(v)
        lines.append("Question card")
        lines.append(f"        {head}")
        lines += [f"            {b}" for b in body]
    for n in range(1, len(specs) + 1):
        spec = specs[n - 1]
        if words:
            a, b = beat_window(specs, words, n, vf)
            window = f"{a / FPS:.1f}–{b / FPS:.1f}s"
        else:
            window = ""
        said = beat_text(specs, words, n)
        cap = " / ".join(spec.get("lines") or [])
        lines.append(f"Beat {n}  {window}  \"{said}\"" + (f"   caption {cap}" if cap else ""))
        vs = by_beat.get(n, [])
        if not vs:
            lines.append("        no visual — her face carries it")
        for v in vs:
            head, body = describe(v)
            lines.append(f"        {head}")
            lines += [f"            {b}" for b in body]
    for v in [x for x in extra if x.get("treatment") != "hookBackdrop"]:
        head, body = describe(v)
        lines.append(f"Window {v.get('at')}")
        lines.append(f"        {head}")
        lines += [f"            {b}" for b in body]
    lines.append("")
    lines.append(f"TOTAL  images {counts['image']} · videos {counts['video']} · text animations "
                 f"{counts['graphic']} · already generated {counts['cached']}")
    lines.append(f"Estimated GPU cost to generate the approved, missing assets now: "
                 f"${lo_total:.3f}–${hi_total:.3f}  (warm–cold; an estimate, not a bill)")
    lines.append("Next: --approve all | --approve v1,v3 | --reject v2 | --generate")
    return "\n".join(lines)


def summary_text(project):
    m = load_manifest(project)
    items = m.get("items", {}).values()
    done = [e for e in items if e.get("status") == "complete"]
    images = sum(1 for e in done if e.get("kind") == "image")
    videos = sum(1 for e in done if e.get("kind") == "video")
    # Graphics are drawn, never generated, so the brief — not the generation
    # manifest — is what says how many are in the reel.
    graphics = len(ready_assets(project)[0]) - sum(
        1 for vid, r in ready_assets(project)[0].items() if r["kind"] != "graphic")
    reused = sum(1 for e in done if e.get("reused"))
    failed = sum(1 for e in items if e.get("status") == "failed")
    ledger = m.get("ledger")
    if ledger is not None:
        spent = sum(x["costUsd"] for x in ledger if x["ok"])
        wasted = sum(x["costUsd"] for x in ledger if not x["ok"])
    else:                                   # manifests written before the ledger
        spent, wasted = sum(r.get("costUsd", 0) for r in m.get("runs", [])), 0.0
    lines = [
        "AI VISUAL GENERATION",
        f"Images: {images}",
        f"Videos: {videos}",
        f"Text animations: {graphics}",
        f"Reused cached assets: {reused}",
        f"Failed: {failed}",
        f"Estimated GPU generation cost: ${spent:.4f}  (estimate — wall-clock × Modal's "
        f"per-second GPU rate; real charges: `uv run modal billing report` in the toolkit)",
    ]
    if wasted:
        lines.append(f"Failed calls: up to ${wasted:.4f} more (upper bound — mostly time "
                     f"spent waiting for the app, not GPU time; the billing report has "
                     f"the real figure)")
    return "\n".join(lines)


def preview_sheet(project):
    """One contact sheet of every generated asset, for a person to look at
    before building."""
    project = Path(project)
    m = load_manifest(project)
    files = [project / e["file"] for e in m.get("items", {}).values()
             if e.get("status") == "complete" and e.get("file")]
    files = [p for p in dict.fromkeys(files) if p.exists()]
    if not files:
        return None
    out = project / "out" / "previews" / f"{project.name}-visuals.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        for i, fp in enumerate(files):
            at = ["-ss", "1.0"] if fp.suffix == ".mp4" else []
            subprocess.run(["ffmpeg", "-v", "error", "-y", *at, "-i", str(fp), "-frames:v", "1",
                            "-vf", "scale=360:640:force_original_aspect_ratio=decrease,"
                                   "pad=360:640:(ow-iw)/2:(oh-ih)/2:color=0x1A1A1A",
                            f"{td}/t{i:02d}.png"], check=True, capture_output=True)
        cols = min(4, len(files))
        rows = math.ceil(len(files) / cols)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{td}/t%02d.png",
                        "-vf", f"tile={cols}x{rows}:padding=8:color=0x1A1A1A",
                        "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, project = argv[0], Path(argv[1])
    rest = argv[2:]

    def ids(arg):
        return "all" if arg == "all" else [x.strip() for x in arg.split(",") if x.strip()]

    if cmd == "plan":
        print(plan_text(project))
    elif cmd == "approve":
        approve(project, ids(rest[0]) if rest else "all")
        print(plan_text(project))
    elif cmd == "reject":
        reject(project, ids(rest[0]))
        print(plan_text(project))
    elif cmd == "generate":
        only = ids(rest[rest.index("--only") + 1]) if "--only" in rest else None
        s = generate(project, only=only if only != "all" else None, retry="--retry" in rest)
        print()
        print(summary_text(project))
        return 1 if s["failed"] else 0
    elif cmd == "preview":
        out = preview_sheet(project)
        print(out or "nothing generated yet")
    elif cmd == "summary":
        print(summary_text(project))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
