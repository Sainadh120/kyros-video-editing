#!/usr/bin/env python3
"""The register — every axis a clip's look can vary on, read from the prior
briefs so the next clip's combination is PROPOSED rather than guessed, and so
no single axis quietly repeats the last reel's choice.

    python scripts/register.py <slug>          propose the next clip's register

Each entry in AXES names an axis and its ordered list of valid option
tokens. To add a new axis — a reveal mechanic or type pairing another module
owns — that module registers its own option list into AXES (see
`_typography_options` / `_motion_options` below for the pattern: a small
function that imports the owning module and reads its own dict of names).
Nothing else here has to change for a new axis to show up in the proposal
and the README table.

Two kinds of axis:
  chosen    a creative decision with room to alternate — these get an actual
            proposal: an option this brief did not already pin, and that
            neither of the last two clips used.
  measured  an outcome of the hazard-aware solvers in build_captions.py
            (plateAnchorStyle, markAnchorStyle) — reported from history for
            visibility only, never overridden. Forcing "not what you did
            last time" onto a safety measurement is exactly backwards: the
            plate/mark solvers already answer to the footage on every clip,
            not to a rotation, and a brief's pin already wins over them too.

A brief that sets its own value for a CHOSEN axis (the fields `_pinned()`
below knows about for that axis) still wins outright — this only fills in
what a brief leaves unset, and says why it picked what it picked.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
LOOKBACK = 2   # "don't repeat the last two reels" — the rule stated in the README


def _typography_options():
    """typePairing's option list, owned by scripts/typography.py. Read, not
    hardcoded, so adding a pairing there is a data change, not a code change
    here."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import typography
        return list(typography.PAIRINGS.keys())
    except Exception:
        return []


def _motion_options():
    """revealStyle's option list, owned by scripts/motion.py.

    `legacyMaskWipe` is excluded on purpose — per docs/INTEGRATION-type-
    motion-audio.md #3, it is not a style anything should choose, only the
    implicit resolution of an absent per-chunk `reveal` field. This axis
    also only ever applies to the CLIP-WIDE pin (brief.style.revealStyle),
    never to motion.py's own per-beat `auto` selection, which is driven by
    that beat's audio/zone, not by a cross-clip rotation."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import motion
        return [k for k in motion.REVEAL_STYLES.keys() if k != "legacyMaskWipe"]
    except Exception:
        return []


def _visual_options(name):
    """visualStyle / bubbleShape option lists, owned by scripts/visuals.py —
    same pattern as the type and motion axes."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import visuals
        return list(getattr(visuals, name))
    except Exception:
        return []


AXES = {
    "groundPolarity":   {"kind": "chosen",
                          "options": ["none", "light", "dark"]},
    "questionPreset":   {"kind": "chosen",
                          "options": ["ink", "forest", "paper", "white",
                                      "plum", "teal", "clay", "bone"]},
    "leadStyle":        {"kind": "chosen",
                          "options": ["match", "neutral", "tint"]},
    "paletteLead":      {"kind": "chosen",
                          "options": ["forest", "brick", "deep teal", "plum",
                                      "indigo", "deep chocolate", "rust",
                                      "spring green", "warm white", "blush",
                                      "mint", "coral", "periwinkle"]},
    "shadingTreatment": {"kind": "chosen",
                          "options": ["flat"]},   # see README "Backgrounds and shading"
    "plateAnchorStyle": {"kind": "measured", "options": ["low", "high"]},
    "markAnchorStyle":  {"kind": "measured", "options": ["upper-right", "upper-left"]},
    # Registered by the type/motion module (owned separately) as data, once
    # each dict there is populated.
    "typePairing":      {"kind": "chosen", "options": _typography_options()},
    "revealStyle":       {"kind": "chosen", "options": _motion_options()},
    # Supporting visuals (brief.visuals). A clip with no visuals records
    # nothing, so these only start rotating once reels actually use them.
    "visualStyle":      {"kind": "chosen", "options": _visual_options("VISUAL_STYLES")},
    "bubbleShape":      {"kind": "chosen", "options": _visual_options("BUBBLE_SHAPES")},
}


def _ground_polarity(b):
    scrim = (b.get("layout") or {}).get("captionScrim") or {}
    if not scrim.get("enabled"):
        return "none"
    return scrim.get("ground", "dark")


def _lead_style(b):
    style = (b.get("style") or {}).get("leadStyle")
    if style:
        return style
    scrim = (b.get("layout") or {}).get("captionScrim") or {}
    return "match" if scrim.get("enabled") else "tint"


def _palette_lead(b):
    """The first rotation colour named in the brief's own accent prose, if
    any. A rough signal only — the actual rotation is derived at build time
    from the measured wall, not stored in the brief — but it is the only
    record a past brief carries of which hue led its rotation."""
    accent = ((b.get("style") or {}).get("accent") or "").lower()
    for name in AXES["paletteLead"]["options"]:
        if name in accent:
            return name
    return None


# Every brief predating the pairing system records the pairing as free-text
# prose — all four shipped clips say "PlayfairDisplay Italic / Anton", which is
# exactly what `heritage` names now that DoctorVideo.tsx resolves pairings by
# key. Dropping that as unparseable made the selector read "never run" and
# propose `heritage` for the next clip: the one pairing all four reels already
# used, i.e. the precise repetition this axis exists to prevent. The prose is a
# record of what rendered, so it is normalised rather than discarded.
LEGACY_PAIRING_PROSE = {"playfairdisplay italic / anton": "heritage"}


def _type_pairing(b):
    v = (b.get("style") or {}).get("typePairing")
    if not v:
        return "heritage"          # no style block at all: the hardcoded default rendered
    return LEGACY_PAIRING_PROSE.get(v.strip().lower(), v)


AXIS_READERS = {
    "groundPolarity":   _ground_polarity,
    "questionPreset":   lambda b: (b.get("question") or {}).get("preset", "legacy"),
    "leadStyle":        _lead_style,
    "paletteLead":      _palette_lead,
    "shadingTreatment": lambda b: "flat",   # the only kind that ships today
    "typePairing":      _type_pairing,
    # The STRUCTURED key from docs/INTEGRATION-type-motion-audio.md #2.2 —
    # not the free-text "revealMechanic" prose the four shipped briefs carry
    # for human documentation, which is not a valid axis option and was
    # never meant to be machine-read.
    "revealStyle":       lambda b: (b.get("style") or {}).get("revealStyle"),
    "visualStyle":      lambda b: (b.get("visuals") or {}).get("style"),
    "bubbleShape":      lambda b: (b.get("visuals") or {}).get("bubbleShape"),
}


def read_history():
    """Every prior brief's recorded value per axis, oldest first, plus the
    slugs in that order.

    Nothing in brief.json records when a clip shipped, so this orders by the
    brief's file mtime — a real proxy for "which reel came first" as long as
    the project folders were never bulk-copied, ties broken by slug name for
    determinism. Reproduces the README's own running-record order on this
    repo (insulin-resistance, walking, muscle, sleep-cycle) even though
    muscle and sleep-cycle share an mtime."""
    paths = sorted(PROJECTS.glob("*/brief.json"),
                    key=lambda p: (p.stat().st_mtime, p.parent.name))
    briefs, slugs = [], []
    for p in paths:
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        briefs.append(b)
        slugs.append(b.get("slug", p.parent.name))
    hist = {ax: [] for ax in AXES}
    for b in briefs:
        for ax, spec in AXES.items():
            hist[ax].append(AXIS_READERS[ax](b) if ax in AXIS_READERS else None)
    return hist, slugs


def _pinned(brief, axis):
    if not brief:
        return None
    if axis == "groundPolarity":
        scrim = (brief.get("layout") or {}).get("captionScrim") or {}
        if "ground" in scrim or "enabled" in scrim:
            return _ground_polarity(brief)
        return None
    if axis == "questionPreset":
        return (brief.get("question") or {}).get("preset")
    if axis == "leadStyle":
        return (brief.get("style") or {}).get("leadStyle")
    if axis == "paletteLead":
        return (brief.get("style") or {}).get("paletteLead")
    if axis == "typePairing":
        return (brief.get("style") or {}).get("typePairing")
    if axis == "revealStyle":
        return (brief.get("style") or {}).get("revealStyle")
    if axis == "visualStyle":
        return (brief.get("visuals") or {}).get("style")
    if axis == "bubbleShape":
        return (brief.get("visuals") or {}).get("bubbleShape")
    return None


def propose(brief=None, lookback=LOOKBACK):
    """Propose the next register. For each CHOSEN axis: the brief's own
    pinned value if it has one, else an option neither of the last
    `lookback` clips used, with the reason. MEASURED axes are reported from
    history only — see the module docstring for why."""
    hist, slugs = read_history()
    out = {}
    for ax, spec in AXES.items():
        # Only a value that is actually one of this axis's registered
        # options counts as "recent" — a legacy brief's free-text prose
        # (e.g. typePairing's old "PlayfairDisplay Italic / Anton" field,
        # predating the structured pairing names) should not masquerade as
        # a real pick.
        recent = [v for v in hist[ax][-lookback:] if v and v in spec["options"]]
        if spec["kind"] == "measured":
            out[ax] = {"recent": hist[ax][-lookback:],
                       "note": "measured by the solver in build_captions.py, not chosen"}
            continue
        pin = _pinned(brief, ax)
        if pin:
            out[ax] = {"value": pin, "reason": "pinned by this brief"}
            continue
        options = spec["options"]
        if not options:
            out[ax] = {"value": None, "reason": "no options registered yet"}
            continue
        fresh = [o for o in options if o not in recent]
        pick = fresh[0] if fresh else options[0]
        spent = ", ".join(f"`{v}`" for v in dict.fromkeys(recent)) or "(none yet)"
        reason = (f"last {len(recent)} clip(s) ran {spent} -> this one takes `{pick}`"
                  if fresh else
                  f"every registered option has run in the last {lookback} clips; "
                  f"`{pick}` is the one used longest ago")
        out[ax] = {"value": pick, "reason": reason}
    return out, slugs


def report(slug):
    p = PROJECTS / slug / "brief.json"
    brief = json.loads(p.read_text()) if p.exists() else {}
    reg, slugs = propose(brief)
    lines = [f"register proposal for {slug}  (history: {', '.join(slugs) or '(none yet)'})"]
    for ax, v in reg.items():
        if "value" in v and "note" not in v:
            lines.append(f"   {ax:17s} -> {v['value']!s:14s} {v['reason']}")
        else:
            lines.append(f"   {ax:17s} -> {v.get('note','')}  recent: {v.get('recent')}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    print(report(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
