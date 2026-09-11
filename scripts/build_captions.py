#!/usr/bin/env python3
"""Turn a clip's brief + word alignment into frame-timed caption data.

    python scripts/build_captions.py projects/<slug>

Reads   projects/<slug>/brief.json      the answers Niranjan gave
        projects/<slug>/work/words.json word-level alignment
        projects/<slug>/work/scene.json measured colour and head position
Writes  projects/<slug>/work/captions_data.json

Everything the component renders comes from here. Nothing is hardcoded in the
TSX, so repositioning or recolouring is a change to this file, not to code.
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import palette as palette_engine
import typography as typography_engine
import motion as motion_engine
import measure_audio as audio_engine
import register as register_engine
import visuals as visuals_engine

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"


def resolve_doctor(ref):
    """A doctor is a library entry, not per-clip files. Dr. Bharani recurs, so
    her plate and details are stored once under brand/doctors/<id>/."""
    if isinstance(ref, dict):
        return ref, None
    d = BRAND / "doctors" / ref
    rec = json.loads((d / "doctor.json").read_text())
    rec["platePath"] = str(d / rec["plate"])
    return rec, d


def resolve_partner(ref, doctor):
    """Partner defaults to the doctor's usual clinic; a brief can override it."""
    if isinstance(ref, dict):
        return ref
    pid = ref or doctor.get("defaultPartner")
    if not pid:
        raise SystemExit("no partner clinic: set one in the brief or in doctor.json")
    d = BRAND / "partners" / pid
    rec = json.loads((d / "partner.json").read_text())
    rec["logoPath"] = str(d / rec["logo"])
    return rec

FPS = 30
WIDTH, HEIGHT = 1080, 1920


def f(s): return int(round(s * FPS))
def ms(m): return int(round(m / 1000 * FPS))


def over(fg, bg, alpha):
    """Flatten `fg` painted at `alpha` over `bg`. Used to work out what a
    caption actually sits on once a scrim covers the footage."""
    a, b = (int(fg[i:i + 2], 16) for i in (1, 3, 5)), (int(bg[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(
        int(round(x * alpha + y * (1 - alpha))) for x, y in zip(a, b))


# Defaults. A brief can override any of these via a "theme" or "layout" block.
THEME = {
    "type": {
        "lead": {"fontFamily": "PlayfairDisplay", "weight": 500,
                 "lineHeight": 1.18, "letterSpacing": -0.5,
                 "questionSize": 78, "answerSize": 70,
                 "bottomAnswerSize": 44},
        "key": {"fontFamily": "Anton", "weight": 400, "lineHeight": 0.92,
                "letterSpacing": -1.0, "advanceEm": 0.47, "minSize": 96,
                "maxSizeOneLine": 240, "maxSizeMultiLine": 178,
                "questionBonus": 26,
                # Bottom zone sits low over the subject, so it reads "low" —
                # smaller than the big top-of-wall payload, and sized to clear
                # the platform UI at the very bottom of the frame.
                "bottomMinSize": 70, "bottomMaxOneLine": 140,
                "bottomMaxMultiLine": 108},
        "ui": {"fontFamily": "DMSans", "weight": 500,
               "nameSize": 30, "metaSize": 24, "ctaSize": 34},
        # The outline, not the fill, is what keeps a caption readable over
        # moving footage — a bright saree, a hand, the mic, all inside one
        # beat. Widths are a fraction of the type size so they hold at every
        # caption size. Set "color": None in a brief to switch strokes off.
        "stroke": {"color": "#0B0B0B", "keyEm": 0.105, "leadEm": 0.075,
                   "shadow": "0 8px 26px rgba(0,0,0,0.40)"},
    },
    "motion": {
        "soft": {"mass": 0.5, "damping": 22, "stiffness": 200},
        "punch": {"mass": 0.5, "damping": 13, "stiffness": 210},
        "wordFrames": ms(200), "chunkInFrames": ms(320),
        "chunkOutFrames": ms(240), "wipeFrames": ms(420),
        "scrimFrames": ms(360), "closeFrames": ms(560),
        "maskRevealFrames": ms(560), "ruleDrawFrames": ms(450),
        "entranceFrames": ms(220), "sectionFrames": ms(450),
        "pullQuoteFrames": ms(600),
    },
}

# ---- the question card ----------------------------------------------------
# The opening question owns the whole screen, so it is the one place the reel
# can change its whole register from clip to clip. Four grounds, two dark and
# two light, each with its own type colours and a texture so the panel is never
# a flat wash. A brief picks one with question.preset; the rule is simply not
# to repeat the last two reels. Anything here can be overridden per clip with
# an explicit question.card block.
HOOK_CARDS = {
    # Dense ink. Near-solid, so the doctor genuinely disappears behind it.
    "ink":    {"bg": "#0C0A07", "opacity": 0.985, "lead": "#FFF6E8",
               "key": "#FFB01F", "texture": "vignette"},
    # The Kyros green, solid — the brand colour carrying the question.
    "forest": {"bg": "#0B2119", "opacity": 0.985, "lead": "#F3E9D8",
               "key": "#FFC64D", "texture": "vignette"},
    # Paper. A full light card with dark type — the register of the
    # insulin-resistance cut, taken full screen.
    "paper":  {"bg": "#F4ECDF", "opacity": 0.99, "lead": "#3A2B20",
               "key": "#103D2C", "texture": "grain"},
    # Bone white, near-pure, rust payload. The brightest of the four.
    "white":  {"bg": "#FBF8F3", "opacity": 0.995, "lead": "#41352C",
               "key": "#A6371C", "texture": "grain"},
    # Deep aubergine. A third dark register, distinct from ink's near-black
    # and forest's brand green — warm white and blush both clear 62 Lc by a
    # wide margin (101.3 / 67.4; see README).
    "plum":   {"bg": "#2A0F22", "opacity": 0.985, "lead": "#FFF6E8",
               "key": "#FFA8B6", "texture": "vignette"},
    # Deep teal. A cool dark register with the brand saffron popping off it
    # (cream 91.6, saffron 65.6).
    "teal":   {"bg": "#0A2B28", "opacity": 0.985, "lead": "#F5EAD2",
               "key": "#FFB01F", "texture": "vignette"},
    # Warm clay/terracotta, mid-light rather than near-black or near-white —
    # a register the first four don't cover at all. Needed lightening past a
    # first pass (#C97B56, best fit only 41.9 Lc) to clear the 45 Lc display
    # floor: espresso 57.9, forest 52.0.
    "clay":   {"bg": "#E0A07A", "opacity": 0.99, "lead": "#2A1B10",
               "key": "#103D2C", "texture": "grain"},
    # Bone/sand. Lighter and greyer than paper, with a brick payload instead
    # of paper's forest or white's rust, so the three light cards don't just
    # differ by a few percent of lightness (warm grey 74.3, brick 65.7).
    "bone":   {"bg": "#EDE3D0", "opacity": 0.995, "lead": "#5A4636",
               "key": "#A6371C", "texture": "grain"},
}


def hook_card(brief):
    """Resolve the question card: a named preset, then any explicit overrides."""
    q = brief.get("question", {})
    card = dict(HOOK_CARDS[q.get("preset", "ink")])
    card.update(q.get("card") or {})
    # A legacy brief may still carry question.scrimOpacity; honour it.
    if "scrimOpacity" in q and not (q.get("card") or {}).get("opacity"):
        card["opacity"] = q["scrimOpacity"]
    card["dark"] = palette_engine.is_dark(card["bg"])
    return card


LAYOUT = {
    "topZone": {"top": 268, "height": 486, "paddingX": 70, "align": "center"},
    # Where captions go when a baked-in graphic occupies the top half. Lower on
    # the frame, over the subject, on a scrim — see layout.captionScrim.
    "bottomZone": {"top": 1150, "height": 430, "paddingX": 84, "align": "center"},
    "captionScrim": {"enabled": False, "color": "#120C08",
                     "opacity": 0.9, "top": 900},
    "logo": {"width": 258, "right": 38, "y": 778,
             "stingSeconds": 1.07, "loop": True, "opacity": 0.95},
    "doctorPlate": {"src": "doctor-plate.png", "targetPillWidth": 780,
                    "left": 70, "top": 1430, "holdFrames": ms(1900)},
    "video": {"renderWidth": WIDTH, "renderHeight": HEIGHT, "offsetY": 0},
    "safeArea": {"topPct": 15, "bottomPct": 15},
}


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def pill_box(png: Path):
    """Visible bounding box inside a transparent PNG, so layout positions the
    artwork rather than the file's padding."""
    wh = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "stream=width,height", "-of", "csv=p=0", str(png)]).decode().strip()
    W, H = [int(v) for v in wh.split(",")[:2]]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-vf",
        "alphaextract", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True).stdout
    x0, x1, y0, y1 = W, 0, H, 0
    for y in range(H):
        row = raw[y * W:(y + 1) * W]
        if max(row) > 24:
            y0, y1 = min(y0, y), max(y1, y)
            for x in range(W):
                if row[x] > 24:
                    x0 = min(x0, x); break
            for x in range(W - 1, -1, -1):
                if row[x] > 24:
                    x1 = max(x1, x); break
    return {"fileWidth": W, "fileHeight": H, "pillX": x0, "pillY": y0,
            "pillWidth": x1 - x0 + 1, "pillHeight": y1 - y0 + 1}


def key_size(lines, tk, avail, question=False, zone="top"):
    """Fit the payload caps to the widest line, clamped to the zone's ceiling.

    The bottom zone rides over the subject on a scrim, so it is deliberately
    smaller ("low") than the big top-of-wall payload.
    """
    longest = max(len(l) for l in lines)
    if zone == "bottom":
        min_s = tk["bottomMinSize"]
        ceiling = tk["bottomMaxOneLine"] if len(lines) == 1 else tk["bottomMaxMultiLine"]
    else:
        min_s = tk["minSize"]
        ceiling = tk["maxSizeOneLine"] if len(lines) == 1 else tk["maxSizeMultiLine"]
    if question:
        ceiling += tk["questionBonus"]
    return int(max(min_s, min(avail / (longest * tk["advanceEm"]), ceiling)))


def face_bottom(clip, at_seconds):
    """Where the subject's face ends — the chin/neck line, in 1920-space.

    The panel behind the low captions must fade in BELOW this, or it shades
    her chin, which reads as a smudge rather than a design. Skin alone will
    not do it: her hands are skin too, and they sit lower than the caption
    band. So take contiguous runs of skin down the centre column and keep the
    TOPMOST one — that is the face; the next run down is the hands, with the
    mic and saree between them.
    """
    import numpy as np
    lows = []
    for t in at_seconds:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip),
             "-frames:v", "1", "-vf",
             "crop=in_w*0.42:in_h:in_w*0.29:0,scale=64:192,format=rgb24",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True).stdout
        if len(raw) < 192 * 64 * 3:
            continue
        a = np.frombuffer(raw[:192 * 64 * 3], np.uint8).reshape(192, 64, 3).astype(int)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        mx, mn = a.max(2), a.min(2)
        skin = (((r > 85) & (r > g + 12) & (g > b + 4) & (mx > 70)
                 & ((mx - mn) > 18) & ((mx - mn) < 130)).mean(1) > 0.30)
        start = None
        for y in range(192):
            if skin[y] and start is None:
                start = y
            elif not skin[y] and start is not None:
                if y - start >= 6:            # first real run = the face
                    lows.append(round((y - 1) / 192 * HEIGHT))
                    break
                start = None
        else:
            if start is not None and 192 - start >= 6:
                lows.append(HEIGHT)
    return max(lows) if lows else None


# How far below the chin the panel may begin to appear, and the range a fade
# is allowed to span. A very short fade reads as a hard bar cut across the
# frame; a very long one climbs the subject's face. The honest answer is in
# between and depends on how much room this particular clip leaves.
CHIN_CLEARANCE = 40
FEATHER_MIN, FEATHER_MAX = 90, 300


def measure_hide_windows(clip, x0px, y0px, x1px, y1px, frames30, top_win, pad=26):
    """Frames where something in the footage has moved in under a FIXED
    on-screen rectangle, given in 1080x1920 render-space pixels.

    Originally written for the Kyros mark, which sits upper-right, between
    the two caption bands, so neither band's scan answers for it. On
    pcos-sleep-cycle the mark landed squarely on a full-screen infographic
    while the top-band scan reported nothing unusual, because by then the
    whole frame was graphic. The doctor plate has the exact same problem —
    it is its own fixed rectangle, not a zone — so this measures whichever
    rectangle it is given rather than duplicating the method per caller.

    Build a per-pixel median plate for the rectangle and flag the frames
    that differ from it. A talking head leaves a fixed patch of wall (or
    whatever the rectangle sits over) essentially static, so a high changed
    fraction means something has been laid over it.
    """
    import numpy as np
    x0 = max(0.0, (x0px - pad) / WIDTH)
    x1 = min(1.0, (x1px + pad) / WIDTH)
    y0 = max(0.0, (y0px - pad) / HEIGHT)
    y1 = min(1.0, (y1px + pad) / HEIGHT)
    if x1 <= x0 or y1 <= y0:
        return []
    fps = 4
    vf = (f"crop=in_w*{x1 - x0:.4f}:in_h*{y1 - y0:.4f}:in_w*{x0:.4f}:in_h*{y0:.4f},"
          f"scale=48:-2,fps={fps},format=rgb24")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", vf,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    if not raw:
        return []
    # ffmpeg emits n stacked frames of 48 x h; h comes from the crop's aspect,
    # so recover it from the byte count and the number of frames sampled.
    n_frames = max(1, int(round(frames30 / FPS * fps)))
    h = max(2, len(raw) // 3 // 48 // n_frames)
    usable = n_frames * h * 48 * 3
    if usable == 0 or len(raw) < usable:
        return []
    a = np.frombuffer(raw[:usable], np.uint8).reshape(n_frames, h * 48, 3).astype(np.int16)
    # The reference must be a frame we KNOW is clean, not the clip's median: on
    # a clip that is graphic for more than half its length the median IS the
    # graphic, and every talking-head frame then reads as "covered".
    clear = [i for i in range(n_frames)
             if not occupied_at(top_win, int(i / fps * FPS))]
    plate = np.median(a[clear] if clear else a, axis=0)
    changed = (np.abs(a - plate).max(axis=2) > 34).mean(axis=1)
    flags = changed > 0.22
    wins, run = [], None
    for i, f in enumerate(flags):
        if f and run is None:
            run = i
        elif not f and run is not None:
            wins.append([run, i]); run = None
    if run is not None:
        wins.append([run, len(flags)])
    out = []
    for a0, b0 in wins:
        f0, f1 = int(a0 / fps * FPS), int(b0 / fps * FPS)
        if f1 - f0 >= FPS // 2:          # ignore flickers under half a second
            out.append([max(0, f0 - 4), min(frames30, f1 + 4)])
    return out


def logo_hide_windows(clip, logo, frames30, top_win, pad=26):
    """Windows where the footage has put something under the mark's own
    rectangle — a thin wrapper over measure_hide_windows(); see there."""
    x0 = WIDTH - logo["right"] - logo["width"]
    x1 = WIDTH - logo["right"]
    y0 = logo["y"]
    y1 = logo["y"] + logo["width"] * 0.42
    return measure_hide_windows(clip, x0, y0, x1, y1, frames30, top_win, pad)


def load_top_occupied(work):
    """Frames where a burned-in graphic covers the TOP caption band, from
    scan_overlays. Returns a sorted list of [startFrame, endFrame] windows, or
    [] if the scan has not run (then everything defaults to the top zone, i.e.
    the original always-at-the-top layout)."""
    f = work / "overlays.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())["regions"]["top"]["occupied"]


def load_bottom_occupied(work):
    """Frames where a burned-in graphic covers the BOTTOM caption band, and
    the source-pixel y-range that scan covered (so a hazard is only trusted
    once it is checked for spatial relevance — see solve_doctor_plate).
    ([], None) if the scan has not run.

    This scan has the same median trap load_top_occupied's caller works
    around (see measure_hide_windows): scan_overlays' bottom-band "clean"
    plate is the per-pixel median over the WHOLE take, so on a clip that is
    graphic for more than half its length that median IS the graphic, and it
    can flag the clean part of the take while missing the covered part
    (measured on pcos-sleep-cycle, see README). That is why this is only
    ever used as a coarse, fast pre-filter for a lower-third graphic — the
    plate's own rectangle is always also measured directly."""
    f = work / "overlays.json"
    if not f.exists():
        return [], None
    d = json.loads(f.read_text())["regions"]["bottom"]
    return d["occupied"], d.get("bandPx")


def occupied_at(windows, frame):
    return any(a <= frame < b for a, b in windows)


def occupied_frac(windows, a, b):
    if b <= a:
        return 0.0
    covered = sum(max(0, min(b, w1) - max(a, w0)) for w0, w1 in windows)
    return covered / (b - a)


def blank_windows(windows, lo, hi):
    """Complement of `windows` within [lo, hi] — the stretches where the top is
    clear."""
    blanks, cur = [], lo
    for w0, w1 in sorted(windows):
        if w1 <= lo or w0 >= hi:
            continue
        if w0 > cur:
            blanks.append([cur, min(w0, hi)])
        cur = max(cur, w1)
    if cur < hi:
        blanks.append([cur, hi])
    return blanks


# Frames of clearance required on each side of a top-zone chunk. The caption
# must be fully gone before a burned-in graphic arrives, not merely mostly gone.
ZONE_MARGIN = 8


def zoom_blank_wins(top_win, answer0, video_frames, plate_span, ease, min_len):
    """Windows where the zoomBlankTop filler may stretch the footage: the
    complement of the burned-in graphic windows inside the answer, minus the
    plate's own span — the plate is the filler the zoom replaces, so the two
    must never share frames (on best-diet the zoom pushed her head up into the
    name label)."""
    wins, prev = [], answer0
    for a, b in top_win:
        wins.append([prev, a])
        prev = b
    wins.append([prev, video_frames])
    if plate_span:
        pa, pb = plate_span
        split = []
        for a, b in wins:
            if pb <= a or pa >= b:
                split.append([a, b])
                continue
            if a < pa:
                split.append([a, min(pa, b)])
            if b > pb:
                split.append([max(pb, a), b])
        wins = split
    return [[a, b] for a, b in wins if b - a >= min_len]


def auto_zone(spec, chunk_from, chunk_to, key_from, top_win):
    """Pick a chunk's zone from the footage. A chunk sits at the top ONLY when
    the top band is clear for the whole of its life plus a margin either side.

    The earlier rule allowed the top whenever a graphic covered less than half
    the beat, which is how a caption ended up laid over the illustration for the
    second or so of overlap at each end: it was still on screen when the graphic
    arrived. Partial clearance is not clearance — anything that is not clear
    throughout goes low, so the text has already moved before the top fills.

    An explicit zone in the brief always wins."""
    if "zone" in spec:
        return spec["zone"]
    if not top_win:
        return "top"
    if occupied_frac(top_win, chunk_from - ZONE_MARGIN, chunk_to + ZONE_MARGIN) > 0:
        return "bottom"
    return "top"


# ---- fixed-rectangle placement: the doctor plate and the mark -------------
# Both are static boxes laid over a live take for a few seconds at a time.
# The old rule for the plate reasoned about the ZONE NAME of whichever chunk
# overlapped its default slot in time, and moved it to the OTHER zone's usual
# spot without checking what actually renders there — which is how a plate
# pushed up to dodge a low caption could land squarely on a TOP caption
# instead (measured below, on pcos-sleep-cycle). This solver instead checks
# real rectangles, in both space and time, against every hazard: caption
# text (motion-padded, so a still-animating chunk still counts), the scrim,
# the mark, a burned-in graphic measured directly under the candidate's own
# rectangle, the bottom-band scan, and the platform's safe area.

PLATE_HOLD_FLOOR = ms(900)     # below this a title card reads as a flash
RECT_HAZARD_PAD = 20           # px of daylight required around a hazard box


def rect_overlap(a, b, pad=0):
    """Do two (x0,y0,x1,y1) rectangles overlap, with `pad` px of margin
    required around `a`? Used to decide whether a hazard is even in the
    running for a given candidate rectangle before its time windows are
    consulted at all."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (ax0 - pad) < bx1 and bx0 < (ax1 + pad) and (ay0 - pad) < by1 and by0 < (ay1 + pad)


def find_clear_slot(hazards, lo, hi, target_len, floor_len):
    """Earliest slot in [lo, hi) of length >= floor_len (up to target_len)
    that overlaps NONE of `hazards`' windows. None if there is no such slot.

    Walks left to right: if the current start sits inside a hazard, jump
    past it; otherwise the run extends to the next hazard's start (or `hi`),
    and if that run clears the floor it is the answer — earliest always wins,
    per "prefer a slot early in the answer"."""
    # Windows arrive as a mix of lists (from JSON / measured scans) and
    # tuples (built in-line here); normalise before sorting a mixed bag.
    busy = sorted(tuple(w) for _, wins in hazards for w in wins)
    start = lo
    while start <= hi - floor_len:
        blocking = [b for a, b in busy if a <= start < b]
        if blocking:
            start = max(blocking)
            continue
        end = min([a for a, b in busy if a > start] + [hi])
        if end - start >= floor_len:
            return start, min(end, start + target_len)
        start = end
    return None


def least_bad_slot(hazards, lo, hi, length, step=5):
    """No slot is fully clear — used only as a last resort. Grid-searches for
    the slot that minimises total hazard overlap (frame-seconds of collision,
    summed across every hazard that touches it), so the failure is at least
    the smallest one available, and returns what it collides with so the
    build log can say so instead of shipping it silently."""
    best = None
    start = lo
    while start <= hi - length:
        slot = (start, start + length)
        detail = []
        for label, wins in hazards:
            ov = sum(max(0, min(slot[1], b) - max(slot[0], a)) for a, b in wins)
            if ov:
                detail.append((label, ov))
        total = sum(ov for _, ov in detail)
        if best is None or total < best[0]:
            best = (total, start, detail)
        start += step
    if best is None:
        return lo, lo + length, []
    _, start, detail = best
    return start, start + length, detail


def nearest_gap(labels, hazards, f0, f1):
    """Frames between [f0,f1) and the closest window under any of `labels` —
    0 if one already overlaps, None if none of those hazards apply here."""
    by_label = dict(hazards)
    gaps = []
    for lbl in labels:
        for a, b in by_label.get(lbl, []):
            gaps.append(0 if (a < f1 and b > f0) else (f0 - b if b <= f0 else a - f1))
    return min(gaps) if gaps else None


def rect_spatial_gap(a, b):
    """Shortest push, in px, that would separate two non-overlapping
    rectangles — used to report the mark's clearance from a plate that
    never shares its time window with it at all."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return max(ax0 - bx1, bx0 - ax1, ay0 - by1, by0 - ay1, 0)


def plate_rect(dp, top, left=None):
    """The plate's TRUE visible rectangle — the pill, not the file's
    transparent padding — from targetPillWidth and the measured pill aspect.
    Mirrors exactly how DoctorVideo.tsx positions the artwork (see
    DoctorPlate there): fileLeft = left - pillX*k puts the pill's own left
    edge at `left`, not the file's."""
    left = dp["left"] if left is None else left
    k = dp["targetPillWidth"] / dp["pillWidth"]
    h = dp["pillHeight"] * k
    return left, top, left + dp["targetPillWidth"], top + h


def solve_doctor_plate(brief, layout, scrim, chunks, top_win, work, clip, M,
                       extra_hazards=None):
    """Choose where and when the doctor's title card appears — see the
    README ("The plate answers to the frame, not just the zone") for the
    failure this replaced. Returns (plate_from, ok, report_line); mutates
    layout["doctorPlate"]'s "top" and "holdFrames" in place, matching the
    mutate-in-place style the rest of this module uses for layout.

    `extra_hazards` is [(label, rect-or-None, windows)] from supporting
    visuals; a None rect blocks the plate wherever it is (she is off screen)."""
    dp = layout["doctorPlate"]
    pin = (brief.get("layout") or {}).get("doctorPlate", {})
    video_frames = clip["frames30"]
    default_hold = dp.get("holdFrames", ms(1900))
    answer_start = chunks[0]["fromFrame"]

    pill_h = dp["pillHeight"] * (dp["targetPillWidth"] / dp["pillWidth"])
    safe_top = HEIGHT * layout["safeArea"]["topPct"] / 100
    safe_bottom = min(HEIGHT * (1 - layout["safeArea"]["bottomPct"] / 100), HEIGHT - 250)

    # Two candidate anchors: LOW, over the subject near the bottom, where the
    # plate has always lived; HIGH, tucked just under the top zone's own top
    # edge, for a clip whose low band is busy with captions or a scrim for
    # most of the take. Both are clamped into the safe area up front, rather
    # than discovered to violate it later — the shipped LAYOUT default
    # (top:1430) is 43px past the 15% bottom safe line for this doctor's
    # plate aspect, which is exactly the kind of thing this solver exists to
    # catch rather than repeat.
    high_top = layout["topZone"]["top"] + 40
    low_top = int(min(dp.get("top", LAYOUT["doctorPlate"]["top"]), safe_bottom - pill_h))
    anchors = ([("pinned", dp["top"])] if "top" in pin
               else [("low", low_top), ("high", high_top)])

    pad_in, pad_out = M["chunkInFrames"], M["chunkOutFrames"]
    zone_box = {
        "top": (0, layout["topZone"]["top"], WIDTH,
                layout["topZone"]["top"] + layout["topZone"]["height"]),
        "bottom": (0, layout["bottomZone"]["top"], WIDTH,
                   layout["bottomZone"]["top"] + layout["bottomZone"]["height"]),
    }
    # Every caption chunk's on-screen window, padded by its own in/out motion
    # on both ends: a chunk still fading in or out is still on screen, so the
    # raw fromFrame/toFrame alone under-counts what the plate can collide with.
    caption_wins = {"top": [], "bottom": []}
    for c in chunks:
        caption_wins[c["zone"]].append(
            (max(0, c["fromFrame"] - pad_in), c["toFrame"] + pad_out))

    scrim_rect = (0, scrim.get("top", HEIGHT), WIDTH, HEIGHT)
    # The scrim is only live exactly when a bottom chunk is (CaptionScrim.tsx
    # takes the max over bottom-chunk visibilities), so it shares that chunk's
    # padded windows rather than needing its own measurement.
    scrim_wins = caption_wins["bottom"] if scrim.get("enabled") else []

    bottom_occ, bottom_band = load_bottom_occupied(work)
    bottom_rect = None
    if bottom_band:
        s = HEIGHT / clip["height"]
        bottom_rect = (0, bottom_band[0] * s, WIDTH, bottom_band[1] * s)

    logo = layout["logo"]
    logo_rect = (WIDTH - logo["right"] - logo["width"], logo["y"],
                 WIDTH - logo["right"], logo["y"] + logo["width"] * 0.42)
    logo_wins = logo_hide_windows(clip["clip"], logo, video_frames, top_win)

    fixed_window = (dp["appearFrame"], dp["appearFrame"] + default_hold) \
        if "appearFrame" in dp else None

    best = None
    for name, top in anchors:
        rect = plate_rect(dp, top)
        # "hard" hazards are trusted enough to block a slot outright: real
        # caption timing (we built it ourselves, it is not a guess), the
        # scrim and mark (same), and the plate's OWN rectangle measured
        # directly. "soft" hazards still get reported and still count in the
        # least-bad fallback, but never veto an otherwise-clear slot — the
        # bottom-band overlays scan is the one soft hazard here, because its
        # own "clean" plate is the take's per-pixel median (see
        # load_bottom_occupied): on pcos-sleep-cycle, which is graphic for
        # just under half its length, that median is skewed enough that the
        # scan flags the SAFE early minutes and clears the actually-covered
        # full-screen stretch — trusting it as a hard veto erased the one
        # genuinely clear window this clip has. The plate's own direct
        # measurement below does not have this failure mode and is what
        # actually has to be relied on.
        hard, soft = [], []
        if top < safe_top or top + pill_h > safe_bottom:
            hard.append(("safe area", [(0, video_frames)]))
        for zn in ("top", "bottom"):
            if rect_overlap(rect, zone_box[zn], RECT_HAZARD_PAD):
                hard.append((f"{zn} caption", caption_wins[zn]))
        if scrim.get("enabled") and rect_overlap(rect, scrim_rect, RECT_HAZARD_PAD):
            hard.append(("scrim", scrim_wins))
        if bottom_rect and rect_overlap(rect, bottom_rect, RECT_HAZARD_PAD):
            soft.append(("burned-in graphic, bottom-band scan", bottom_occ))
        if rect_overlap(rect, logo_rect, RECT_HAZARD_PAD):
            hard.append(("mark", logo_wins))
        # The measurement that actually matters most: the plate's own
        # rectangle, scanned directly against the footage, the same way the
        # mark's rectangle already is. This is what catches a full-screen
        # graphic regardless of which caption band the scan attributes it to.
        graphic_wins = measure_hide_windows(clip["clip"], *rect, video_frames, top_win)
        hard.append(("graphic under the plate", graphic_wins))
        for label, xrect, xwins in (extra_hazards or []):
            if xrect is None or rect_overlap(rect, xrect, RECT_HAZARD_PAD):
                hard.append((label, xwins))
        hazards = hard + soft

        if fixed_window:
            f0, f1 = fixed_window
            detail = [(lbl, sum(max(0, min(f1, b) - max(f0, a)) for a, b in wins))
                      for lbl, wins in hazards]
            detail = [(l, o) for l, o in detail if o]
            hard_labels = {lbl for lbl, _ in hard}
            ok = not any(l in hard_labels for l, _ in detail)
        else:
            clear = find_clear_slot(hard, answer_start, video_frames,
                                     default_hold, PLATE_HOLD_FLOOR)
            if clear:
                f0, f1 = clear
                # A hard-clear slot can still brush a soft hazard; report it
                # but it does not cost the slot its "clear" verdict.
                detail = [(lbl, sum(max(0, min(f1, b) - max(f0, a)) for a, b in wins))
                          for lbl, wins in soft]
                detail = [(l, o) for l, o in detail if o]
                ok = True
            else:
                f0, f1, detail = least_bad_slot(hazards, answer_start, video_frames,
                                                 PLATE_HOLD_FLOOR)
                ok = False

        # Earliest fully-clear slot wins outright; among clear slots (or among
        # least-bad ones) the low anchor is preferred as the tie-break — it is
        # where the plate has always read best when nothing forces it up.
        score = (0 if ok else 1, f0 if ok else sum(o for _, o in detail), name != "low")
        cand = dict(name=name, top=top, rect=rect, f0=f0, f1=f1,
                    hazards=hazards, detail=detail, ok=ok, score=score)
        if best is None or cand["score"] < best["score"]:
            best = cand

    dp["top"] = best["top"]
    dp["holdFrames"] = max(PLATE_HOLD_FLOOR, best["f1"] - best["f0"])
    graphic_pct = occupied_frac(dict(best["hazards"]).get("graphic under the plate", []),
                                 best["f0"], best["f1"])
    cap_gap = nearest_gap(["top caption", "bottom caption", "scrim"],
                          best["hazards"], best["f0"], best["f1"])
    if rect_overlap(best["rect"], logo_rect):
        mg = nearest_gap(["mark"], best["hazards"], best["f0"], best["f1"])
        mark_txt = f"mark {mg}f away" if mg else "mark overlapping in time"
    else:
        mark_txt = f"mark {int(round(rect_spatial_gap(best['rect'], logo_rect)))}px clear"
    bits = [f"graphic {graphic_pct:.0%}"]
    bits.append(f"nearest caption {cap_gap}f away" if cap_gap is not None
                else "no caption in this band")
    bits.append(mark_txt)
    top_disp = round(best["top"], 1) if best["top"] != int(best["top"]) else int(best["top"])
    status = "clear" if best["ok"] else "NOT CLEAR"
    line = (f"  title card at f{best['f0']} ({best['f0']/FPS:.1f}s), "
            f"held {dp['holdFrames']}f, {best['name']} anchor y={top_disp} — "
            f"{status}: {', '.join(bits)}")
    # A hard-clear slot can still sit inside the bottom-band overlays' flagged
    # window — a diagnostic note, not a failure, since that scan is the one
    # known to be unreliable on a clip that is graphic for close to half its
    # length (see the comment above). Surfaced so a person can sanity-check
    # it, never silently.
    soft_hit = dict(best["detail"]).get("burned-in graphic, bottom-band scan")
    if best["ok"] and soft_hit:
        line += (f"\n  note: {soft_hit}f of this slot is inside the bottom-band "
                 f"overlays scan's flagged window — that scan is known-unreliable "
                 f"on a clip this graphic-heavy (see load_bottom_occupied); the "
                 f"direct measurement above is what was trusted.")
    if not best["ok"]:
        why = "; ".join(f"{lbl} {ov}f" for lbl, ov in best["detail"])
        line += (f"\n  WARNING: no fully clear slot found for the doctor plate — "
                 f"picked the least-bad. Colliding with: {why}")
    return best["f0"], best["ok"], line


def solve_mark_anchor(brief, layout, scrim, chunks, plate_rect_final, plate_window,
                       clip, top_win, logo_from, video_frames, M, extra_hazards=None):
    """Choose the mark's corner as a decision, not a fixed spot with a hide
    fallback. AnimatedLogo positions purely from layout.logo.right/y (see
    DoctorVideo.tsx) — no render change is needed to move it, only a
    different number here. Two candidates on the band the mark has always
    occupied, mirrored left/right; scored by how much of the mark's natural
    on-screen life (logoFromFrame -> end) each would still have to hide for.
    Hiding stays the fallback for whatever a moved anchor still can't clear,
    not the first answer."""
    logo = layout["logo"]
    pin = (brief.get("layout") or {}).get("logo", {})

    def visual_wins(rect):
        # An inset card is a hazard like a burned-in graphic: the mark steps
        # aside for it. Full-frame visuals carry no rect and keep the mark.
        return [tuple(w) for label, xrect, xwins in (extra_hazards or [])
                if xrect is not None and rect_overlap(rect, xrect, RECT_HAZARD_PAD)
                for w in xwins]

    if "right" in pin:
        wins = logo_hide_windows(clip["clip"], logo, video_frames, top_win)
        if extra_hazards:
            wins = list(wins) + visual_wins(
                (WIDTH - logo["right"] - logo["width"], logo["y"],
                 WIDTH - logo["right"], logo["y"] + logo["width"] * 0.42))
        return "pinned", logo, wins

    pad_in, pad_out = M["chunkInFrames"], M["chunkOutFrames"]
    zone_box = {
        "top": (0, layout["topZone"]["top"], WIDTH,
                layout["topZone"]["top"] + layout["topZone"]["height"]),
        "bottom": (0, layout["bottomZone"]["top"], WIDTH,
                   layout["bottomZone"]["top"] + layout["bottomZone"]["height"]),
    }
    caption_wins = {"top": [], "bottom": []}
    for c in chunks:
        caption_wins[c["zone"]].append(
            (max(0, c["fromFrame"] - pad_in), c["toFrame"] + pad_out))
    scrim_rect = (0, scrim.get("top", HEIGHT), WIDTH, HEIGHT)

    candidates = [("upper-right", dict(logo, right=38)),
                  ("upper-left", dict(logo, right=WIDTH - logo["width"] - 38))]
    best = None
    for name, cand in candidates:
        rect = (WIDTH - cand["right"] - cand["width"], cand["y"],
                WIDTH - cand["right"], cand["y"] + cand["width"] * 0.42)
        wins = list(logo_hide_windows(clip["clip"], cand, video_frames, top_win))
        for zn in ("top", "bottom"):
            if rect_overlap(rect, zone_box[zn], RECT_HAZARD_PAD):
                wins += caption_wins[zn]
        if scrim.get("enabled") and rect_overlap(rect, scrim_rect, RECT_HAZARD_PAD):
            wins += caption_wins["bottom"]
        if plate_rect_final and rect_overlap(rect, plate_rect_final, RECT_HAZARD_PAD):
            wins += [plate_window]
        if extra_hazards:
            wins += visual_wins(rect)
        hide_frac = occupied_frac(wins, logo_from, video_frames)
        score = (hide_frac, name != "upper-right")
        if best is None or score < best[0]:
            best = (score, name, cand, wins)
    _, name, cand, wins = best
    return name, cand, wins


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    project = Path(sys.argv[1])
    work = project / "work"
    brief = json.loads((project / "brief.json").read_text())
    words = json.loads((work / "words.json").read_text())["words"]
    scene = json.loads((work / "scene.json").read_text()) if (work / "scene.json").exists() else {}
    clip = json.loads((work / "clip.json").read_text())
    top_win = load_top_occupied(work)

    theme = deep_merge(THEME, brief.get("theme"))
    # The type pairing is an axis like the palette is, not a constant. Absent
    # key -> nothing runs and THEME's own Playfair/Anton stands, which is what
    # all four shipped clips get; "auto" asks the register for a pairing
    # neither of the last two reels used. Applied here, before TK/TL are read
    # at the sizing step, because `key_size` measures against the payload face:
    # a pairing swapped in after that point would size the old font's metrics.
    pairing_name = (brief.get("style") or {}).get("typePairing")
    if pairing_name and pairing_name in ("auto",) + tuple(typography_engine.PAIRINGS):
        # propose() returns (axes, slugs); the current brief is deliberately
        # not passed — it pins "auto", which is a request for a proposal, not a
        # value, and _pinned would hand it straight back.
        resolved = (register_engine.propose()[0]["typePairing"]["value"]
                    if pairing_name == "auto" else pairing_name)
        pairing = typography_engine.PAIRINGS[resolved]
        theme = deep_merge(theme, {"type": {"lead": pairing["lead"],
                                            "key": pairing["key"]}})
        print(f"  type pairing: {resolved} — "
              f"{pairing['lead']['fontFamily']} over {pairing['key']['fontFamily']}")
    layout = deep_merge(LAYOUT, brief.get("layout"))

    # Palette is derived automatically from the measured background (palette.py:
    # measure -> APCA-checked elegant mix), then a brief can override any part.
    palf = work / "palette.json"
    autopal = json.loads(palf.read_text()) if palf.exists() else palette_engine.compute(project)
    ztop, zbot = autopal["zones"]["top"], autopal["zones"]["bottom"]

    # A scrim changes what the caption is measured against. Without one, the
    # background is the footage — and on a clip like this that footage is
    # bimodal (bright saree AND a black microphone in the same band), so no
    # flat colour clears both ends and the type has to be rescued by an
    # outline. With a scrim, the ground is the scrim, it is uniform, and a
    # single light tone reads on it cleanly with no outline at all.
    scrim = layout["captionScrim"]
    if scrim.get("enabled"):
        # The ground is derived from the measured wall unless a brief pins a
        # colour outright, so the panel belongs to the room it sits in. Its
        # POLARITY is the per-clip decision — and it decides everything
        # downstream, because which half of the palette can be read depends
        # entirely on what is behind the type.
        polarity = scrim.get("ground", "dark")
        # Only a colour pinned by THIS brief counts as pinned. The merged
        # layout always carries the module default, so testing the merged
        # value would mean the ground was never derived at all.
        pinned = (brief.get("layout") or {}).get("captionScrim", {}).get("color")
        if not pinned:
            scrim = dict(scrim, color=palette_engine.ground_from(
                autopal["scene"]["wall"], polarity))
            layout = dict(layout, captionScrim=scrim)
        ground = over(scrim["color"], zbot["bg"], scrim.get("opacity", 0.9))
        # The palette half follows the ground, because a colour is only legible
        # against what is behind it. On a DARK panel the deep tones score in
        # the single digits, so the rotation takes their light-flipped
        # counterparts — spring green for forest, coral for brick — kept vivid
        # rather than neutral, with a warm white as a breather. On a LIGHT
        # panel the reverse: the deep forest/brick/teal register reads, and
        # the pale tones vanish. Either way the brand tone is held back as the
        # accent so it lands on the takeaway rather than being spent early.
        if palette_engine.is_dark(ground):
            # periwinkle appended after the four that have always shipped
            # (spring green / warm white / blush / mint), so an unmodified
            # brief keeps the exact rotation it always has; a brief that
            # sets style.paletteLead moves its choice to the front instead.
            prefer = ["spring green", "warm white", "blush", "mint",
                      "periwinkle", "saffron", "cream"]
            accent_prefer = ["saffron", "honey gold", "cream yellow"]
        else:
            prefer = ["forest", "brick", "deep teal", "plum", "indigo",
                      "deep chocolate", "rust"]
            accent_prefer = ["rust", "brick", "forest"]
        lead_pref = brief.get("style", {}).get("paletteLead")
        if lead_pref in prefer:
            prefer = [lead_pref] + [p for p in prefer if p != lead_pref]
        zbot = dict(zbot, bg=ground,
                    rotation=palette_engine.mixed_rotation(
                        ground, prefer, floor_dark=60, floor_light=45, n=4),
                    accent=palette_engine.best(ground, 45, accent_prefer))
    nl = palette_engine.nearby_lead
    base_palette = {
        "scene": autopal["scene"],
        "onLight": {"lead": nl(ztop["rotation"][0]["hex"], ztop["bg"]),
                    "key": ztop["rotation"][0]["hex"],
                    "keyAlt": ztop["accent"]["hex"], "muted": "#5A4636"},
        "onDark": autopal["onDark"],
        "bottomText": {"lead": nl(zbot["rotation"][0]["hex"], zbot["bg"]),
                       "key": zbot["rotation"][0]["hex"],
                       "keyAlt": zbot["accent"]["hex"]},
    }
    palette = deep_merge(base_palette, brief.get("palette"))
    TK, M = theme["type"]["key"], theme["motion"]
    video_frames = clip["frames30"]
    avail = WIDTH - 2 * layout["topZone"]["paddingX"]

    # ---- question rows (accumulate on the question card) ------------------
    card = hook_card(brief)
    q_rows = []
    for row in brief.get("question", {}).get("rows", []):
        r = dict(row)
        r["appearFrame"] = words[r["words"][0]]["startFrame"]
        r["text"] = " ".join(words[i]["word"] for i in r["words"])
        if r["style"] == "key":
            r["size"] = key_size(r["lines"], TK, avail, question=True)
        q_rows.append(r)

    # ---- answer chunks: a quiet lead, then the payload --------------------
    def w(i):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else words[i]["end"] + 0.4
        return {"index": i, "text": words[i]["word"],
                "startFrame": words[i]["startFrame"],
                "activeFromFrame": words[i]["startFrame"],
                "activeToFrame": f(nxt)}

    TL = theme["type"]["lead"]
    avail_top = WIDTH - 2 * layout["topZone"]["paddingX"]
    avail_bottom = WIDTH - 2 * layout["bottomZone"]["paddingX"]

    answer_words = [w(i) for i in range(len(words))]
    specs = brief["chunks"]
    # Where the zoomBlankTop filler will run, the top is NOT free — the zoom
    # fills it with her head, so beats there sit low (on best-diet the hero
    # captions landed on her zoomed face). Estimated plate span, since the
    # plate solves later; the data pass below re-checks with the real one.
    zone_zoom = []
    if (brief.get("style") or {}).get("zoomBlankTop"):
        ze = int((brief.get("style") or {}).get("zoomEaseFrames", 15))
        a0 = words[(specs[0]["lead"] or specs[0]["key"])[0]]["startFrame"]
        _dp = layout["doctorPlate"]
        plate_est = (a0 + ms(800), a0 + ms(800) + _dp.get("holdFrames", ms(1900)))
        zone_zoom = zoom_blank_wins(top_win, a0, video_frames, plate_est,
                                    ze, 2 * ze + 6)
    zone_wins = sorted(top_win + zone_zoom)
    # Supporting visuals (brief.visuals, opt-in). An inset card on the wall is
    # a graphic as far as the captions know, so its windows join the burned-in
    # ones and that beat drops low. Absent -> vplan stays None, nothing runs.
    vplan = None
    if visuals_engine.enabled(brief):
        vplan = visuals_engine.plan_for_build(project, brief, words, video_frames,
                                              top_win, scene, layout, M)
        zone_wins = sorted(zone_wins + vplan["topBlock"])
    zpal = {"top": ztop, "bottom": zbot}
    rot_i = {"top": 0, "bottom": 0}   # per-zone rotation counter
    # Per-clip default for the lead/payload colour relationship; a beat can
    # still override it. Rotate this between reels — see README Part 2.
    lead_style = brief.get("style", {}).get("leadStyle") or (
        "match" if layout["captionScrim"].get("enabled") else "tint")
    chunks = []
    kept_specs = []          # specs that became chunks, in chunk order
    skipped, candidates = [], []
    for n, spec in enumerate(specs):
        first = (spec["lead"] or spec["key"])[0]
        nxt = specs[n + 1] if n + 1 < len(specs) else None
        end = (words[(nxt["lead"] or nxt["key"])[0]]["startFrame"] if nxt
               else min(words[spec["key"][-1]]["endFrame"] + ms(700),
                        video_frames - M["chunkOutFrames"]))
        # zone: "top" (big, on the bare wall) when the top half is blank;
        # "bottom" (low, on the subject) when a baked-in graphic occupies the
        # top half. Derived from scan_overlays automatically; brief overrides.
        first_frame = words[first]["startFrame"]
        zone = auto_zone(spec, first_frame, end, words[spec["key"][0]]["startFrame"], zone_wins)
        av = avail_bottom if zone == "bottom" else avail_top

        # A caption is not owed to every sentence. When the footage already
        # carries the point — a burned-in graphic naming the same benefit, a
        # diagram doing the explaining — a caption underneath repeats rather
        # than reinforces, and the frame is quieter and stronger without it.
        # `skip` in a brief drops the beat; beats that merely *overlap* a
        # graphic are reported as candidates for a person to judge.
        share = occupied_frac(top_win, first_frame, end)
        if spec.get("skip"):
            skipped.append((n + 1, "/".join(spec["lines"]), share, spec.get("_skipWhy", "")))
            continue
        if share >= 0.75:
            candidates.append((n + 1, "/".join(spec["lines"]), share))

        # Per-beat colour: stats/accent beats take the zone accent; the rest
        # rotate through the zone's elegant mix (chocolate / white / dark red /
        # cool). The small lead line is paired to the payload's polarity — dark
        # payload gets a light lead, light payload a dark lead — so the two
        # lines are always two distinct colours. A brief can pin keyColor.
        Z = zpal[zone]
        if spec.get("tone") == "keyAlt":
            kc = Z["accent"]
        else:
            kc = Z["rotation"][rot_i[zone] % len(Z["rotation"])]
            rot_i[zone] += 1
        key_color = spec.get("keyColor", kc["hex"])
        key_dark = palette_engine.is_dark(key_color)
        # How the small lead line relates to the payload. Three ways, and the
        # point is to ROTATE them between reels rather than always doing one:
        #
        #   match    one colour — lead and payload the same tone, separated by
        #            size and italic alone. Quiet, safe on a busy ground.
        #   neutral  two colours — the payload takes the rotation colour and
        #            the lead a deep/pale NEUTRAL. This is the
        #            pcos-insulin-resistance look: brown italic over forest
        #            caps. It works because a neutral and a colour are far
        #            apart; two mid-tone colours would just muddy each other,
        #            which is what the earlier chocolate-over-brown beats did.
        #   tint     the lead is a nearby tint of the payload — a tonal pair.
        #            The default off a scrim.
        mode = spec.get("leadStyle", lead_style)
        if mode == "neutral":
            default_lead = palette_engine.neutral_lead(
                autopal["scene"]["wall"],
                "dark" if palette_engine.is_dark(Z["bg"]) else "light",
                Z["bg"])
        elif mode == "match":
            default_lead = key_color
        else:
            default_lead = palette_engine.nearby_lead(key_color, Z["bg"])
        lead_color = spec.get("leadColor", default_lead)
        kept_specs.append(spec)
        chunks.append({
            "id": f"chunk-{n+1}",
            "zone": zone,
            "leadWords": spec["lead"],
            "leadText": " ".join(words[i]["word"] for i in spec["lead"]),
            "leadSize": TL["bottomAnswerSize"] if zone == "bottom" else TL["answerSize"],
            "leadColor": lead_color,
            "leadDark": palette_engine.is_dark(lead_color),
            "keyWords": spec["key"],
            "keyLines": spec["lines"],
            "keySize": key_size(spec["lines"], TK, av, zone=zone),
            "keyColor": key_color,
            "keyDark": key_dark,
            "tone": spec.get("tone", "key"),
            "fromFrame": words[first]["startFrame"],
            "toFrame": end,
            "keyFromFrame": words[spec["key"][0]]["startFrame"],
            # The ladder rule: beats that are rungs of a spoken list carry their
            # position, so the payload can show how far down the list it is.
            # Absent on beats that are not part of a list — the rule then hides.
            "listIndex": spec.get("listIndex"),
            "listTotal": spec.get("listTotal"),
        })

    # Her VOICE opens the answer, not the first caption: chunks may skip her
    # opening words (build-muscle speaks "So in any woman, usually" from 3.08s
    # but its first chunk starts at word 11), and keying the card's exit to the
    # chunk held the question on her face while she talked.
    q_span = {i for row in q_rows for i in (row.get("words") or [])}
    speech = next((words[i]["startFrame"] for i in range(len(words))
                   if i not in q_span), chunks[0]["fromFrame"])
    answer_start = min(chunks[0]["fromFrame"], speech)

    # ---- how each beat reveals -------------------------------------------
    # A caption that appears is not automatically a caption that should
    # animate — the same logic that says a beat under a burned-in graphic
    # wants no caption says a beat under a MOVING graphic wants no motion of
    # its own. Three levers, in precedence order: a per-beat "reveal" pin, a
    # clip-wide style.revealStyle, then style.autoMotion, which reads
    # work/audio.json and lets how she actually said the line pick the reveal.
    # None of the three set -> no `reveal` key is written at all and the TSX
    # resolves every beat to legacyMaskWipe, today's exact path. That is what
    # keeps the four shipped clips byte-identical.
    style = brief.get("style") or {}
    clip_pin = style.get("revealStyle")
    audio = None
    if style.get("autoMotion") and (work / "audio.json").exists():
        audio = json.loads((work / "audio.json").read_text())
        emph = sorted(w["emphasis"] for w in audio["words"])
        hero_floor = emph[int(0.9 * (len(emph) - 1))] if emph else 1.0
        by_idx = {w["index"]: w["emphasis"] for w in audio["words"]}
    if clip_pin or audio or any("reveal" in sp for sp in kept_specs):
        consec, notes = 0, []
        for chunk, spec in zip(chunks, kept_specs):
            if "reveal" in spec:
                chunk["reveal"] = spec["reveal"]
                notes.append((chunk["id"], chunk["reveal"], "pinned on the beat"))
            elif clip_pin:
                chunk["reveal"] = clip_pin
                notes.append((chunk["id"], clip_pin, "pinned for the clip"))
            elif audio:
                dur = chunk["toFrame"] - chunk["fromFrame"]
                beat_e = max((by_idx.get(i, 0.0) for i in chunk["keyWords"]), default=0.0)
                covered = (occupied_frac(top_win, chunk["fromFrame"], chunk["toFrame"])
                           if chunk["zone"] == "top" else 0.0)
                gesture = motion_engine.gesture_intensity(
                    clip["clip"], chunk["fromFrame"] / FPS, chunk["toFrame"] / FPS)
                is_hero = (chunk["zone"] == "top"
                           and not layout["captionScrim"].get("enabled")
                           and dur >= ms(1800) and beat_e >= hero_floor)
                animate, why = motion_engine.should_animate(
                    dur, covered, gesture, consec, is_hero)
                if animate:
                    chunk["reveal"] = motion_engine.choose_reveal(
                        dur, chunk["zone"], bool(layout["captionScrim"].get("enabled")),
                        beat_e, is_hero,
                        prior_styles=[c.get("reveal") for c in chunks
                                      if c.get("reveal")])["style"]
                    consec += 1
                else:
                    # Still legible, still arrives — it just does not perform.
                    chunk["reveal"] = "wordStagger"
                    consec = 0
                notes.append((chunk["id"], chunk["reveal"], why))
        print("\n  reveals:")
        for cid, styl, why in notes:
            print(f"   {cid}: {styl}  ({why})")

    # The brief's beat boundaries are read off the transcript, where a sentence
    # break looks obvious on the page. It is not always where she breathes.
    if (work / "audio.json").exists():
        warnings = audio_engine.check_chunk_boundaries(
            brief, words, json.loads((work / "audio.json").read_text()))
        if warnings:
            print("\n  chunk boundaries that do NOT fall in a measured pause:")
            for line in warnings:
                print(f"   {line}")

    # ---- panel geometry, derived from the subject ------------------------
    # Two ways to get this wrong, and both have been shipped: a long soft wash
    # that climbs the doctor's chin, and a hard cut that reads as a bar laid
    # across the frame. The fade wants to be gradual AND to begin below her
    # face, and how much room that leaves is a property of the clip, not a
    # number to guess. So: start below the measured chin, be solid by the time
    # the payload begins, and let the feather be whatever distance that is.
    if scrim.get("enabled") and scrim.get("feather") in (None, "auto"):
        bottom_beats = [c for c in chunks if c["zone"] == "bottom"]
        if bottom_beats:
            sample_t = [(c["keyFromFrame"] + c["toFrame"]) / 2 / FPS
                        for c in bottom_beats[:6]]
            chin = face_bottom(clip["clip"], sample_t)
            if chin:
                solid_top = layout["bottomZone"]["top"] + 100
                feather = max(FEATHER_MIN,
                              min(FEATHER_MAX, solid_top - (chin + CHIN_CLEARANCE)))
                scrim = dict(scrim, top=max(0, solid_top - feather), feather=feather)
                layout = dict(layout, captionScrim=scrim)
                print(f"  panel: chin measured at y={chin}; fades in over "
                      f"{feather}px from y={scrim['top']}, solid by y={solid_top}")
    # ---- doctor + partner (needed now: the plate solver measures the real
    # pill geometry, not a zone) ---------------------------------------------
    doctor, _ = resolve_doctor(brief["doctor"])
    partner = resolve_partner(brief.get("partner"), doctor)
    layout["doctorPlate"].update(pill_box(Path(doctor["platePath"])))

    # The title card's placement is solved for real rectangles against every
    # hazard — caption text (motion-padded), the scrim, the mark, a burned-in
    # graphic measured directly under its own rectangle, and the safe area —
    # rather than reasoning about which ZONE an overlapping chunk happened to
    # be in. See solve_doctor_plate() and the README ("The plate answers to
    # the frame, not just the zone").
    plate_from, plate_ok, plate_report = solve_doctor_plate(
        brief, layout, scrim, chunks, top_win, work, clip, M,
        extra_hazards=visuals_engine.plate_hazards(vplan["items"]) if vplan else None)
    dp = layout["doctorPlate"]

    # The mark's corner is a decision too, scored against the same hazards,
    # with hiding as the fallback rather than the first answer. See
    # solve_mark_anchor() and the README ("Where the mark goes").
    logo_from = answer_start + ms(800)
    mark_anchor, layout["logo"], logo_hide = solve_mark_anchor(
        brief, layout, scrim, chunks, plate_rect(dp, dp["top"]),
        (plate_from, plate_from + dp["holdFrames"]),
        clip, top_win, logo_from, video_frames, M,
        extra_hazards=visuals_engine.mark_hazards(vplan["items"]) if vplan else None)
    outro_enter = video_frames
    brands = {
        "kyros": {"label": "Kyros Clinic", "logo": {"enabled": True},
                  "outro": {"kind": "clip", "src": "outro.mp4",
                            "durationSeconds": 3.0}},
        "partner": {"label": partner["name"],
                    "logo": {"enabled": partner.get("logoInBody", False)},
                    "outro": {"kind": partner.get("outroKind", "logo-card"),
                              "src": "partner-logo.png",
                              "durationSeconds": partner.get("outroSeconds", 1.0),
                              "background": partner.get("outroBackground", "#FFFFFF"),
                              "logoWidth": partner.get("outroLogoWidth", 760)}},
    }
    for b in brands.values():
        b["outro"]["enterFrame"] = outro_enter
        b["outro"]["durationInFrames"] = int(round(b["outro"]["durationSeconds"] * FPS))
        b["durationInFrames"] = outro_enter + b["outro"]["durationInFrames"]

    # Blank-top filler: where no burned-in graphic covers the top band and the
    # question card is gone, the bare wall above her head reads as empty space.
    # A gentle zoom, eased at the window edges, fills it with her; wherever a
    # graphic IS burned in the zoom stays at 1 so the crop never touches the
    # artwork. The zoom and the plate never share frames (the plate solves to
    # the real span here), and a window that would carry a top caption is
    # dropped outright — her zoomed head is not a text background. Off unless
    # the brief's style asks for it.
    zoom = None
    if style.get("zoomBlankTop"):
        ease = int(style.get("zoomEaseFrames", 15))
        wins = zoom_blank_wins(
            top_win, answer_start, video_frames,
            (plate_from, plate_from + dp.get("holdFrames", ms(1900))),
            ease, 2 * ease + 6)
        wins = [w for w in wins
                if not any(c["zone"] == "top" and c["fromFrame"] < w[1]
                           and c["toFrame"] > w[0] for c in chunks)]
        if vplan:
            wins = visuals_engine.drop_overlapping(wins, vplan["items"])
        if wins:
            zoom = {"windows": wins,
                    "scale": float(style.get("zoomScale", 1.35)),
                    "easeFrames": ease}

    vout = None
    if vplan and vplan["items"]:
        vout = visuals_engine.finish_for_build(
            vplan, brief=brief, chunks=chunks, layout=layout, M=M, card=card,
            palette={"top": ztop, "bottom": zbot, "scene": autopal["scene"]},
            logo=layout["logo"], logo_hide=logo_hide, logo_from=logo_from,
            clip=clip, words=words, video_frames=video_frames, question_rows=q_rows)
        if vout["markHide"]:
            logo_hide = sorted([list(w) for w in logo_hide] + vout["markHide"])

    data = {
        "zoom": zoom,
        "meta": {"fps": FPS, "width": WIDTH, "height": HEIGHT,
                 "durationInFrames": brands["kyros"]["durationInFrames"],
                 "videoFrames": video_frames,
                 "videoSrc": "video.mp4", "audioSrc": "audio.m4a",
                 "slug": brief["slug"],
                 "style": brief.get("style", {}),
                 "frameFormula": "frame = round(seconds * 30)"},
        "theme": {"palette": palette, "type": theme["type"], "motion": M},
        "layout": layout,
        "compliance": {"doctor": doctor,
                       "openFlags": brief.get("openFlags", [])},
        # The mark obeys the footage for the same reason the captions do. It
        # sits in the upper-right, so a burned-in graphic that fills the top
        # lands underneath it — on pcos-sleep-cycle the mark came down squarely
        # on the insulin-resistance illustration. It hides for the duration of
        # any such window and returns when the frame is the doctor's again.
        "fixtures": {"plateFromFrame": plate_from, "logoFromFrame": logo_from,
                     "logoHideWindows": logo_hide},
        "brands": brands,
        "phases": [
            {"id": "question", "kind": "hook",
             "card": card,
             "scrimOpacity": card["opacity"],
             "exitFrame": answer_start - M["scrimFrames"],
             "exitDurationInFrames": M["scrimFrames"],
             "rows": q_rows},
            {"id": "answer", "kind": "captions",
             "fromFrame": answer_start, "toFrame": video_frames,
             "chunks": chunks},
        ],
        "words": {"question": answer_words, "answer": answer_words},
    }
    if vout:
        data["visuals"] = vout["data"]
    (work / "captions_data.json").write_text(json.dumps(data, indent=2))

    print(f"wrote {work/'captions_data.json'}")
    if top_win:
        spans = ", ".join(f"{a/FPS:.1f}-{b/FPS:.1f}s" for a, b in top_win)
        print(f"  top-half graphic in the footage at {spans} -> those beats go low")
    else:
        print("  top half clear the whole take -> every beat sits up top")
    print(plate_report)
    hide_txt = (", ".join(f"{a/FPS:.1f}-{b/FPS:.1f}s" for a, b in logo_hide)
                if logo_hide else "never")
    print(f"  mark: {mark_anchor} anchor (right={layout['logo']['right']}, "
          f"y={layout['logo']['y']}) — hides {hide_txt}")
    print(f"  kyros   {brands['kyros']['durationInFrames']}f "
          f"({brands['kyros']['durationInFrames']/FPS:.2f}s)")
    print(f"  partner {brands['partner']['durationInFrames']}f "
          f"({brands['partner']['durationInFrames']/FPS:.2f}s)  "
          f"-> {partner['name']}")
    print(f"  palette (measured): wall {autopal['measured']['wall']}  "
          f"saree {autopal['measured']['saree']}")
    for c in chunks:
        print(f"   f{c['fromFrame']:>4}-{c['toFrame']:<4} [{c['zone']:>6}] "
              f"lead {c['leadColor']} / key {c['keyColor']}  "
              f"\"{c['leadText']}\" -> {' / '.join(c['keyLines'])} @{c['keySize']}px")
    if skipped:
        print("\n  skipped on purpose — the footage carries these itself:")
        for n, lines, share, why in skipped:
            print(f"   beat {n}: {lines}  ({share:.0%} of it under a burned-in "
                  f"graphic){'  — ' + why if why else ''}")
    if candidates:
        print("\n  SKIP CANDIDATES — a graphic covers most of these beats. If it"
              "\n  already says the same thing, set \"skip\": true on the beat:")
        for n, lines, share in candidates:
            print(f"   beat {n}: {lines}  ({share:.0%} covered)")
    if vplan:
        print("\n  supporting visuals:")
        for it in (vout["data"]["items"] if vout else []):
            where = (it.get("bubble") or {}).get("corner") or it.get("rect") or "full frame"
            print(f"   {it['id']}: {it['kind']} · {it['treatment']} · "
                  f"f{it['fromFrame']}-{it['toFrame']} ({it['fromFrame']/FPS:.1f}-"
                  f"{it['toFrame']/FPS:.1f}s) · {where}"
                  + (f"  · soft ground behind {len(it['captionWashes'])} caption(s)"
                     if it.get("captionWashes") else ""))
        for line in (vout["report"] if vout else vplan["report"]):
            print(line)
        if not (vout and vout["data"]["items"]):
            print("   none ready — this build is footage only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
