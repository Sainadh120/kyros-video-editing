# Integration — audio, typography and motion

Handoff for wiring `scripts/measure_audio.py`, `scripts/typography.py` and
`scripts/motion.py` into `scripts/prep`/`scripts/build_captions.py`, which I
do not own for this task. Everything here is additive: every new key is
optional, every new code path is opt-in, and the exact default for each key
is chosen so that re-running `build_captions.py` on any of the four shipped
`brief.json` files, unchanged, produces byte-identical `captions_data.json`
to what is already staged. I verified this holds for the TSX side by
diffing `studio/src/captions_data.json` (the currently staged
`pcos-sleep-cycle` output) against `projects/pcos-sleep-cycle/work/
captions_data.json` before and after all my changes — identical (md5
`20cf70afa3e2daeb0dad4d46fcd2d330`), and `npx tsc --noEmit` passes.

The reasoning behind every number here is in `docs/TYPE-AND-MOTION.md`.

---

## 1. What `prep` should additionally run

After `transcribe.py` writes `work/words.json`:

```bash
python3 scripts/measure_audio.py projects/<slug> --check-chunks
```

Writes `work/audio.json` (schema below). Purely additive — reads
`work/clip.json` + `work/words.json`, writes one new file, touches nothing
that exists today. Already run against all four shipped projects as a
safety check; only creates `work/audio.json` in each, no other file
changed. `--check-chunks` also prints chunk-boundary warnings against
`brief.json` at prep time, in the same spot the transcript and its pause
list already print — a natural place for a person to notice a proposed
break sits mid-phrase, before `build` ever runs.

### `work/audio.json` schema

```
{
  "meta": {"sourceAudio": str, "sampleRate": int, "fps": 30, "wordCount": int},
  "takeStats": {"rmsP90": float, "expectedSecondsPerChar": float,
                "pauseThresholdSeconds": float},
  "words": [
    {"index": int, "word": str, "start": float, "end": float,
     "rms": float, "energyNorm": float, "durationRatio": float,
     "pitchRangeSemitones": float, "pitchMeanHz": float | null,
     "emphasis": float}   // 0..1, min-max normalised across the take
  ],
  "gaps": [float, ...],   // gaps[i] = words[i+1].start - words[i].end
  "phrases": [
    {"startIndex": int, "endIndex": int, "startSeconds": float,
     "endSeconds": float, "wordCount": int, "charCount": int,
     "durationSeconds": float, "wordsPerSecond": float, "charsPerSecond": float}
  ]
}
```

### Functions ready to call

```python
import measure_audio as audio_engine   # same sys.path.insert pattern as `palette`

audio_engine.check_chunk_boundaries(brief, words, audio) -> list[str]
audio_engine.suggest_payload_word(word_indices, audio) -> int | None
```

`check_chunk_boundaries` returns warning strings (no exception, no
mutation) — print them next to the existing skip-candidate report in
`build_captions.py`'s own output, same treatment.

---

## 2. What `build` should call

### 2.1 Typography — pin or auto-pick a pairing

```python
import typography as typography_engine   # scripts/typography.py
```

New brief key, entirely optional:

```json
{ "style": { "typePairing": "warmEditorial" } }
```

or `"typePairing": "auto"` to rotate (see axis schema, §3). **Absent
key → zero new code executes for this clip** — `theme.type.lead/key` are
left exactly as `THEME`'s existing hardcoded values
(`PlayfairDisplay`/`Anton`), which is what all four shipped briefs already
get. This is the guarantee.

When present:

```python
pairing_name = brief.get("style", {}).get("typePairing")
if pairing_name:
    resolved = (typography_engine.rotation_pick(load_rotation_history("typePairing"))
                if pairing_name == "auto" else pairing_name)
    pairing = typography_engine.PAIRINGS[resolved]
    theme = deep_merge(theme, {"type": {"lead": pairing["lead"], "key": pairing["key"]}})
```

`deep_merge` is already generic (`build_captions.py` already merges
`brief.get("theme")` the same way), so this is additive: `pairing["lead"]`/
`pairing["key"]` are plain dicts shaped exactly like `THEME["type"]["lead"]`/
`["key"]` already are (`fontFamily`, `weight`, `lineHeight`,
`letterSpacing`, plus `style` for the lead and `advanceEm` for the key —
see `scripts/typography.py:PAIRINGS`). No restructuring of `THEME` needed.

**New key inside `theme.type.lead`**: `style: "italic" | "normal"`.
Absent → `"italic"` (matches every shipped clip; `DoctorVideo.tsx` already
defaults it the same way). Only `quietPremium`/`warmEditorial`/etc. ever set
it, and they all set `"italic"` too — none of the five researched pairings
uses an upright lead, so in practice this key never needs to change value,
only exist as a default-safe field.

`load_rotation_history("typePairing")` is a stub name — see §3 for how this
should actually resolve once the shared register-selector schema exists.
Until then, or if that lands later than this, the safe fallback is: no
persisted history at all, `rotation_pick([])` on every call, which always
returns `"heritage"` (first key in `PAIRINGS`, dict order) — i.e., even a
literal `"auto"` with no history wired up degrades to today's default
rather than to an error or a random pick.

### 2.2 Motion — per-beat reveal selection

```python
import motion as motion_engine   # scripts/motion.py
```

Three levers, in order of precedence:

1. **Per-beat pin** — a brief's chunk spec: `{"key": [...], "lines": [...],
   "reveal": "punchPop"}`. Highest precedence, always honoured verbatim.
2. **Clip-wide pin** — `brief["style"]["revealStyle"]`, one of
   `motion.REVEAL_STYLES` (excluding `legacyMaskWipe`, which is
   implicit-only — see below). Applied to every beat that has no per-beat
   pin of its own.
3. **Auto** — `brief["style"]["autoMotion"] = true` AND `work/audio.json`
   exists. Runs `should_animate` + `choose_reveal` per beat using the
   measurements below. This is the "do the best job on its own" path.

**If NONE of the three are present, no chunk gets a `reveal` key at all** —
`DoctorVideo.tsx` then resolves every chunk to `legacyMaskWipe`, today's
exact code path. This is the second half of the byte-identical guarantee:
the four shipped briefs set none of these three, so nothing changes for
them, ever, regardless of how many later clips opt in.

Sketch (after `chunks` is built, before it is written to `data`):

```python
def top_decile_emphasis(audio):
    import numpy as np
    return float(np.percentile([w["emphasis"] for w in audio["words"]], 90))

auto = brief.get("style", {}).get("autoMotion")
clip_pin = brief.get("style", {}).get("revealStyle")
audio = None
if auto and (work / "audio.json").exists():
    audio = json.loads((work / "audio.json").read_text())
    hero_floor = top_decile_emphasis(audio)

consec = 0
for chunk, spec in zip(chunks, specs_kept_in_order):  # specs_kept_in_order excludes skipped beats
    if "reveal" in spec:
        chunk["reveal"] = spec["reveal"]
    elif clip_pin:
        chunk["reveal"] = clip_pin
    elif audio:
        dur = chunk["toFrame"] - chunk["fromFrame"]
        by_idx = {w["index"]: w["emphasis"] for w in audio["words"]}
        beat_emphasis = max((by_idx.get(i, 0.0) for i in chunk["keyWords"]), default=0.0)
        graphic_frac = (occupied_frac(top_win, chunk["fromFrame"], chunk["toFrame"])
                        if chunk["zone"] == "top" else 0.0)
        gesture = motion_engine.gesture_intensity(
            clip["clip"], chunk["fromFrame"] / FPS, chunk["toFrame"] / FPS)
        is_hero = (chunk["zone"] == "top" and not layout["captionScrim"]["enabled"]
                   and dur >= ms(1800) and beat_emphasis >= hero_floor)
        animate, _reason = motion_engine.should_animate(dur, graphic_frac, gesture, consec, is_hero)
        if animate:
            chunk["reveal"] = motion_engine.choose_reveal(
                dur, chunk["zone"], layout["captionScrim"]["enabled"],
                beat_emphasis, is_hero, prior_styles=[c.get("reveal") for c in chunks[:chunks.index(chunk)]]
            )["style"]
            consec += 1
        else:
            chunk["reveal"] = "wordStagger"   # quiet, legible, never the legacy mask
            consec = 0
    # else: no key set at all -> legacyMaskWipe in the TSX
```

Print, alongside the existing per-beat report line: which style each beat
got and why (`should_animate`'s second return value is a ready-made
reason string).

**New key**: `phases[1].chunks[i].reveal?: string`. Optional, one of
`legacyMaskWipe | maskWipeFast | wordStagger | charCascade | punchPop |
blurIn`. Absent → `legacyMaskWipe`.

---

## 3. Axis-schema entries, for the shared non-repetition selector

Two new axes, in the shape requested: name, candidate values, and what
"different enough" means for that axis specifically.

### `typePairing`

- **Candidates**: `heritage`, `warmEditorial`, `classicPress`,
  `modernCalm`, `quietPremium` (see `scripts/typography.py:PAIRINGS`).
- **Different-enough rule**: two values are the SAME only if they share
  BOTH the lead font family and the payload font family. In practice all
  five candidates are pairwise distinct on both faces, so any two different
  names already satisfy this — the rule is stated for when a future sixth
  pairing reuses one face from an existing one (e.g. a hypothetical
  `Fraunces / Anton` pairing would only collide with `warmEditorial` on the
  lead, not the payload, and should still count as sufficiently different).
- **Default / fallback**: `heritage`. This must stay the fallback in two
  senses: it is what an ABSENT `typePairing` key resolves to (no new code
  runs), and it is what `rotation_pick([])` returns when no history is
  available yet — the same value from two different code paths, which is
  what keeps a brief-new "auto" clip and a brief with the key entirely
  missing indistinguishable in output until a real rotation history exists.
- **History granularity**: per-clip, one value per clip, in the order
  clips are processed. Do NOT backfill history from the four shipped clips
  — they never set this key, so they have no entry; seeding the rotation
  with synthetic history for them would change what the FIFTH real clip
  computes, not the four themselves, but it is cleaner and more honest for
  the ledger to start empty and mean "no clip has opted into this axis
  yet" rather than to fabricate a history for clips that never chose one.

### `revealStyle`

- **Candidates**: `maskWipeFast`, `wordStagger`, `charCascade`, `punchPop`,
  `blurIn` (see `scripts/motion.py:REVEAL_STYLES`). **`legacyMaskWipe` is
  never a candidate on this axis** — it is not a style anything should
  choose; it exists solely as the implicit resolution of an absent
  `reveal` field, for backward compatibility.
- **Different-enough rule**: exact name match only — there is no partial
  credit between styles the way two colours can be "close" in hue. But
  read the granularity note below before wiring this into clip-level
  non-repetition.
- **Granularity — the important caveat**: unlike `typePairing` (one choice
  per clip), `revealStyle` is chosen **per beat**, by
  `scripts/motion.py:choose_reveal()`, from that beat's own duration/zone/
  emphasis — it already varies within a single clip by design (see
  `docs/TYPE-AND-MOTION.md` Part 3's "repetition" rule, which forces
  variety WITHIN a clip after three identical styles in a row). Folding
  per-beat choices into a CLIP-LEVEL "don't repeat the last two reels"
  axis would fight that per-beat logic rather than complement it. If the
  shared selector wants a `revealStyle` axis at all, it should apply only
  to `brief.style.revealStyle` — the CLIP-WIDE pin described in §2.2, used
  rarely, when a whole clip should visibly commit to one reveal register —
  not to the per-beat `auto` selections, which should stay driven by
  `choose_reveal()` regardless of what the last clip did.
- **Default / fallback**: no clip-level pin at all (per-beat `auto`, or
  `legacyMaskWipe` if `autoMotion` is also unset).

---

## 4. Shading dependency — read before building gradient scrims

`docs/TYPE-AND-MOTION.md` Part 3 has the full reasoning; the operative
constraint for whoever builds the new shading treatments: **none of the
five new reveal styles assume a flat backdrop — they reveal the glyph
itself, never the background — so they keep working mechanically over a
gradient.** The thing that WOULD break is `palette.py`'s current
assumption that a beat's payload sits on one solid colour, which today is
true only because `build_captions.py` guarantees the scrim is fully
opaque by `bottomZone.top + 100`, before any payload begins. If a new
shading treatment puts colour variation THROUGH the payload's own
footprint (not just the panel's leading edge), contrast should be checked
against the worst point under the text, not the panel's nominal colour —
that is purely a `palette.py`/`build_captions.py` change; nothing in
`DoctorVideo.tsx`'s reveal rendering needs to know about it.

---

## 5. Quick reference — every new key

| Location | Key | Type | Default | Effect |
|---|---|---|---|---|
| `theme.type.lead` | `style` | `"italic" \| "normal"` | `"italic"` | which face variant `DoctorVideo.tsx` loads |
| `brief.style` | `typePairing` | `string \| "auto"` | absent | pin/rotate a pairing (§2.1) |
| `brief.style` | `revealStyle` | one of the 5 non-legacy names | absent | clip-wide reveal pin (§2.2) |
| `brief.style` | `autoMotion` | `bool` | `false`/absent | enables per-beat audio-driven selection |
| brief chunk spec | `reveal` | one of the 5 non-legacy names | absent | per-beat pin, highest precedence |
| `phases[1].chunks[i]` (output) | `reveal` | one of 6 names incl. `legacyMaskWipe` | absent → `legacyMaskWipe` | consumed by `DoctorVideo.tsx`'s `KeyLine` dispatcher |

Every row's default is "absent," and absent is defined, on the TSX side, to
reproduce today's rendering exactly. That is the whole guarantee in one
table.
