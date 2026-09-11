#!/usr/bin/env python3
"""Scan a raw clip for burned-in graphics, so the reel's own elements land in
the space the footage leaves free.

    python scripts/scan_overlays.py projects/<slug> [--debug]

A clip may arrive with graphics already composited into it — illustrations,
lower-thirds, on-screen text. Those cover parts of the frame at certain times,
and the reel's captions, title card and logo must not fight them. This maps,
over the whole take, when the TOP caption band and the BOTTOM caption band are
covered, and writes the occupied windows to work/overlays.json. build_captions
reads it to drop each caption into whichever half is clear at that moment.

Two regions, two methods, because their "clean" state differs:

  TOP    the clean state is a smooth wall. A burned-in graphic breaks that
         smoothness — it adds edges (spatial variance), near-white card panels,
         or saturated colour the wall does not have. Detected from the frame
         itself, since the wall is calm and any of those signals means "busy".

  BOTTOM the clean state is the subject, who is already busy. So "clean" is
         whatever sits there MOST of the take: the per-pixel median over time.
         A burned-in graphic is a large, sustained departure from that plate;
         a head turn or a moving hand is not.

Nothing here is clip-specific: a clean-plate clip (empty wall throughout, no
burned-in anything) reports no occupied windows, which reproduces the original
always-at-the-top layout.
"""
import json, subprocess, sys
from pathlib import Path

SAMPLE_FPS = 10
FPS = 30

# Bands as fractions of frame height. These are the zones captions live in, not
# the whole half — the platform UI covers the outer 15% and is left alone.
TOP_BAND = (0.06, 0.45)
BOTTOM_BAND = (0.55, 0.86)
SAMPLE_W = 100

# TOP: any one signal clearing its gate marks the frame busy. Tuned so a calm
# wall stays under all three and every graphic trips at least one.
TOP_STD = 25.0       # spatial stdev of luma
TOP_WHITE = 0.06     # fraction of near-white pixels (card panels)
TOP_SAT = 0.12       # fraction of vivid pixels (illustration colour)

# BOTTOM: fraction of the band that departs strongly from the median plate.
BOT_DIFF = 46        # per-pixel max-channel delta that counts as "changed"
BOT_FRAC = 0.30      # share of the band that must change to call it a graphic

MERGE_GAP_S = 0.34   # bridge windows split by a sub-frame flicker
MIN_WIN_S = 0.40     # drop blips shorter than this


def region_raw(clip, y0f, y1f, w, hc, wc):
    h = max(2, round(w * (hc * (y1f - y0f)) / wc))
    h -= h % 2
    vf = (f"crop=in_w:in_h*{y1f - y0f:.4f}:0:in_h*{y0f:.4f},"
          f"scale={w}:{h},fps={SAMPLE_FPS},format=rgb24")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", vf,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    size = w * h * 3
    n = len(raw) // size
    return [raw[i * size:(i + 1) * size] for i in range(n)], w, h


def top_busy(frame, w, h):
    """(std, white_frac, sat_frac) for one TOP-band frame."""
    n = w * h
    lum = [0.0] * n
    white = sat = 0
    s = s2 = 0.0
    for i in range(n):
        r, g, b = frame[3 * i], frame[3 * i + 1], frame[3 * i + 2]
        y = 0.299 * r + 0.587 * g + 0.114 * b
        lum[i] = y
        s += y; s2 += y * y
        if r > 205 and g > 205 and b > 205:
            white += 1
        mx, mn = max(r, g, b), min(r, g, b)
        if mx > 40 and (mx - mn) / mx > 0.40:
            sat += 1
    mean = s / n
    std = (max(0.0, s2 / n - mean * mean)) ** 0.5
    return std, white / n, sat / n


def bottom_busy(frames, w, h):
    """Per-frame changed-fraction vs the per-pixel median plate."""
    n = w * h
    med = bytearray(n * 3)
    for c in range(3):
        for i in range(n):
            col = sorted(fr[3 * i + c] for fr in frames)
            med[3 * i + c] = col[len(col) // 2]
    out = []
    for fr in frames:
        changed = 0
        for i in range(n):
            d = max(abs(fr[3 * i + c] - med[3 * i + c]) for c in range(3))
            if d > BOT_DIFF:
                changed += 1
        out.append(changed / n)
    return out


def smooth(flags):
    """Majority vote over a 3-sample window, to kill single-sample flicker."""
    out = list(flags)
    for i in range(len(flags)):
        lo, hi = max(0, i - 1), min(len(flags), i + 2)
        out[i] = sum(flags[lo:hi]) > (hi - lo) / 2
    return out


def windows(flags):
    """Boolean-per-sample -> merged, min-length frame windows."""
    runs, i, n = [], 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            runs.append([i, j - 1])
            i = j
        else:
            i += 1
    frm = lambda s: round(s / SAMPLE_FPS * FPS)
    wins = [[frm(a), frm(b + 1)] for a, b in runs]
    merged = []
    for w in wins:
        if merged and w[0] - merged[-1][1] <= MERGE_GAP_S * FPS:
            merged[-1][1] = w[1]
        else:
            merged.append(w)
    return [w for w in merged if w[1] - w[0] >= MIN_WIN_S * FPS]


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    project = Path(sys.argv[1])
    debug = "--debug" in sys.argv
    work = project / "work"
    meta = json.loads((work / "clip.json").read_text())
    clip = meta["clip"]
    wc, hc = meta["width"], meta["height"]

    tfrms, tw, th = region_raw(clip, *TOP_BAND, SAMPLE_W, hc, wc)
    bfrms, bw, bh = region_raw(clip, *BOTTOM_BAND, SAMPLE_W, hc, wc)

    top_flags, top_feat = [], []
    for fr in tfrms:
        std, wf, sf = top_busy(fr, tw, th)
        top_feat.append((std, wf, sf))
        top_flags.append(std > TOP_STD or wf > TOP_WHITE or sf > TOP_SAT)

    bot_scores = bottom_busy(bfrms, bw, bh)
    bot_flags = [s > BOT_FRAC for s in bot_scores]

    top_win = windows(smooth(top_flags))
    bot_win = windows(smooth(bot_flags))

    if debug:
        print("  t(s)   Tstd  Twhite  Tsat  Tbusy    Bfrac  Bbusy")
        for i in range(len(tfrms)):
            std, wf, sf = top_feat[i]
            bf = bot_scores[i] if i < len(bot_scores) else 0.0
            print(f"  {i / SAMPLE_FPS:5.1f}  {std:5.1f}  {wf:5.2f}  {sf:5.2f}"
                  f"   {'YES' if top_flags[i] else ' . '}    {bf:5.2f}"
                  f"  {'YES' if i < len(bot_flags) and bot_flags[i] else ' . '}")
        print()

    band_px = lambda b: [round(b[0] * hc), round(b[1] * hc)]
    secs = lambda ws: [[round(a / FPS, 2), round(b / FPS, 2)] for a, b in ws]
    data = {
        "fps": FPS, "sampleFps": SAMPLE_FPS,
        "regions": {
            "top": {"bandPx": band_px(TOP_BAND), "occupied": top_win,
                    "occupiedSeconds": secs(top_win)},
            "bottom": {"bandPx": band_px(BOTTOM_BAND), "occupied": bot_win,
                       "occupiedSeconds": secs(bot_win)},
        },
    }
    (work / "overlays.json").write_text(json.dumps(data, indent=2))

    def report(name, wins):
        if not wins:
            print(f"{name:7s} clear the whole take")
        else:
            spans = ", ".join(f"{a / FPS:.1f}-{b / FPS:.1f}s" for a, b in wins)
            print(f"{name:7s} burned-in graphic at  {spans}")
    print("burned-in graphics found in the raw clip:")
    report("top", top_win)
    report("bottom", bot_win)
    print("\ncaptions drop to the clear half automatically; the title card is "
          "timed to a blank-top window. wrote " + str(work / "overlays.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
