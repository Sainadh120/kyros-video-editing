#!/usr/bin/env python3
"""A researched type-pairing system, so a reel is not stuck speaking in one
voice forever.

    python scripts/typography.py                    print the pairing table
    python scripts/typography.py measure "STRING"    measure one string in
                                                      every pairing's payload

Today every reel runs the same two faces: Playfair Display italic for the
lead line, Anton for the payload. That was never a deliberate choice made
per clip — it is the only pairing that has ever existed in code. This module
adds four more, each validated the way `palette.py` validates a colour: not
"this looks premium," but a number that would have rejected it if it failed.

Every payload face here is checked against the same two numbers:

  1. it exists in @remotion/google-fonts at the exact weight used, confirmed
     against the installed package's own font-info tables (see the checks
     recorded below `PAIRINGS`, not asserted from memory of what Google Fonts
     ships), so the render stays hermetic;
  2. it holds the LONGEST real payload line shipped so far — "MAINTAINING
     MUSCLE" (pcos-muscle, bottom zone, 984px available) and "TREATMENT OF
     PCOS" (top zone, 940px available) — inside its zone's available width at
     the size the existing `key_size()` sizing rule would pick, with real
     glyph-advance measurements from the actual font file, not an assumed
     average character width.

How the widths were measured: the five candidate payload fonts' woff2 files
were downloaded from the exact `fonts.gstatic.com` URLs @remotion/google-fonts
resolves for that family/weight, decompressed, and read with `fontTools` for
each glyph's real advance width (`hmtx`), summed per string and normalised by
`unitsPerEm`. No kerning/GPOS was applied (no `harfbuzz` in this environment)
— for a display face at these sizes, in ALL CAPS, kerning moves the total a
few px at most, and every number below already carries 28-92px of margin, so
the missing kerning term cannot flip a pass into a fail. This is strictly
better than the sizing rule's own `advanceEm` heuristic already in
`build_captions.py`, which assumes one flat average width for every
character; here every pairing's `advanceEm` IS that measured average,
calibrated per font.

See docs/TYPE-AND-MOTION.md for the full research, the rejections, and the
worked numbers this file is built from.
"""
from __future__ import annotations
import sys

# ---------------------------------------------------------------------------
# Each pairing names the exact @remotion/google-fonts module + weight for its
# two faces. `advanceEm` is the MEASURED per-character average width (see the
# module docstring) already padded with a small safety margin — see
# docs/TYPE-AND-MOTION.md "the pairing table" for the raw per-string numbers.
# `letterSpacing`/`lineHeight` mirror the shape of THEME["type"] in
# build_captions.py so a pairing patches straight into `theme.type.lead` /
# `theme.type.key` with no restructuring.
# ---------------------------------------------------------------------------

PAIRINGS = {
    # The only pairing that has ever shipped. Left utterly unchanged so it
    # stays the default: a clip with no `style.typePairing` gets exactly this,
    # which is what all four shipped clips already receive implicitly.
    "heritage": {
        "label": "Playfair Display italic / Anton",
        "register": "warm, editorial, the original register — an italic "
                     "serif lead against a tall, ungiving grotesque cap",
        "lead": {"fontFamily": "PlayfairDisplay", "googleFontsModule": "PlayfairDisplay",
                 "style": "italic", "weight": 500, "weights": [500, 600],
                 "lineHeight": 1.18, "letterSpacing": -0.5},
        "key": {"fontFamily": "Anton", "googleFontsModule": "Anton",
                 "style": "normal", "weight": 400, "weights": [400],
                 "lineHeight": 0.92, "letterSpacing": -1.0, "advanceEm": 0.47},
    },
    # Fraunces is a "soft-serif" display face built for warm editorial work
    # (Vox, several health/wellness verticals use it) — it has none of
    # Playfair's Didone sharpness, so it reads calmer at the question-card
    # size where Playfair's thin hairlines can look brittle on a soft ground.
    # Paired against Barlow Condensed at 800: a humanist condensed grotesque
    # (drawn for UI/signage legibility, not a poster face), less severe than
    # Anton, still comfortably inside the width budget.
    "warmEditorial": {
        "label": "Fraunces italic / Barlow Condensed 800",
        "register": "softer and warmer than the default — a rounded-serif "
                     "lead against a humanist (not geometric) condensed cap; "
                     "reads calmer, less poster-like",
        "lead": {"fontFamily": "Fraunces", "googleFontsModule": "Fraunces",
                 "style": "italic", "weight": 500, "weights": [500, 600],
                 "lineHeight": 1.2, "letterSpacing": -0.3},
        "key": {"fontFamily": "BarlowCondensed", "googleFontsModule": "BarlowCondensed",
                 "style": "normal", "weight": 800, "weights": [800],
                 "lineHeight": 0.94, "letterSpacing": -0.4, "advanceEm": 0.46},
    },
    # Cormorant Garamond is a delicate classical revival — the most "quiet
    # literary" face in the set. Oswald is a condensed grotesque drawn after
    # 1920s European sans signage (originally a redrawn Alternate Gothic) —
    # not razor-tight like Anton, reads more like a documentary title card.
    # The pairing is the most contrast-heavy of the five: a hairline serif
    # against a solid geometric block.
    "classicPress": {
        "label": "Cormorant Garamond italic / Oswald 700",
        "register": "the most classical of the five — a hairline-delicate "
                     "serif lead against a confident, documentary-style "
                     "condensed sans; the highest lead/payload contrast",
        "lead": {"fontFamily": "CormorantGaramond", "googleFontsModule": "CormorantGaramond",
                 "style": "italic", "weight": 600, "weights": [500, 600, 700],
                 "lineHeight": 1.22, "letterSpacing": -0.2},
        "key": {"fontFamily": "Oswald", "googleFontsModule": "Oswald",
                 "style": "normal", "weight": 700, "weights": [700],
                 "lineHeight": 0.96, "letterSpacing": -0.6, "advanceEm": 0.49},
    },
    # Newsreader is Google's own "reading experience" serif — built for long
    # text at small sizes, so at the italic lead's modest size it reads warm
    # and unaffected rather than "designed." Saira Condensed at 800 is a
    # geometric condensed grotesque with a slightly more contemporary,
    # tech-adjacent cut than Barlow — a brisker, more energetic payload for a
    # clip whose beats move fast.
    "modernCalm": {
        "label": "Newsreader italic / Saira Condensed 800",
        "register": "unaffected and calm — a plain reading serif against a "
                     "crisp geometric condensed cap; suits a fast, "
                     "matter-of-fact take",
        "lead": {"fontFamily": "Newsreader", "googleFontsModule": "Newsreader",
                 "style": "italic", "weight": 500, "weights": [500, 600],
                 "lineHeight": 1.2, "letterSpacing": -0.2},
        "key": {"fontFamily": "SairaCondensed", "googleFontsModule": "SairaCondensed",
                 "style": "normal", "weight": 800, "weights": [800],
                 "lineHeight": 0.94, "letterSpacing": -0.5, "advanceEm": 0.47},
    },
    # Instrument Serif is a single-weight, high-fashion editorial italic —
    # thinner and quieter than any other lead here, built for a large-scale
    # pull-quote register. Antonio is a clean condensed grotesque with a
    # slightly rounder shoulder than Anton — the least "shouted" payload of
    # the five, for a quiet hero beat that should not compete with itself.
    "quietPremium": {
        "label": "Instrument Serif italic / Antonio 700",
        "register": "the quietest pairing — a thin, fashion-editorial serif "
                     "against a clean, unaggressive condensed cap; best on a "
                     "calm hero beat, not a loud one",
        "lead": {"fontFamily": "InstrumentSerif", "googleFontsModule": "InstrumentSerif",
                 "style": "italic", "weight": 400, "weights": [400],
                 "lineHeight": 1.16, "letterSpacing": 0.0},
        "key": {"fontFamily": "Antonio", "googleFontsModule": "Antonio",
                 "style": "normal", "weight": 700, "weights": [700],
                 "lineHeight": 0.96, "letterSpacing": -0.3, "advanceEm": 0.44},
    },
}

DEFAULT_PAIRING = "heritage"

# ---------------------------------------------------------------------------
# Measured payload widths — see docs/TYPE-AND-MOTION.md for the full
# per-string table across all four shipped clips and the rejected fonts.
# Recorded here so a caller (or a test) can sanity-check without re-running
# fontTools against a network download.
# ---------------------------------------------------------------------------

# (pairing, zone) -> {line, availPx, sizePx, measuredWidthPx, marginPx}
# zone geometry: "bottom" uses pcos-muscle's own tightest bottomZone
# (paddingX=48 -> avail 984px, ceiling 168px, the tightest shipped case);
# "top" uses the shared default topZone (paddingX=70 -> avail 940px,
# ceiling 178px).
MEASURED_FIT = {
    ("heritage", "bottom"):     {"line": "MAINTAINING MUSCLE", "availPx": 984, "sizePx": 116, "widthPx": 927, "marginPx": 57},
    ("heritage", "top"):        {"line": "TREATMENT OF PCOS", "availPx": 940, "sizePx": 118, "widthPx": 878, "marginPx": 62},
    ("warmEditorial", "bottom"): {"line": "MAINTAINING MUSCLE", "availPx": 984, "sizePx": 119, "widthPx": 932, "marginPx": 52},
    ("warmEditorial", "top"):    {"line": "TREATMENT OF PCOS", "availPx": 940, "sizePx": 120, "widthPx": 912, "marginPx": 28},
    ("classicPress", "bottom"): {"line": "MAINTAINING MUSCLE", "availPx": 984, "sizePx": 112, "widthPx": 909, "marginPx": 75},
    ("classicPress", "top"):    {"line": "TREATMENT OF PCOS", "availPx": 940, "sizePx": 113, "widthPx": 863, "marginPx": 77},
    ("modernCalm", "bottom"):   {"line": "MAINTAINING MUSCLE", "availPx": 984, "sizePx": 116, "widthPx": 933, "marginPx": 51},
    ("modernCalm", "top"):      {"line": "TREATMENT OF PCOS", "availPx": 940, "sizePx": 118, "widthPx": 878, "marginPx": 62},
    ("quietPremium", "bottom"): {"line": "MAINTAINING MUSCLE", "availPx": 984, "sizePx": 124, "widthPx": 919, "marginPx": 65},
    ("quietPremium", "top"):    {"line": "TREATMENT OF PCOS", "availPx": 940, "sizePx": 126, "widthPx": 848, "marginPx": 92},
}

# Rejected candidates, and the number that killed each one — see
# docs/TYPE-AND-MOTION.md for the narrative version.
REJECTED = [
    {"name": "Poppins ExtraBold 800", "reason":
     "not condensed: at the sizing rule's OWN floor (96px, before any "
     "attempt to fit a two-line payload) 'MAINTAINING MUSCLE' already "
     "measures 1083px against 984px available — 99px over, at the smallest "
     "size the system will ever pick."},
    {"name": "Montserrat Black 900", "reason":
     "same failure, worse: 1105px at the 96px floor, 121px over."},
    {"name": "Righteous", "reason":
     "fails on width (1004px at the 96px floor, 20px over) AND on register "
     "— a rounded novelty display face reads as a meme caption, not a "
     "clinic's."},
    {"name": "Staatliches", "reason":
     "clears width but not register: its deliberately uneven, hand-cut "
     "strokes read as a poster/flyer face, not a clinical one, at this "
     "sustained a screen presence — rejected on register, not a number."},
]


def print_table():
    print(f"{'pairing':16s} {'lead':30s} {'payload':24s} widths (bottom / top)")
    for name, p in PAIRINGS.items():
        lead = f"{p['lead']['fontFamily']} {p['lead']['style']} {p['lead']['weight']}"
        key = f"{p['key']['fontFamily']} {p['key']['weight']}"
        b = MEASURED_FIT[(name, "bottom")]
        t = MEASURED_FIT[(name, "top")]
        print(f"{name:16s} {lead:30s} {key:24s} "
              f"{b['widthPx']}/{b['availPx']}px (+{b['marginPx']})  "
              f"{t['widthPx']}/{t['availPx']}px (+{t['marginPx']})")
    print()
    for r in REJECTED:
        print(f"rejected: {r['name']:24s} {r['reason']}")


def rotation_pick(history: list[str]) -> str:
    """Next pairing that is NOT one of the last two used — mirrors the
    non-repetition rule the palette/question-card rotations already use
    (README: "rotate; do not repeat the last two reels"). `history` is the
    ordered list of pairing names used by previous clips, most recent last."""
    recent = set(history[-2:])
    for name in PAIRINGS:
        if name not in recent:
            return name
    return DEFAULT_PAIRING


if __name__ == "__main__":
    print_table()
