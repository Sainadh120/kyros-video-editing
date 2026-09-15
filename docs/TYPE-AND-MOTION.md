# Type, motion and audio — the research

This is the companion to the README's Part 2, for the half of the pipeline
that was, until now, a single hardcoded look: which two faces set a reel,
how a caption arrives on screen, and whether the audio says anything about
either. Same standard of evidence as the README — a number that would have
rejected a choice, not an adjective. See `docs/INTEGRATION-type-motion-audio.md`
for the keys and defaults that wire this in; this file is the reasoning and
the worked numbers behind it.

---

## Part 1 — the audio nobody was listening to

Captions have always been timed off forced-alignment word starts and
nothing else. A shouted word and a murmured one got the identical spring.
`scripts/measure_audio.py` reads the same 16kHz alignment WAV
`probe_and_extract.py` already produces (via Python's stdlib `wave` module —
no second ffmpeg decode, no new dependency) and measures, per word: RMS
energy normalised against the take's own 90th percentile, a duration ratio
against the take's own median seconds-per-character, and a pitch range in
semitones from a plain autocorrelation F0 tracker over 40ms frames. The
three combine (0.4 / 0.3 / 0.3) into an emphasis score, min-max normalised
across the take.

**Pause threshold, measured not pinned.** Same reasoning as the caption
ground: sort the take's inter-word gaps and find the largest multiplicative
jump between consecutive values — the boundary between "still mid-phrase"
and "a real pause" — clamped to [0.12s, 1.2s]. Measured on the four shipped
clips:

| Clip | Pause threshold | Words | Phrases | Speaking rate |
|---|---|---|---|---|
| `pcos-insulin-resistance` | 0.83s | 38 | 3 | 2.60–2.80 words/s |
| `pcos-muscle` | 0.22s | 80 | 9 | 2.14–3.10 words/s |
| `pcos-sleep-cycle` | 0.41s | 61 | 8 | 2.12–10.00 words/s |
| `pcos-walking` | 0.37s | 58 | 4 | 2.55–2.99 words/s |

Four different numbers from four different takes, which is the point — a
pinned 0.3s constant would have called `pcos-muscle`'s tightly-run delivery
"all one phrase" and `pcos-insulin-resistance`'s more deliberate one "eight
separate phrases."

**The hand-written chunk list, checked against the pauses.** Every shipped
brief's chunk boundaries were authored by reading the transcript, not the
waveform. Run against the measured pause threshold:

| Clip | Boundaries checked | Landing in continuous speech |
|---|---|---|
| `pcos-insulin-resistance` | 5 | 4 |
| `pcos-muscle` | 8 | 1 |
| `pcos-sleep-cycle` | 7 | 3 |
| `pcos-walking` | 6 | 4 |

12 of 26 checked boundaries (46%) land with a 0.00s gap — one word runs
straight into the next. That is not necessarily wrong: a caption break can
sit inside one breath on purpose, to give a reveal a head start before the
next payload word is spoken, and every shipped clip already reads correctly
on screen. But it means the boundaries were never actually checked against
the audio before this — `check_chunk_boundaries()` now does, and warns
rather than blocks, exactly like the skip-candidate report already does for
graphic coverage.

**The acoustically emphasised word, as a check on the payload choice.**
`suggest_payload_word()` ranks a beat's own words by emphasis, first
excluding a short closed list of connectives (`a/is/of/in/the/for/and/...`)
— unfiltered, the single highest-emphasis word in the WHOLE take was a
connective on all four clips ("of", "is", "in", "Is"), because a held or
pitch-raised "is" is a real acoustic event, just never the word that should
go large. Tested against the four shipped clips' own chosen payload words:
**the suggested word falls inside the beat's actual payload set on 20 of 30
beats (67%)**. That is a real signal, not a coincidence — but 33% miss rate
means this is a build-time cross-check for a person to glance at, the same
role the skip-candidate report plays, not a replacement for the chunking
round-trip the README already spends twenty seconds on.

**Gesture intensity.** A coarse frame-differencing reading (6fps, 64×114px,
full-frame mean absolute difference, normalised against a fixed ceiling of
30) of how much is moving in a span — reused for the animate/don't-animate
rule below. Pooled across 1-second windows over all four shipped clips:
median 0.10, p90 0.21, p99 0.44. The "high gesture" threshold used below
(0.20) is this take's own top decile, not a guessed round number.

---

## Part 2 — a type-pairing system

Today: Playfair Display italic for the lead, Anton for the payload, on
every reel. The README already says the pairing is meant to vary clip to
clip; the code never made that true. Five pairings now exist —
`scripts/typography.py:PAIRINGS` — the original plus four researched
alternatives, each validated against the real payload strings that have
already shipped, not asserted from taste.

### What was researched

Looking at how well-made vertical health/clinical content is actually set
(not general "trending fonts" lists): the working pattern in that space is
consistently a **high-contrast pairing** — an editorial serif (often
italic, often a "soft-serif" cut rather than a hard Didone) carrying the
spoken, conversational line, against a **condensed grotesque** carrying the
one-word takeaway. The condensed cut matters for a structural reason, not a
stylistic one: a payload has to hold a real phrase — sometimes two lines of
it — inside roughly 940-990px, and an uncondensed bold face simply cannot,
no matter how legible or premium it reads (see Rejections). The serif does
the opposite job: it never has to fit a hard width budget (it wraps,
word-staggers, sits at a modest size), so it is free to be chosen purely for
register — how warm, how classical, how quiet.

Every pairing here keeps that contrast (serif/italic lead vs. sans/caps
payload) and varies WHICH serif and WHICH condensed grotesque, so five
pairings read as five registers, not five random font swaps.

### How width was actually measured

Not asserted, not "looks condensed enough." The five candidate payload
faces' `.woff2` files were downloaded from the exact `fonts.gstatic.com` URLs
`@remotion/google-fonts` resolves for that family/weight (confirmed against
the installed package's own font-info tables — every weight below exists in
`@remotion/google-fonts` at that exact value), decompressed, and read with
`fontTools` for each glyph's real advance width (`hmtx`, normalised by
`unitsPerEm`). No kerning (no `harfbuzz` available in this environment) —
immaterial here: a few px on an 848-933px measurement with 28-92px of
margin cannot flip a pass into a fail.

Two worst-case lines, both from shipped clips, both driving today's actual
sizing:

- **"MAINTAINING MUSCLE"** (18 chars) — the longest single line shipped,
  bottom zone, `pcos-muscle`'s own tightest geometry (`paddingX=48` →
  984px available).
- **"TREATMENT OF PCOS"** (18 chars) — the longest top-zone line, default
  geometry (`paddingX=70` → 940px available).

For each font, the measured per-string em-widths give a calibrated
`advanceEm` (the per-character average the sizing rule's own `key_size()`
formula already uses, just measured per font instead of guessed once for
Anton and reused everywhere). Running the SAME formula `build_captions.py`
already runs, with that calibrated constant:

| Pairing | Lead | Payload | Bottom-zone fit | Top-zone fit |
|---|---|---|---|---|
| `heritage` (default) | Playfair Display italic 500 | Anton 400 | 927/984px (+57) | 878/940px (+62) |
| `warmEditorial` | Fraunces italic 500 | Barlow Condensed 800 | 932/984px (+52) | 912/940px (+28) |
| `classicPress` | Cormorant Garamond italic 600 | Oswald 700 | 909/984px (+75) | 863/940px (+77) |
| `modernCalm` | Newsreader italic 500 | Saira Condensed 800 | 933/984px (+51) | 878/940px (+62) |
| `quietPremium` | Instrument Serif italic 400 | Antonio 700 | 919/984px (+65) | 848/940px (+92) |

Every pairing clears both worst-case lines with real margin. `warmEditorial`
is the tightest (+28px at the top zone — Barlow Condensed is, at 800 weight,
the least condensed of the five candidates that still passed) but still
comfortably inside budget.

### The registers

- **`heritage`** (default, unchanged) — Playfair's Didone sharpness against
  Anton's ungiving grotesque. Warm but a little severe; the original voice.
- **`warmEditorial`** — Fraunces (a soft-serif built for warm editorial
  work, none of Playfair's hairline brittleness) against Barlow Condensed
  (a humanist condensed grotesque drawn for UI/signage legibility, not a
  poster face). Calmer, rounder, less "shouted."
- **`classicPress`** — Cormorant Garamond, the most delicate classical
  revival in the set, against Oswald (redrawn from 1920s Alternate Gothic
  signage) — a documentary title-card feel. The highest lead/payload
  contrast of the five.
- **`modernCalm`** — Newsreader (Google's own long-reading-text serif, so
  it reads unaffected rather than "designed" even at a modest lead size)
  against Saira Condensed — a crisper, more geometric, faster-feeling
  payload. Best for a clip whose beats move quickly.
- **`quietPremium`** — Instrument Serif (a single-weight, high-fashion
  editorial italic, the thinnest/quietest lead of the five) against Antonio
  (a clean condensed grotesque with a rounder shoulder than Anton, the
  least "shouted" payload). Reserved for a genuinely calm hero beat — this
  pairing on a fast, busy clip would read as underpowered.

### Rejections

| Candidate | Killed by |
|---|---|
| Poppins ExtraBold 800 | Not condensed: at the sizing rule's OWN floor (96px — before any attempt to fit a real payload size) "MAINTAINING MUSCLE" already measures **1083px against 984px available — 99px over, at the smallest size the system will ever pick.** |
| Montserrat Black 900 | Same failure, worse: **1105px at the 96px floor, 121px over.** |
| Righteous | Fails on width too (**1004px at the 96px floor, 20px over**) AND on register — a rounded novelty display face reads as a meme caption, not a clinic's. |
| Staatliches | Clears width. Rejected on register, not a number: its deliberately uneven, hand-cut strokes read as a poster/flyer face sustained across a whole screen presence, not a clinical one. |

The first two are the important lesson: "bold enough" and "condensed
enough" are different axes, and a face can have plenty of the first with
none of the second. Every candidate that shipped above was chosen from
fonts DESIGNED as condensed cuts, not merely heavy ones — the difference is
visible in the numbers, not just the specimen.

### Rotation

`scripts/typography.py:rotation_pick(history)` picks a pairing that is not
one of the last two used — the exact rule the palette and question-card
rotations already run (README: "rotate; do not repeat the last two reels").
A brief pins one explicitly with `style.typePairing`.

---

## Part 3 — a text-reveal library

Today, one reveal, everywhere: a vertical mask wipe for the payload,
word-by-word fade for the lead. `scripts/motion.py:REVEAL_STYLES` adds five
more, each with an explicit frame budget, and the decision rule
(`choose_reveal`) that picks one from Task A's measurements plus the beat's
zone and duration.

### The bug this is built around

A frame pulled at 10.5s of the shipped `pcos-sleep-cycle` cut caught the
payload "UNDER CONTROL" mid-wipe, rendering as a flat grey half-drawn line —
on a still, that reads as a rendering fault, not an in-progress reveal.
Reproduced here deliberately, on the unmodified legacy code path, at the
exact same frame, to confirm the mechanism before fixing it:

**Why it happens**: the legacy reveal clips a line VERTICALLY — the text
rises up through a fixed-height `overflow:hidden` window the height of one
text line. At any mid-transition frame, that shows only the TOP portion of
EVERY glyph in the line simultaneously — a horizontal band cutting through
every letterform at once, which is what reads as "half-drawn." Measured
illegibility window: **~9-13 frames (0.3-0.43s)** at `M.wipeFrames` (~13
frames) — long enough to be caught by any freeze-frame or thumbnail pull in
roughly a third of the reveal's own duration.

**The fix — `maskWipeFast`**: rotate the wipe axis 90 degrees. A
`clip-path: inset()` reveals the line LEFT TO RIGHT instead. At every
instant, every VISIBLE character is its complete glyph — only the count of
visible characters changes, never a fragment of one. The sweep runs in a
fixed 6 frames (0.2s) regardless of line length, so on every payload line
shipped so far (6-19 characters) the wipe edge sits inside any single
glyph's width for at most ~1 frame before moving past it. Rendered proof
(scratch render, frame 315, the exact bug frame, with only this beat's
`reveal` field changed to `maskWipeFast`): the line reads "UNDE|R" with a
single clean vertical cut through the "R" — every visible letter complete,
legible as an in-progress reveal, not a fault.

**This is NOT applied to the four shipped clips.** Their captions_data.json
carries no `reveal` field on any chunk, which resolves to `legacyMaskWipe` —
the original, byte-for-byte-unchanged code — specifically so they keep
rendering exactly as they do today, illegibility window included. New clips
should never opt into `legacyMaskWipe`; it exists only so old output is not
silently altered by this work.

### The rest of the library

| Style | Mechanism | Illegibility window | Displacement | Used when |
|---|---|---|---|---|
| `legacyMaskWipe` | vertical clip, slow spring | ~9-13f (0.3-0.43s) — the defect above | 0px (clipped, not translated) | never (implicit only, pre-existing clips) |
| `maskWipeFast` | horizontal `clip-path`, 6f sweep | ≤1f, one glyph at most | 0px | the new default for a normal beat |
| `wordStagger` | whole-word fade + rise, no mask | 0f — no spatial cut is possible | ≤10px | a fast beat (<0.9s) or a quiet aside under a graphic |
| `charCascade` | whole-character fade + rise, no mask | 0f, same reasoning | ≤8px | an energetic beat, list items, short punchy payloads |
| `punchPop` | scale 0.85→1.04→1.0 + opacity, no mask | 0f, same reasoning | 0px | the beat's payload carries a top-quartile emphasis word |
| `blurIn` | blur 10px→0 + opacity, no mask, 20f | see below | 0px | a hero beat only: ≥1.8s, top zone, no scrim, top-decile emphasis |

**Why `wordStagger`/`charCascade`/`punchPop` get a hard 0-frame number, not
a measured-small one**: none of the three ever clips or masks anything. A
faint, small-scale, or not-yet-full-size glyph is still its own COMPLETE
outline at every frame — there is no spatial cut for a freeze-frame to
catch mid-motion. The zero is a property of the technique, not a tuning
result.

**Why `blurIn` is held to a different kind of proof, not exempted**: the
brief's own hard rule is "no illegible intermediate state... in no more
than a couple of frames," and a slow blur reveal spends far longer than
that with real blur on the glyph, on purpose — that IS the "hero beat can
afford a slower, bigger reveal" case the research was asked to cover. The
resolution: the ORIGINAL bug's failure mode was a fragmentary, broken glyph
shape (a half-drawn line) — something a person would call a rendering
FAULT. A blurred-but-whole glyph is a different, and much more forgiving,
failure mode: every frame still shows the complete outline, softened, which
reads as "the words are coming into focus," an intentional aesthetic, not
broken output. Rendered proof (frame 318 of the same beat, 10 frames into a
20-frame blur): "UNDER CONTROL" is fully readable, softly out of focus —
not a fault. `blurIn` is reserved for exactly the beat this reasoning
applies to (a genuine hero: long, bare wall, no competing scrim, top-decile
emphasis) and nowhere else, so the forgiving failure mode is never asked to
cover a beat that does not deserve the risk.

**Scope limit, stated plainly**: `punchPop` snaps the whole payload LINE,
not one word highlighted inside a longer surviving line — `build_captions`
should route it only to beats whose payload line already IS the emphasised
word (a single short line), which is how most payloads already resolve by
the time sizing picks them. True per-word highlighting inside a multi-word
line is not implemented.

### When a beat earns a reveal, and when it should not

The README already has this rule one level up: "a caption is owed to
nothing" — when a burned-in graphic already carries the point, the caption
should not exist at all. This is the same logic one level down: a caption
that DOES appear is not automatically a caption that should ANIMATE.
`scripts/motion.py:should_animate()` says no for four measured reasons, and
a hero beat overrides all four:

1. **Duration.** A beat under 30 frames (1.0s at 30fps) is on screen for
   less time than `wordStagger`'s own longest stagger+settle already takes
   (~18-24f). The reveal would still be resolving when the beat starts
   leaving — that is flicker, not a reveal.
2. **A moving graphic underneath.** If a burned-in graphic covers ≥60% of
   the beat's span, it is very likely animating on its own account
   (illustrations, wipes, counters — see the README's own overlay
   examples). Stacking a text reveal on top asks for attention twice in one
   breath. (Beats ≥75% covered are usually skipped entirely by the existing
   restraint rule; this covers the 60-75% band that still gets a caption.)
3. **Gesture.** `gesture_intensity` ≥ 0.20 — the measured top decile across
   the four shipped takes' own footage (median 0.10, p90 0.21, p99 0.44,
   pooled over 1-second windows) — means she is already the dominant
   motion in frame for that span. A translating or masking reveal competes
   with her instead of supporting her.
4. **Repetition.** Three animated beats already in a row defaults the
   fourth to a flat cut/fade regardless of its own numbers — "don't be
   bored" cuts both ways: three staggered reveals running back-to-back is a
   template running, not a reel reacting to what she said.

A **hero beat** (long, bare wall, high emphasis — the one place the brief
calls for "a slower, bigger reveal") overrides all four checks
unconditionally.

### Shading interacts with type — flagged, not solved here

The colour/placement half of the pipeline is moving from a single flat
scrim to gradient scrims, tinted washes and depth treatments (owned
elsewhere). Two consequences for this system, stated so the two halves
reconcile cleanly:

- **Reveal legibility must be judged against the gradient's worst point,
  not its average.** None of `maskWipeFast`/`wordStagger`/`charCascade`/
  `punchPop`/`blurIn` assume anything about the background — they reveal
  the TEXT, not the ground behind it — so none of them break structurally
  on a gradient. But today's invariant that the payload always sits on the
  SOLID part of the scrim (`build_captions.py` already guarantees the panel
  reaches full opacity by `bottomZone.top + 100`, before any payload
  begins) is what currently lets `palette.py` pick one colour per beat
  against one background colour. If a new shading treatment introduces
  colour variation THROUGH the payload's own footprint — not just the
  panel's leading edge — colour choice needs to score against the worst
  point under the text, not the panel's nominal ground colour. That is a
  `palette.py` concern, flagged here because it changes what "legible"
  means for whichever reveal is chosen, not because this system needs to
  change.
- **No reveal here relies on a flat backdrop to function.** `maskWipeFast`
  clips the glyph itself via `clip-path`; the stagger/punch/blur styles
  never mask at all. All five continue to work, mechanically, over a
  gradient ground.

---

## Summary tables for the axis-schema integration

See `docs/INTEGRATION-type-motion-audio.md` for how `typePairing` and
`revealStyle` register as axes in the shared non-repetition selector.
