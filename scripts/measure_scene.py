#!/usr/bin/env python3
"""Measure the footage so colour and placement are decided by numbers.

    python scripts/measure_scene.py projects/<slug> [--at 6.0]

Reports the background colour where text will sit, WCAG contrast for candidate
palettes, and where the subject's head begins.

This exists because taste gets it wrong. On one shoot the wall measured
#E9C39F — light — and white type, the obvious choice from every reference reel,
scored 1.64:1. Unreadable. Dark type scored 7.4:1. Use what passes.
"""
import json, subprocess, sys
from pathlib import Path

# Large text (>=24px bold) needs 3:1 under WCAG; body needs 4.5:1. Captions at
# 100px+ are unambiguously large text, so 3:1 is the real floor here — but
# prefer candidates that clear 4.5:1 when any do.
CANDIDATES = {
    "white":      "#FFFFFF",
    "cream":      "#FFF6E8",
    "espresso":   "#2A1F17",
    "forest":     "#0F3D2E",
    "rust":       "#9E3B16",
    "saffron":    "#E08E3C",
    "deep navy":  "#16294A",
}


def srgb_to_lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (srgb_to_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def frame_rgb(clip: str, at: float, w: int, h: int) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(at), "-i", clip, "-frames:v", "1",
         "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = Path(sys.argv[1])
    at = float(sys.argv[sys.argv.index("--at") + 1]) if "--at" in sys.argv else None

    work = project / "work"
    meta = json.loads((work / "clip.json").read_text())
    clip = meta["clip"]
    if at is None:
        at = meta["durationSeconds"] * 0.45      # mid-clip, subject settled

    W, H = 216, 384                              # sample small; colour is broad
    raw = frame_rgb(clip, at, W, H)
    if not raw:
        print("could not read a frame")
        return 1

    def px(x, y):
        i = (y * W + x) * 3
        return raw[i], raw[i + 1], raw[i + 2]

    def region_mean(y0, y1, x0=0, x1=W):
        n = 0
        acc = [0, 0, 0]
        for y in range(y0, y1):
            for x in range(x0, x1):
                p = px(x, y)
                acc[0] += p[0]; acc[1] += p[1]; acc[2] += p[2]; n += 1
        return tuple(v // n for v in acc)

    # The upper band is where captions normally sit.
    upper = region_mean(int(H * 0.10), int(H * 0.34))
    lower = region_mean(int(H * 0.72), int(H * 0.92))

    # Head top: first row from the upper band downward where a good share of
    # the centre columns departs from the background colour.
    x0, x1 = int(W * 0.25), int(W * 0.75)
    head_row = None
    for y in range(int(H * 0.10), H):
        off = sum(1 for x in range(x0, x1)
                  if max(abs(px(x, y)[c] - upper[c]) for c in range(3)) > 42)
        if off > (x1 - x0) * 0.34:
            head_row = y
            break

    print(f"sampled at {at:.2f}s\n")
    print(f"upper band (caption zone)  #{upper[0]:02X}{upper[1]:02X}{upper[2]:02X}"
          f"   luminance {luminance(upper):.3f}")
    print(f"lower band                 #{lower[0]:02X}{lower[1]:02X}{lower[2]:02X}"
          f"   luminance {luminance(lower):.3f}\n")

    print("contrast against the caption zone (large text needs 3:1, body 4.5:1)")
    scored = sorted(
        ((contrast(upper, tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))), name, hx)
         for name, hx in CANDIDATES.items()), reverse=True)
    for ratio, name, hx in scored:
        mark = "PASS" if ratio >= 4.5 else ("large-text only" if ratio >= 3 else "FAILS")
        print(f"   {name:10s} {hx}  {ratio:5.2f}:1  {mark}")

    best = [s for s in scored if s[0] >= 4.5]
    print(f"\nuse {best[0][1] if best else scored[0][1]} for the payload; "
          f"pick the lead from the others that pass.")

    if head_row is not None:
        head_px = round(head_row / H * 1920)
        print(f"\nsubject appears at {head_row/H*100:.0f}% of frame height "
              f"(y={head_px} at 1920)")
        print(f"caption zone: y=288 (below the top UI band) to y={head_px - 20}")
        if head_px < 620:
            print("  NOTE: subject sits high — little clear space above. "
                  "Ask whether to place captions low instead.")
    else:
        print("\ncould not locate the subject — inspect a frame and ask.")

    print("\nplatform UI covers the top and bottom 15% (y<288, y>1632). "
          "Keep type outside both.")

    payload = best[0] if best else scored[0]
    lead = next((s for s in scored if s[2] != payload[2] and s[0] >= 4.5), payload)
    scene = {
        "sampledAt": round(at, 3),
        "captionZone": "#%02X%02X%02X" % upper,
        "lowerBand": "#%02X%02X%02X" % lower,
        "contrast": {name: round(r, 2) for r, name, _ in scored},
        "suggestedPalette": {
            "scene": {"wall": "#%02X%02X%02X" % upper,
                      "wallShadow": "#%02X%02X%02X" % lower},
            "onLight": {"lead": lead[2], "key": payload[2],
                        "keyAlt": next((s[2] for s in scored if 3 <= s[0] < 4.5),
                                       payload[2]),
                        "muted": "#5A4636"},
            "onDark": {"scrim": "#1C1410", "lead": "#FFF6E8", "key": "#E8A33C",
                       "keyAlt": "#F2C879", "muted": "#C9B39A"},
        },
        "headTopPx": round(head_row / H * 1920) if head_row else None,
        "captionZoneTop": 288,
        "captionZoneBottom": (round(head_row / H * 1920) - 20) if head_row else None,
    }
    (work / "scene.json").write_text(json.dumps(scene, indent=2))
    print(f"\nwrote {work/'scene.json'} — copy suggestedPalette into brief.json "
          f"after confirming it with Niranjan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
