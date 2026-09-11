#!/usr/bin/env python3
"""Automatic caption palette — measured, not chosen.

    python scripts/palette.py projects/<slug> [--debug]

Given a clip, this samples the real colour behind each caption zone (the wall
up top, the subject/saree down low) and derives an elegant, legible, multi-
colour scheme: a rotation of payload colours that changes beat to beat, a
contrasting colour for the small lead line, and an accent for stats — each one
checked for perceptual contrast (APCA) against its own local background, so
nothing that blends survives (saffron on parrot green, white on a pale wall).

It adapts on its own: a different saree, wall, room or person yields a
different measured background and therefore a different palette, with no
questions asked. Writes work/palette.json.

APCA (the modern perceptual contrast model) is implemented here directly —
coloraide ships WCAG only — and coloraide supplies OKLCH for harmony.
"""
import json, subprocess, sys
from pathlib import Path
from coloraide import Color

FPS = 30

# ---- perceptual contrast (APCA 0.98G) -------------------------------------


def _luma(hexs):
    r, g, b = Color(hexs).convert("srgb")[:3]
    f = lambda c: (max(c, 0.0)) ** 2.4
    return 0.2126729 * f(r) + 0.7151522 * f(g) + 0.0721750 * f(b)


def apca(txt, bg):
    """Signed Lc: negative = light text on dark bg, positive = dark on light.
    Magnitude is what matters; ~45+ reads for large display type, 60+ is
    strong."""
    yt, yb = _luma(txt), _luma(bg)
    bt, bc = 0.022, 1.414
    yt = yt + (bt - yt) ** bc if yt < bt else yt
    yb = yb + (bt - yb) ** bc if yb < bt else yb
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14
        out = 0.0 if s < 0.001 else s - 0.027
    else:
        s = (yb ** 0.65 - yt ** 0.62) * 1.14
        out = 0.0 if s > -0.001 else s + 0.027
    return out * 100.0


def is_dark(hexs):
    return _luma(hexs) < 0.18


# ---- an elegant, brand-anchored candidate pool ----------------------------
# family groups keep a rotation from repeating a hue; brand/warm tags bias the
# pick toward Kyros' register (forest, rust, cream) and toward what reads as
# premium on skin/fabric rather than loud.
POOL = [
    # Light/vibrant half — for type on a DARK ground (a scrim, or a dark
    # backdrop). These are the dark tones below flipped up in lightness: a
    # forest green becomes a spring green, a brick red becomes a coral. Same
    # hue family, opposite polarity, because what a colour sits ON decides
    # whether it reads, not the colour itself.
    ("warm white",     "#FFF6E8", "light",  {"warm", "brand"}),
    ("cream",          "#F5EAD2", "cream",  {"warm", "brand"}),
    ("saffron",        "#FFB01F", "amber",  {"warm", "brand"}),
    ("spring green",   "#9BE564", "spring", {"brand"}),
    ("mint",           "#5FE3C0", "mint",   {"cool"}),
    ("periwinkle",     "#B9C4FF", "periwinkle", {"cool"}),
    ("blush",          "#FFA8B6", "blush",  {"warm"}),
    ("coral",          "#FF8F70", "coral",  {"warm"}),
    ("honey gold",     "#F4CE87", "gold2",  {"warm", "brand"}),
    ("cream yellow",   "#F1E2A2", "gold",   {"warm", "brand"}),
    ("deep chocolate", "#3A2416", "brown",  {"warm"}),
    ("espresso",       "#2A1B10", "coffee", {"warm", "brand"}),
    ("bronze",         "#7A4E1C", "bronze", {"warm"}),
    ("caramel",        "#8A5A2A", "caramel", {"warm"}),
    ("dark red",       "#8E2A18", "red",    {"warm"}),
    ("brick",          "#A6371C", "red",    {"warm"}),
    ("rust",           "#9E3B16", "rust",   {"brand"}),
    ("forest",         "#103D2C", "green",  {"brand"}),
    ("deep teal",      "#0E3A38", "teal",   {"cool"}),
    ("plum",           "#361327", "purple", {"cool"}),
    # indigo/periwinkle: the dark half's cool-blue member, previously
    # missing entirely — the pool had reds, greens and one purple (plum) on
    # the cool side but no blue. Same hue (280deg vs 276deg, see README),
    # flipped up in lightness for the dark-ground half, same as every other
    # pair here. Cleared both bars against a real muscle-style dark scrim
    # (#100500) and a real sleep-cycle-style light scrim (#FAE9DC) — see the
    # README worked table; navy/aubergine/olive/sage/gold-ochre were all
    # tested and rejected there for redundancy or too narrow a hue gap.
    ("indigo",         "#28285C", "indigo", {"cool"}),
]
POOL_HEX = {n: h for n, h, _, _ in POOL}
FAMILY = {n: f for n, h, f, _ in POOL}


# The lead line is set smaller than the payload, so it needs more separation
# from the background than the payload does, not less.
LEAD_FLOOR = 45


def nearby_lead(payload, bg, floor=LEAD_FLOOR):
    """The small lead line as a colour NEARBY the payload — the same warm hue,
    nudged just enough in lightness to separate the two lines while staying on
    the legible side of the background. Never a contrasting opposite; the two
    fonts read as a tonal pair.

    The nudge keeps going until the tint clears the APCA floor: a colour picked
    only for its distance from the payload can land right on top of the
    background, which is how the lead came to vanish on a parrot-green saree."""
    p = Color(payload).convert("oklch")
    bl = Color(bg).convert("oklch")["lightness"]
    pl = p["lightness"] or 0.0
    if p["chroma"] is not None:
        p["chroma"] *= 0.82
    if pl >= bl:                                   # light payload -> paler lead
        light, away = min(0.95, pl + 0.05), 0.03
    else:                                          # dark payload -> lighter, still dark
        light, away = min(bl - 0.06, pl + 0.15), -0.03
    for _ in range(24):
        p["lightness"] = max(0.03, min(0.97, light))
        out = p.convert("srgb").to_string(hex=True, upper=True)
        if abs(apca(out, bg)) >= floor:
            return out
        light += away
    return out

# The lead line's neutral, for the two-colour pairing. A neutral against a
# colour reads as a deliberate pair; two mid-tone colours read as a clash.
# Derived from the measured wall for the same reason the ground is: a neutral
# carrying a trace of the room's own hue belongs to the frame, where a pinned
# brown is just a brown that happened to suit one clip.
def neutral_lead(wall, polarity, ground, floor=45):
    c = Color(wall).convert("oklch")
    if polarity == "light":        # dark neutral, for type on a light ground
        light, step = 0.30, -0.03
        c["chroma"] = min(c["chroma"] or 0.0, 0.030)
    else:                          # pale neutral, for type on a dark ground
        light, step = 0.93, 0.02
        c["chroma"] = min(c["chroma"] or 0.0, 0.024)
    for _ in range(20):
        c["lightness"] = max(0.05, min(0.97, light))
        out = c.convert("srgb").to_string(hex=True, upper=True)
        if abs(apca(out, ground)) >= floor:
            return out
        light += step
    return out

# A light colour rides a firmer letter-shade, so it clears a lower bar than a
# solid dark payload does.
LIGHT_FAMILIES = {"light", "cream", "gold", "gold2", "amber",
                  "spring", "mint", "coral", "blush", "periwinkle"}


def floor_for(hexs, floor_dark, floor_light):
    return floor_light if FAMILY_OF(hexs) in LIGHT_FAMILIES else floor_dark


def FAMILY_OF(hexs):
    for n, h, f, _ in POOL:
        if h == hexs:
            return f
    return "other"


def mixed_rotation(bg, prefer, floor_dark, floor_light, n=4):
    """Walk a curated preference list and keep each colour that (a) clears the
    APCA floor for its polarity and (b) brings a new hue family. This is how the
    beat-to-beat variety stays a *designed mix* (chocolate / white / dark red /
    a cool tone) rather than whatever scores highest — while still dropping any
    colour that would blend on this particular background."""
    out, seen = [], set()
    for name in prefer:
        hexs = POOL_HEX[name]
        fam = FAMILY[name]
        if fam in seen:
            continue
        if abs(apca(hexs, bg)) < floor_for(hexs, floor_dark, floor_light):
            continue
        seen.add(fam)
        out.append({"name": name, "hex": hexs, "dark": is_dark(hexs)})
        if len(out) >= n:
            break
    return out


def best(bg, floor, prefer):
    """Single best colour from a preferred name list that clears the floor;
    else the highest-contrast colour in the pool."""
    for name in prefer:
        h = POOL_HEX[name]
        if abs(apca(h, bg)) >= floor:
            return {"name": name, "hex": h, "dark": is_dark(h)}
    name, h, _, _ = max(POOL, key=lambda c: abs(apca(c[1], bg)))
    return {"name": name, "hex": h, "dark": is_dark(h)}


# ---- sampling the footage -------------------------------------------------


def sample(clip, y0, y1, at):
    """Median RGB of a horizontal band [y0,y1] (height fractions) at time `at`."""
    import numpy as np
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(clip), "-frames:v", "1",
         "-vf", f"crop=in_w:in_h*{y1 - y0:.4f}:0:in_h*{y0:.4f},scale=120:-2,format=rgb24",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 3)
    r, g, b = (int(np.median(a[:, i])) for i in range(3))
    return "#%02X%02X%02X" % (r, g, b)


def zone_bg(project, work):
    """Representative background behind the top and bottom caption bands."""
    clip = json.loads((work / "clip.json").read_text())["clip"]
    dur = json.loads((work / "clip.json").read_text())["durationSeconds"]
    # Top: sample where the top half is blank (no burned-in graphic), so we get
    # the wall, not a graphic. Fall back to an early moment.
    top_at = 2.0
    ov = work / "overlays.json"
    if ov.exists():
        occ = json.loads(ov.read_text())["regions"]["top"]["occupied"]
        blanks, cur = [], 0
        for a, b in sorted(occ):
            if a > cur:
                blanks.append((cur, a))
            cur = max(cur, b)
        if cur < int(dur * FPS):
            blanks.append((cur, int(dur * FPS)))
        if blanks:
            a, b = max(blanks, key=lambda w: w[1] - w[0])
            top_at = round((a + b) / 2 / FPS, 2)
    wall = sample(clip, 0.10, 0.34, top_at)
    saree = sample(clip, 0.66, 0.82, round(dur * 0.55, 2))
    return wall, saree


# ---- build the palette ----------------------------------------------------


def ground_from(wall, polarity="dark"):
    """A caption ground derived from the scene, not a generic black box.

    Takes the measured wall and pushes it to one end of the lightness range,
    holding a trace of its own hue so the panel reads as part of the room —
    a warm espresso on a beige wall, a soft paper on the same wall — rather
    than a rectangle dropped on top of the footage. Which end is a per-clip
    decision: `dark` carries vivid light type, `light` carries the deep
    forest/brick/teal register."""
    c = Color(wall).convert("oklch")
    if polarity == "light":
        c["lightness"] = 0.945
        c["chroma"] = min(c["chroma"] or 0.0, 0.026)
    else:
        c["lightness"] = 0.132
        c["chroma"] = min(c["chroma"] or 0.0, 0.034)
    return c.convert("srgb").to_string(hex=True, upper=True)


def darken(hexs, amt=0.12):
    c = Color(hexs).convert("oklch")
    c["lightness"] = max(0, c["lightness"] - amt)
    return c.convert("srgb").to_string(hex=True, upper=True)


def compute(project):
    work = Path(project) / "work"
    wall, saree = zone_bg(project, work)

    # A warm register throughout — cream / yellow / brown / bronze and their
    # shades — because that read best on this footage. The small lead is a
    # nearby tint of each payload (computed at build time), so the two lines are
    # a tonal pair, never a light/dark contrast. No pure white anywhere.

    # TOP zone: dark warm type on a light wall.
    top = {
        "bg": wall,
        "rotation": mixed_rotation(
            wall, ["deep chocolate", "bronze", "caramel", "forest", "espresso"],
            floor_dark=46, floor_light=34, n=4),
        # Forest is a brand colour and scores strongly on a pale wall, so it
        # gets a look in before falling back to bronze, which reads muddy.
        "accent": best(wall, 46, ["rust", "brick", "forest", "bronze"]),
    }

    # BOTTOM zone: warm type straight on the saree (no scrim). A cream/yellow +
    # brown/bronze mix — the lights ride a slightly stronger letter-shade so
    # they read on the bright green; the darks read on their own. Each kept
    # only if it clears APCA on THIS saree.
    bottom = {
        "bg": saree,
        "rotation": mixed_rotation(
            saree, ["cream", "deep chocolate", "cream yellow", "bronze",
                    "caramel", "espresso"],
            floor_dark=34, floor_light=26, n=4),
        "accent": best(saree, 33, ["caramel", "brick", "rust", "bronze"]),
    }

    pal = {
        "measured": {"wall": wall, "saree": saree},
        "scene": {"wall": wall, "wallShadow": darken(wall, 0.14)},
        "zones": {"top": top, "bottom": bottom},
        # kept for the question hook (its own dark scrim) and any legacy read
        "onDark": {"scrim": "#120C08", "lead": "#FFF6E8", "key": "#F4CE87",
                   "keyAlt": "#E8A33C", "muted": "#C9B39A"},
    }
    return pal


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    project = Path(sys.argv[1])
    work = project / "work"
    pal = compute(project)
    (work / "palette.json").write_text(json.dumps(pal, indent=2))

    m = pal["measured"]
    print(f"measured background   wall {m['wall']}   saree {m['saree']}\n")
    for zn in ("top", "bottom"):
        z = pal["zones"][zn]
        print(f"{zn.upper()} zone (bg {z['bg']})")
        for c in z["rotation"]:
            print(f"   payload  {c['name']:14s} {c['hex']}  APCA {apca(c['hex'], z['bg']):+6.1f}")
        print(f"   accent   {z['accent']['name']:14s} {z['accent']['hex']}  "
              f"APCA {apca(z['accent']['hex'], z['bg']):+6.1f}")
        lp = z["rotation"][0]["hex"]
        print(f"   lead     nearby tint of each payload (e.g. {lp} -> {nearby_lead(lp, z['bg'])})\n")
    print(f"wrote {work/'palette.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
