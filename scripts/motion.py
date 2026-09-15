#!/usr/bin/env python3
"""A researched text-reveal library, and the rule for when a beat earns one.

Today every beat reveals the same way regardless of how it was spoken: a
soft spring, word-stagger for the lead, a mask wipe for the payload. This
module is the decision layer — which of several reveal styles a beat gets,
and whether it should animate at all — driven by scripts/measure_audio.py's
per-word/phrase numbers, the beat's zone, and its duration. The actual reveal
RENDERING lives in studio/src/DoctorVideo.tsx, in `KEY_REVEALS`; this module
only picks a style name + params per beat, exactly like `palette.py` decides
colours without touching a pixel.

See docs/TYPE-AND-MOTION.md for the research behind each style, the frame
budget it is held to, and the reasoning behind the animate/don't-animate
rule.
"""
from __future__ import annotations
import json, subprocess
from pathlib import Path

import numpy as np

FPS = 30


# ---------------------------------------------------------------------------
# The reveal library. Every style's `illegibleFrames` is the number of 30fps
# frames, worst case, in which a still pulled mid-reveal could read as a
# rendering fault rather than an in-progress reveal — not a target, a bound
# the technique is built to respect. See DoctorVideo.tsx for how each is
# enforced; see docs/TYPE-AND-MOTION.md for the reasoning per style,
# including why opacity/blur/scale techniques are held to a different
# mechanism of proof than clip/mask techniques (they cannot produce a
# fragmentary glyph at all, by construction — a mask can).
# ---------------------------------------------------------------------------

REVEAL_STYLES = {
    # The ORIGINAL, unmodified reveal — vertical mask wipe with a slow
    # (~13-frame) spring. Kept byte-for-byte as the implicit default so the
    # four shipped clips render exactly as they do today. Its measured
    # illegibility window (~9-13 frames, 0.3-0.43s) is the defect that
    # produced the pcos-sleep-cycle 10.5s frame — recorded here, not fixed,
    # because fixing it would change already-shipped output. New clips
    # should not choose this style; it exists only for backward compatibility.
    "legacyMaskWipe": {
        "label": "vertical mask wipe (legacy, unfixed)",
        "illegibleFrames": 13,
        "displacementPx": 0,   # clipped, not translated, in screen space
        "usedWhen": "never — implicit only, for clips authored before this "
                    "system existed",
    },
    # The successor default. Same visual family (a payload that rises into
    # place) but the axis of the wipe is rotated: instead of clipping
    # vertically through the MIDDLE of every glyph (which is what produced a
    # flat half-height band of caps), it reveals left-to-right with a
    # `clip-path: inset()`, so at every instant every VISIBLE character is
    # its complete glyph — only the count of visible characters changes.
    # The sweep is fast (6 frames, 0.2s) relative to any shipped payload
    # (6-19 characters), so the clip edge can sit inside any one glyph's
    # width for at most ~1 frame before moving past it.
    "maskWipeFast": {
        "label": "horizontal wipe, left to right",
        "illegibleFrames": 1,
        "displacementPx": 0,
        "usedWhen": "the new default for a normal beat — not the fastest, "
                    "not the slowest, not a hero",
    },
    # No mask at all: each word (lead) or the whole payload (key) fades and
    # rises as one complete unit. A faint, fully-formed word is never a
    # broken one — there is no spatial cut to freeze mid-motion, so the
    # illegibility window is 0 BY CONSTRUCTION, not by tuning.
    "wordStagger": {
        "label": "fade + small rise, whole-word units",
        "illegibleFrames": 0,
        "displacementPx": 10,
        "usedWhen": "a fast beat (< 0.9s) or a quiet aside under a graphic",
    },
    # Same reasoning as wordStagger, at the character grain — for a beat that
    # wants more energy than a whole-line fade but is too fast for a wipe to
    # read clearly per word.
    "charCascade": {
        "label": "per-character fade + rise, tight stagger",
        "illegibleFrames": 0,
        "displacementPx": 8,
        "usedWhen": "an energetic beat, list items, short punchy payloads",
    },
    # A fast, slightly overshooting scale+opacity snap on ONE word — the
    # acoustically emphasised one. No mask, so illegibility is 0 by the same
    # reasoning as wordStagger. Reserved for a beat carrying a genuinely
    # emphasised word (top-quartile emphasis score), not applied to a whole
    # line — a punch on every word is not a punch.
    "punchPop": {
        "label": "scale 0.85->1.04->1.0 + opacity, single word",
        "illegibleFrames": 0,
        "displacementPx": 0,
        "usedWhen": "the beat's payload contains a top-quartile-emphasis word",
    },
    # Blur + opacity, no translation, no mask, slow (18-20 frames, ~0.6s).
    # A blurred-but-whole word is not a broken glyph — it is legible-through-
    # softness at every frame, which is a different failure mode than a
    # mask cutting a glyph in half. Reserved for the one place the brief
    # calls for a slower, bigger reveal: a hero beat with real duration on a
    # bare wall, never under a graphic and never on a short beat.
    "blurIn": {
        "label": "blur 10px->0 + opacity, no displacement",
        "illegibleFrames": 0,      # never a FRAGMENTARY glyph; see docstring
        "displacementPx": 0,
        "usedWhen": "a hero beat only: >= 1.8s, zone=top, no scrim, "
                    "top-decile emphasis for the take",
    },
}

DEFAULT_STYLE = "maskWipeFast"


# ------------------------------------------------------------ gesture ------


def gesture_intensity(clip_path: str, t0: float, t1: float) -> float:
    """Coarse 0..1 "how much is moving" reading for [t0, t1), so a beat that
    lands mid-gesture can be told to animate less.

    Same family of technique as scan_overlays.py's frame differencing, but
    answering a different question: that scan asks "is a GRAPHIC covering
    this region," fixed against a median plate; this asks "how much is
    changing frame to frame," full-frame, at a coarse sample rate. A talking
    head who is mostly still (hands down, head steady) scores low; a clip
    where she is gesturing with both hands scores high. Sampled at 6fps,
    64x114px — colour-blind to WHAT moved, only how much, so it is cheap
    (one ffmpeg decode, no model) and does not need to know where her hands
    are.

    Returns 0.0 if the span is degenerate or ffmpeg produced nothing.
    """
    if t1 <= t0:
        return 0.0
    dur = t1 - t0
    fps = 6
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}",
         "-i", str(clip_path), "-vf", f"scale=64:114,fps={fps},format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True).stdout
    n = len(raw) // (64 * 114)
    if n < 2:
        return 0.0
    frames = np.frombuffer(raw[:n * 64 * 114], np.uint8).reshape(n, 114, 64).astype(np.int16)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    # Normalise against a fixed, generous ceiling (mean abs diff of 30 on an
    # 8-bit frame is already a lot of motion) rather than per-clip max, so
    # the number is comparable across clips rather than always spanning 0..1
    # regardless of how much actually moved.
    return float(min(1.0, diffs.mean() / 30.0))


# --------------------------------------------------- when to animate at all


def should_animate(
    duration_frames: int,
    graphic_covered_frac: float,
    gesture: float,
    consecutive_animated: int,
    is_hero: bool,
) -> tuple[bool, str]:
    """Whether a beat earns a reveal, or should simply be on/off (a flat cut
    or a plain opacity fade with no stagger, no mask, no punch).

    The README already has the caption-level version of this rule: "a
    caption is owed to nothing" — when the footage already carries the
    point, the caption itself should not exist. This is the same logic one
    level down: a caption that DOES appear is not automatically a caption
    that should ANIMATE. Four measured reasons to say no:

      duration   a beat under 30 frames (1s at 30fps) is on screen for less
                 time than a `wordStagger` reveal takes to finish (its
                 longest stagger + settle runs ~18-24 frames already) — the
                 reveal would still be resolving when the beat starts
                 leaving. That is not a reveal, it is flicker.

      graphic    if a burned-in graphic already covers >= 60% of the beat's
                 span, it is very likely ALSO moving/animating on its own
                 account (README: graphics arrive as illustrations, wipes,
                 counters) — stacking a text reveal on top of a moving
                 graphic is two things demanding attention in the same
                 breath. (Beats covered >= 75% are usually skipped entirely
                 per the existing restraint rule; this covers the 60-75%
                 band that still gets a caption but should hold still.)

      gesture    a `gesture_intensity` reading >= 0.20 means this span is in
                 the top decile of movement measured across the four shipped
                 takes' own footage (1-second windows, pooled: median 0.10,
                 p90 0.21, p99 0.44) — not a guessed number. Above it she is
                 already the dominant motion in frame, and a translating or
                 masking reveal competes with her rather than supporting her.

      repetition three animated beats in a row reads as a template running,
                 not a reel reacting to what she said (this is the note
                 that produced this rule — "don't be bored, try different
                 things"). The fourth beat in a row defaults to a flat
                 fade-in regardless of its own numbers, UNLESS it is the
                 hero.

    A hero beat (`is_hero=True` — long, on a bare wall, high emphasis)
    overrides all four: it is explicitly the one place the brief calls for
    "a slower, bigger" reveal, so it always animates.
    """
    if is_hero:
        return True, "hero beat: overrides all four checks"
    if duration_frames < 30:
        return False, f"beat is {duration_frames}f (<30f/1.0s) — a reveal would still be resolving when it leaves"
    if graphic_covered_frac >= 0.60:
        return False, f"{graphic_covered_frac:.0%} covered by a burned-in graphic that is likely animating itself"
    if gesture >= 0.20:
        return False, f"gesture intensity {gesture:.2f} >= 0.20 (top decile, measured) — she is already the dominant motion here"
    if consecutive_animated >= 3:
        return False, f"{consecutive_animated} animated beats already in a row — this one cuts/fades flat instead"
    return True, "clears all four checks"


# ------------------------------------------------------------ style choice


def choose_reveal(
    duration_frames: int,
    zone: str,
    scrim_enabled: bool,
    beat_emphasis: float,   # 0..1, e.g. max(word emphasis) over the beat's key words
    is_hero: bool,
    prior_styles: list[str],
) -> dict:
    """Pick a reveal style + a couple of derived params for one beat.
    `prior_styles` is this clip's styles so far, most recent last — used only
    to break a run of 3 identical non-default styles, the same "don't repeat"
    reasoning as the palette/question-card rotations.
    """
    if is_hero:
        style = "blurIn"
    elif duration_frames < 27:                    # < 0.9s
        style = "charCascade" if beat_emphasis >= 0.6 else "wordStagger"
    elif scrim_enabled and zone == "bottom" and beat_emphasis < 0.4:
        style = "wordStagger"                      # a quiet aside, hold still
    elif beat_emphasis >= 0.75:
        style = "punchPop"
    else:
        style = DEFAULT_STYLE

    if len(prior_styles) >= 3 and len(set(prior_styles[-3:])) == 1 == prior_styles[-1:].count(style):
        # the same style four times running — force variety
        alt = "charCascade" if style != "charCascade" else "wordStagger"
        style = alt

    return {"style": style, **REVEAL_STYLES[style]}


if __name__ == "__main__":
    for name, spec in REVEAL_STYLES.items():
        print(f"{name:16s} illegible<= {spec['illegibleFrames']}f  "
              f"displacement<= {spec['displacementPx']}px  {spec['usedWhen']}")
