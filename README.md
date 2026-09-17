# Reels

Turns a doctor's clip into two finished reels: the Kyros cut, and one branded
for the doctor's own clinic.

```
Reels/
├── brand/
│   ├── kyros/      the mark + outro. Same on every clip.
│   ├── doctors/    one folder per doctor: plate.png + doctor.json
│   └── partners/   one folder per clinic: logo.png + partner.json
├── studio/         the Remotion project. Installed once, reused for every clip.
├── scripts/        the pipeline
└── projects/       one folder per clip
```

**The short version:** drop the clip, send one message, answer two questions,
post. Everything between is handled.

---

# Part 1 — doing one clip, start to finish

## 1. Create the project and drop the clip

```bash
cd ~/Downloads/Personal/Kyros_Project/Reels
python3 scripts/reels.py new pcos-thyroid-link
```

Copy the clip into `projects/pcos-thyroid-link/inbox/`. **That is the only file
you drop.** The doctor's plate, the partner's logo and the Kyros mark and outro
all resolve from `brand/`.

Pick a slug that describes the question — `pcos-thyroid-link`,
`metformin-side-effects`. It becomes the output filename, so it is how you find
this reel again in six weeks.

Or skip the command entirely: say "new clip, it's at `<path>`" and it gets set
up for you.

## 2. Say who is in it

| Situation | What to send |
|---|---|
| Dr. Bharani + Aster Ramesh | Nothing. Both on file, pairing is automatic. |
| New doctor | Their name-plate PNG, plus name, title, registration number. |
| New partner clinic | Their logo — **PNG at 1500px+ or SVG**. |

Ask for a good logo file up front. A small JPEG once forced a 3.3× upscale and
the partner's mark came out visibly soft; a proper PNG arrived in a minute and
the problem disappeared.

Check who is already stored:

```bash
python3 scripts/reels.py library _
```

A new doctor only has to be added once. The clip after that needs nothing.

## 3. Confirm the take

```bash
python3 scripts/reels.py prep <slug>
```

Probes the clip, transcribes it word by word, measures the scene, **scans for
graphics already burned into the footage**, and **derives the caption palette
from the measured background**. The transcript gets read back to you —
**confirm it is the right clip.**

Not ceremony: a clip arrived once that was a completely different Q&A from the
one described. Caught here it costs nothing; caught after rendering it costs
everything after this point.

The scan also reports anything already on screen in the raw clip:

```
top     burned-in graphic at  5.0-7.3s, 12.3-24.4s
bottom  clear the whole take
```

That map drives two later decisions automatically: where each caption sits, and
**which captions should not exist at all**. See Part 2.

## 4. Decision one — the chunking

The breakdown is proposed as plain text:

```
Majority of women with  ->  PCOS
has                     ->  INSULIN / RESISTANCE
that is around          ->  65–70%
```

Twenty seconds to read. Approve, or move the emphasis.

**This is where the reel is won or lost.** Which words go large is the whole
difference between a reel that lands and one that reads like a document. A
wrong payload word means a re-render, so the round trip pays for itself.

If you already know the timing and placement you want — "0:04 to 0:09 at top,
then bottom" — send it with the clip and it gets built to your spec instead of
proposed.

## 5. Decision two — the style

`prep` ends by printing a proposed register — the question card, ground
polarity, lead style, palette lead and (once populated) type pairing and
reveal style — each one an option that differs from your last two reels, so
the feed does not go monotone. That is `scripts/register.py` reading the
prior briefs, not a manual check; see "The register" in Part 2. Say yes, or
send a reference screenshot — one image settles what a paragraph cannot.

The things that vary: the **question card**, the type pairing, where the text
sits, how it reveals, how the payload is treated, and which colours carry it.
Two or three change each time. Changing one is invisible; changing all of them
looks like a different account.

## 5b. Supporting visuals — optional, proposed in the same message

When a beat names something you can show — steps, swimming, a gym, a number,
a list — the chunking arrives with a visual proposal beside it: nothing (her
face carries it), a text/number animation drawn by Remotion (free), an AI
still with a slow camera move, or a short AI video. Each one shows exactly
what she says on that beat, realistically, and nothing she didn't.

```bash
python3 scripts/reels.py visuals <slug>                 # the plan, her words beside each prompt, cost
python3 scripts/reels.py visuals <slug> --approve all   # then --generate, then --preview
```

She shrinks into a corner bubble while a picture fills the frame and pops
back after, or a card sits on the bare wall above her head while she stays
full-frame. Every visual is placed against the same hazards as the captions.
Generation runs on our own Modal servers (`infra/modal/`), is cached, and never
blocks the reel — a visual that fails is left out. No `visuals` block, no
change. Setup and details: `docs/VISUALS.md`.

## 6. Build, render, verify

```bash
python3 scripts/reels.py check  _          # the rule suite, ~1.5s, no render
python3 scripts/reels.py build  <slug>
python3 scripts/reels.py stage  <slug>     # NEVER skip this
python3 scripts/reels.py render <slug> kyros     # finalise this one first
python3 scripts/reels.py render <slug> partner   # then this one, after sign-off
python3 scripts/reels.py verify <slug>
```

> **`stage` is not optional.** `build` writes `work/captions_data.json`;
> `stage` copies it into the studio; `render` reads only what the studio holds.
> Skip `stage` and you render the *previous* version with no warning and no
> error — the render succeeds, `verify` passes, and every change you just made
> is silently absent. This has happened.
>
> It can no longer happen quietly. `stage` writes a receipt
> (`studio/src/.staged.json`: slug + digest) and `render` **refuses to start**
> when that receipt does not match the build in front of it, naming both
> digests. Each finished cut is stamped with `<slug>-<cut>.render.json`, so
> "was this cut built from this data?" stays answerable afterwards instead of
> being remembered.

Render one cut at a time. Get the Kyros cut right — that is where the wording
and the timing are settled — then render the partner cut from the same edit; it
inherits every caption and only swaps the logo slot and end card.

Add `--overlays` to `render` **only** if you are compositing your own visuals in
an editor. Otherwise skip it — it roughly doubles render time and adds several
hundred MB of files you will not open.

`check` runs the rule suite — colour polarity and contrast, plate and mark
placement, reveal budgets, type fit, the register's non-repetition, and the
delivery gates. Around 110 cases, about a second and a half, no render needed.
Every one of them is a reel that had to be thrown away or a bug that shipped
and was caught later; `docs/TEST-CASES.md` names which for each. Run it before
staging, not after a render disappoints.

`verify` checks with numbers rather than a glance: durations, whether clips are
actually playing, whether transparent layers are actually transparent. It exists
because three bugs shipped past visual inspection — an end card that held one
frame for three seconds and looked deliberate, a stat card that sat as an empty
box, and a logo at 1.6:1 against the wall.

**`verify` cannot see colour or placement.** It passes happily on a cut whose
captions are illegible — and it passed `pcos-sleep-cycle`, whose doctor plate
covers a caption for 27 frames. Pull frames and look at them, and pull them
*inside* the fixture windows, not around them: the plate collision was missed
on first inspection because 8.4s and 10.5s were sampled and the fault sits
between them.

```bash
ffmpeg -ss 20.6 -i projects/<slug>/out/<slug>-kyros.mp4 -frames:v 1 /tmp/f.png
```

## 7. Last read before posting

Registration details are handled at consultation and are not shown on screen.
The doctor is the clinical authority on her own figures — statistics she states
are not second-guessed against other sources.

What is still worth a glance, because it is about wording rather than facts:

- No cure, reverse, or guarantee language, and no promised timelines. Schedule J
  applies to most Kyros verticals; the `kyros-clinical-compliance` skill has the
  per-vertical detail.
- Captions match what she actually said. If her words sit close to awkward
  framing, raise it rather than quietly rewording her.
- No fabricated testimonials, outcomes, or before/after imagery.

Then post:

```
projects/<slug>/out/<slug>-kyros.mp4      -> Kyros accounts
projects/<slug>/out/<slug>-partner.mp4    -> the doctor's clinic
```

And back it up. Media is not in git — until this runs, the only copy of the
clip, the AI files and the cuts is this disk:

```bash
python3 scripts/reels.py push <slug>      # to the R2 bucket; see docs/MEDIA.md
```

---

# Part 2 — the rules the pipeline works by

These are not preferences. Each one is here because ignoring it produced a reel
that had to be thrown away.

## Not every sentence gets a caption

**A caption is owed to nothing.** When the footage already carries the point —
a burned-in graphic naming the same benefit, a diagram doing the explaining —
a caption underneath repeats rather than reinforces. The frame is quieter and
stronger without it, and the viewer is already reading the graphic.

`build` reports this for you:

```
skipped on purpose — the footage carries these itself:
 beat 4: IMPROVES/METABOLIC RATE  (100% under a burned-in graphic)

SKIP CANDIDATES — a graphic covers most of these beats. If it
already says the same thing, set "skip": true on the beat:
 beat 1: LARGEST ORGAN FOR/GLUCOSE DISPOSAL  (100% covered)
```

Any beat ≥75% covered by a graphic is flagged. **Read what the graphic actually
says** — coverage alone is not duplication. If the graphic names the same thing
the caption would, set `"skip": true` on that beat in the brief, with a
`_skipWhy` recording the reason. On `pcos-muscle` four of nine beats went this
way: the footage listed all five benefits in words, so captioning them again
was noise.

Also skip when the subject is small in frame and the visual is doing the work.
A busy frame plus a caption is worse than either alone.

## The mark obeys the footage too

The Kyros mark sits upper-right, *between* the two caption bands — so neither
band's scan answers for it. On `pcos-sleep-cycle` the clip becomes a
full-screen infographic at 13.2s and the mark landed squarely on the
insulin-resistance illustration, while the top-band scan reported nothing
unusual, because by then the whole frame was graphic.

`build` now measures the mark's own rectangle and emits
`fixtures.logoHideWindows`; the mark steps aside for those frames and returns
when the frame is the doctor's again. It reported `13.1–27.0s` on that clip and
**nothing at all** on `pcos-muscle`, whose mark was never covered.

The reference frame for that measurement is taken from a window the overlay
scan already knows is clear — not the clip's median. On a clip that is graphic
for more than half its length, the median *is* the graphic, and every
talking-head frame then reads as "covered". That bug flagged the entire clip
before it was anchored.

### Where the mark goes

Hiding is a big, sudden absence — the brand mark vanishes for a chunk of the
take. Moving it a few hundred pixels to a corner the footage has left alone
is a smaller one, so `solve_mark_anchor()` treats hiding as the *fallback*,
not the first answer.

Two candidate corners on the band the mark has always occupied, mirrored
left/right (`AnimatedLogo` positions purely from `layout.logo.right`/`.y`, so
moving it is a number, not a render change). Each candidate is scored by how
much of the mark's natural on-screen life — from `logoFromFrame` to the end
of the take — it would still have to hide for, after checking its own
rectangle against every hazard: a burned-in graphic measured directly under
that rectangle (the same method as above), the caption bands (motion-padded),
the scrim, and the doctor plate's own solved rectangle and window. Whichever
corner needs to hide least wins; the default upper-right keeps it on a tie,
so the mark only ever moves for a real reason.

Measured on the two clips that actually stress this: `pcos-muscle` never
covers either corner (0% either way, upper-right kept). `pcos-sleep-cycle`'s
infographic is full-screen from 13.2s, so it covers upper-right *and*
upper-left equally — moving the mark buys nothing there, so it correctly
falls through to hiding for `13.1–27.0s`, exactly as before. Both results
match what shipped; the solver exists for the clip where they won't.

## The plate answers to the frame, not just the zone

The old rule for the doctor's title card asked one question — does a
`bottom`-zone chunk's time window overlap the card's default slot? — and
answered it by moving the card to the *other* zone's usual spot. That is a
zone-name check, not a collision check, and it fails exactly when dodging one
collision walks into another: on `pcos-sleep-cycle`, pushing the card up to
clear a low caption landed it, unmeasured, inside the top zone's own box —
where the very next beat ("HORMONES / UNDER CONTROL") renders. The old code
had no way to notice, because it never asked what was drawn in the box it
moved to.

`solve_doctor_plate()` asks the real question instead: the plate's actual
pixel rectangle — `left`, `top`, `targetPillWidth`, and the pill's measured
aspect, not the file's transparent padding — checked against every hazard as
a rectangle, not a zone name:

- the top and bottom caption zone boxes, but only for whichever chunks
  actually render there, each padded by `chunkInFrames`/`chunkOutFrames` on
  both ends so a chunk still animating in or out still counts as occupying
  the screen;
- the caption scrim's box (`captionScrim.top` down), live exactly when a
  bottom chunk is;
- the Kyros mark's rectangle and its own hide windows;
- the platform safe area, *and* a burned-in graphic measured **directly
  under the plate's own candidate rectangle** — reusing the mark's
  reference-frame trick (`measure_hide_windows()`, generalised from
  `logo_hide_windows()`), because that is the one hazard a zone name can
  never answer for: a full-screen graphic covers both zones' boxes at once,
  and only looking at the actual rectangle catches it regardless of which
  band the scan attributes it to.

One hazard is deliberately *not* trusted at face value: `overlays.json`'s
bottom-band scan. Its own "clean" reference is the take's per-pixel median
(see `scan_overlays.py`), so on a clip that is graphic for close to half its
length that median skews toward the graphic — on `pcos-sleep-cycle` (13.8 of
27.0s graphic) it flags the safe first third of the take and clears the
actually-covered final third, backwards. Treating it as a hard veto erased
the one genuinely clear window this clip has. It is kept as a *soft* hazard —
reported in the build log, folded into the least-bad fallback — but only the
directly-measured rectangle can veto a slot outright.

Two anchors are tried — **low**, over the subject where the card has always
lived (clamped into the safe area: the old fixed `top: 1430` default sits
43px past the 15% bottom line for this doctor's plate aspect, which this
solver catches rather than repeats), and **high**, tucked under the top
zone's own edge — and the earliest slot that is clear on every hazard wins,
with a 1900ms hold shortened only as far as `900ms` if the clear window is
tighter. A brief that pins `doctorPlate.top`/`left`/`appearFrame`/
`holdFrames` still wins outright; the solver then only *reports* what that
pinned slot collides with, loudly, rather than silently accepting it — which
is how it caught a real, previously unnoticed collision on the shipped
`pcos-walking` render (below).

**Measured on all four shipped clips:**

| Clip | Anchor | Appears | Held | Result |
|---|---|---|---|---|
| `pcos-insulin-resistance` | low, y=1386 | f134 (4.5s) | 57f | clear — no caption ever shares this band (every beat is top-zone) |
| `pcos-walking` | low, y=1386 (pinned time) | f220 (7.3s) | 104f (pinned) | **NOT CLEAR** — collides with the "FOR BEGINNERS" bottom caption by 56f (1.87s); the brief's pin wins, so this ships as a loud warning, not a silent fix |
| `pcos-muscle` | high, y=308 | f244 (8.1s) | 57f | clear — zero top-zone chunks exist on this clip at all, so the high anchor is free the moment the first burned-in graphic clears (8.0s) |
| `pcos-sleep-cycle` | low, y=1386 | f334 (11.1s) | 44f | clear of every hard hazard; sits 64f from the nearest caption and inside the (untrusted) bottom-band scan's flagged window, noted, not vetoed |

`pcos-sleep-cycle` is the case worth spelling out, since the old logic's
answer (`top: 308`, appearing at f233/7.8s) looked plausible and shipped
unquestioned: that slot in fact overlaps the "HORMONES / UNDER CONTROL"
top-zone caption by roughly 27 frames (0.9s) once real rectangles are
checked, because pushing the card up to dodge a low caption is exactly the
"walks into another collision" failure this section opened with. The solver
independently finds a different, defensible slot instead — low anchor, 11.1s,
in the true gap between the last low caption and the point the infographic
takes over the whole frame — rather than reproducing the old number. Neither
was rendered, so this is a measured, un-rendered finding, not a visual
confirmation; see the deliverable note below.

### When the plate earns its place

Beyond *where*, `solve_doctor_plate()` also encodes *when*, as an explicit
rule rather than an accident of whichever slot happened to be free first:

- it never appears before the answer has started — the hook question owns
  the screen until then, and the plate is never a contender for the earliest
  seconds of the take, only for a slot inside `[answer_start, videoFrames)`;
- among clear slots, the **earliest** always wins — a name-plate that
  reinforces credibility earns more of the take by appearing early, not by
  lingering late where a viewer has already decided whether to keep watching;
- it holds for **1900ms** by default, shortened only as far as the clear
  window forces it, with a **900ms floor** below which a card reads as a
  flash rather than an introduction — `pcos-sleep-cycle`'s 44f (1.47s) is the
  shortest hold any shipped clip has needed, and it is a floor for a reason:
  shorter than that was never proposed, because a plate that doesn't hold
  long enough to be read is worse than one that appears a beat later;
- it does not compete for the same window as the first payload — on every
  clip above, the plate's slot sits inside a stretch where a caption is
  either not yet on screen or already finished, never overlapping the first
  or hero beat's own reveal.

## Colour flips with the ground it sits on

The single most expensive mistake made on this pipeline, twice.

A colour is not legible or illegible on its own — only against what is behind
it. Measured on the same clip:

| Colour | On a pale wall | On a dark scrim |
|---|---|---|
| forest `#103D2C` | 61 ✅ | **3.9** ❌ |
| brick `#A6371C` | 55 ✅ | **18.8** ❌ |
| warm white `#FFF6E8` | 42 ❌ | **101** ✅ |

So the palette has two halves, and the ground picks which one:

- **Type on a pale wall** → the dark half: deep chocolate, forest, brick, rust.
  This is the `pcos-insulin-resistance` register.
- **Type on a dark scrim** → the light half, which is the *same hues flipped up
  in lightness*: forest becomes spring green `#9BE564`, brick becomes coral
  `#FF8F70`, plus mint `#5FE3C0`, warm white `#FFF6E8`, and the brand saffron
  `#FFB01F` held back as the accent.

**Vivid, not neutral.** On a dark ground the temptation is to reach for cream
and stop there. Don't — it reads flat and monotone. The light half exists so the
reel can be colourful.

### A rotation colour has to clear two bars, not one

Contrast alone is not enough. A tone must also be **far enough in hue from its
neighbours and from the accent**, or the rotation reads as one colour repeating.

Worked example — replacing coral, which was the rotation's weak link at 57 Lc:

| Candidate | Lc (floor 62) | Min hue gap (floor 40°) | |
|---|---|---|---|
| apricot `#FFB38F` | 67.7 ✅ | **29°** ❌ | too near the saffron accent |
| flamingo `#FF8FA3` | **56.4** ❌ | 66° ✅ | too dark |
| lilac `#C0A6FF` | **58.3** ❌ | 124° ✅ | too dark |
| orchid `#E8A6E0` | 62.3 ✅ | 104° ✅ | off-register for a clinic |
| **blush `#FFA8B6`** | **65.1** ✅ | **66°** ✅ | **chosen** |

Blush also keeps the *role* coral held — the light-flip of brick red — so the
rotation's warm/cool balance survives the swap: spring green, warm white,
blush, mint, with saffron held as the accent.

The swap made the panel both **more transparent and more legible**: the worst
tone went from 57 Lc at 0.88 opacity to 65 Lc at 0.80. Raising transparency is
gated by the weakest tone, so fix the weak tone first and the transparency
comes free.

Everything is scored with **APCA** (a perceptual contrast model, stronger than
WCAG for coloured type) against *its own* local background. Floor is 45 Lc for
display type; 60+ is strong.

### The pool gained a colour family it never had: blue

Before this pass the pool had reds (brick/rust/dark red), greens (forest/
spring green), warm neutrals (chocolate/bronze/caramel/cream/gold), one
purple (plum) and one cool green-blue (deep teal) — no genuine blue on
either half. `indigo`/`periwinkle` fill that gap, tested the same two-bar
way, against a real dark scrim (`pcos-muscle`'s derived `#100500`) and a
real light one (`pcos-sleep-cycle`'s derived `#FAE9DC`):

| Candidate | Ground | Lc (floor 62) | Min hue gap (floor 40°) | |
|---|---|---|---|---|
| **periwinkle `#B9C4FF`** | dark `#100500` | **72.5** ✅ | **92.9°** ✅ vs blush | **chosen** — the light half |
| sky `#8FD3FF` | dark `#100500` | 75.0 ✅ | 65.0° ✅ vs mint | passes both bars, rejected anyway: a second blue buys nothing periwinkle doesn't already give |
| lilac `#C0A6FF` (retest) | dark `#100500` | **61.8** ❌ | 72.3° ✅ | fails the same way the original worked example found (58.3 there) — consistent, not cherry-picked |
| gold ochre `#E8B85A` | dark `#100500` | 68.2 ✅ | **3.1°** ❌ vs warm white | reads as a duller warm white, not a new hue |
| sage `#B7D9A8` | dark `#100500` | 77.5 ✅ | **2.4°** ❌ vs spring green | same failure, green side |
| **indigo `#28285C`** | light `#FAE9DC` | **88.5** ✅ | **67.6°** ✅ vs plum | **chosen** — the dark half, same hue as periwinkle (280° vs 276°, 3.4° apart) flipped up in lightness, same relationship as every other pair in the pool |
| navy `#1A2A4A` | light `#FAE9DC` | 89.5 ✅ | 72.2° ✅ vs deep teal | passes both bars, rejected as redundant with indigo — same navy-blue family, no reason to carry two |
| olive `#4A4A1E` | light `#FAE9DC` | 79.8 ✅ | **33.9°** ❌ vs saffron | too close to the brand accent |
| aubergine `#361327` | light `#FAE9DC` | 91.8 ✅ | **0.0°** ❌ vs plum | this is just plum — confirms plum already owns that hue, no separate aubergine needed |

`indigo`/`periwinkle` are in `palette.py`'s `POOL` now, in the `indigo`
family. They do not appear in any shipped rotation's *default* preference
list yet — appending them after the four colours every dark/light rotation
has always led with keeps the four shipped clips' output byte-identical —
but a brief can bring either to the front with `style.paletteLead:
"periwinkle"` (or `"indigo"` on a light ground), which is exactly the field
`scripts/register.py`'s `paletteLead` axis proposes into.

**`plum` and `deep teal` still haven't shipped either**, despite being in the
pool since before this pass — they cleared 86–90 Lc on `pcos-sleep-cycle`'s
paper ground when the original worked example was written and nothing has
used them since. Between these two and indigo, a light-ground clip now has
five cool/purple dark-half options (forest, brick, plum, deep teal, indigo)
where it used to effectively run forest/brick every time.

## When footage is busy, the text needs its own ground

`palette.py` samples the **median** colour of a caption band. That is correct
for a plain wall and actively misleading for anything else.

On `pcos-muscle` the low band read `#B7B54C` — bright parrot-green saree. It
also contained a **black microphone** dead centre, in the same strip. The median
hid it completely, so dark type passed the contrast check against an average
that existed nowhere on screen, then vanished against the mic.

Measured on that clip: **no flat colour clears both ends.** Cream fails against
the bright saree (worst 2.2 Lc); forest and rust fail against the mic (0.6).

When a band is bimodal like that, do not hunt for a cleverer colour — **give the
text its own ground** with `layout.captionScrim`.

### The panel's top edge — derived, because both extremes are wrong

This was got wrong twice in opposite directions, so it is now measured rather
than chosen:

- **A long soft wash** (a ~420px feather starting at y=990) climbed the
  doctor's chin and shaded her face. Rejected.
- **A hard cut** (12px) read as a bar laid across the frame. Also rejected.

The honest answer is a gradual fade that still begins below her face, and how
much room that leaves is a property of the clip. So `build` measures it:

1. Find the **chin** — contiguous runs of skin down the centre column, keeping
   the *topmost* run. Her hands are skin too and sit lower than the caption
   band, so a naive skin search returns the hands; the run below the face is
   separated from it by the mic and saree.
2. The fade starts `CHIN_CLEARANCE` (40px) below that.
3. The panel is solid by the time the payload begins (`bottomZone.top + 100`).
4. `feather` is whatever distance lies between, clamped to 90–300px.

Measured on the two current clips — the same rule, two different answers:

| Clip | Chin | Fade starts | Feather | Solid by |
|---|---|---|---|---|
| `pcos-muscle` | y=1290 | y=1330 | 240px | y=1570 |
| `pcos-sleep-cycle` | y=1300 | y=1340 | 180px | y=1520 |

Set `captionScrim.feather` to `"auto"` (or omit it) to get this. Pin a number
only to override.

**Opacity**: keep it high enough that the payload clears its floor, but not so
high the panel is a solid slab — 0.88–0.90 lets a little of the footage read
through. Check the numbers after changing it; at 0.88 the muscle rotation
still scores 57–101 Lc, and the sleep rotation 67–89.

### The ground is a decision, and it is never a black box

Set `captionScrim.ground` to `"dark"` or `"light"` and the colour is **derived
from the measured wall** — pushed to one end of the lightness range while
keeping a trace of the room's own hue. A beige wall yields a warm espresso or a
soft paper, not a generic black rectangle. Pin `color` explicitly only to
override.

Polarity is the single most consequential choice in the reel, because it picks
which half of the palette can be read at all. Measured on `pcos-sleep-cycle`:

| Type | On the light ground `#FAE9DC` | On the dark ground `#100500` |
|---|---|---|
| forest `#103D2C` | **84** ✅ | 4.5 ❌ |
| plum `#361327` | **90** ✅ | 0.4 ❌ |
| spring green `#9BE564` | 10.6 ❌ | **78** ✅ |
| warm white `#FFF6E8` | 7.5 ❌ | **102** ✅ |

So choose the ground by what suits the footage — and then **alternate it
between reels**, because two clips in a row on the same polarity look like one
template. Running record:

| Clip | Ground | Type register | Question card | Lead |
|---|---|---|---|---|
| `pcos-insulin-resistance` | none (clean wall) | forest / rust, dark on light | old flat scrim | neutral |
| `pcos-walking` | none (low, on the saree) | chocolate / white | old flat scrim | tint |
| `pcos-muscle` | **dark** deep forest @0.80 | spring green / warm white / blush / mint, saffron accent | `ink` | `match` |
| `pcos-sleep-cycle` | **light** warm paper @0.82 | forest / brick, dark on light | `paper` | `neutral` |

This table is still hand-maintained as the historical record, but **which
combination comes next is no longer read off it by eye** — see "The register"
below: `scripts/register.py` reads every `brief.json` in `projects/` itself
and derives the same kind of table on demand, for whichever axis you ask
about, so it stays correct as clips accumulate instead of drifting out of
date the way a hand-written "unused combinations" list inevitably does.
Running it after `pcos-sleep-cycle` (`python3 scripts/register.py
<next-slug>`) proposes:

```
groundPolarity    -> none      last 2 clip(s) ran `dark`, `light` -> this one takes `none`
questionPreset    -> forest    last 2 clip(s) ran `ink`, `paper` -> this one takes `forest`
leadStyle         -> tint      last 2 clip(s) ran `match`, `neutral` -> this one takes `tint`
paletteLead       -> brick     last 2 clip(s) ran `forest` -> this one takes `brick`
```

— which is the same answer a person reading the old table by hand would give
(`forest` or `white` next, `tint` is the only lead style that hasn't run, no
scrim inverts the last two dark/light clips), now produced from the briefs
themselves rather than maintained in prose. `paletteLead`'s reading is the
one honest weak spot: no brief records its rotation's lead colour as data,
only as free prose in `style.accent`, so the selector greps that string for
a known name and can mismatch — it read `pcos-muscle`'s "vivid rotation
**on the forest scrim**" as if `forest` had shipped as a *payload* colour,
when `forest` there names the scrim's own ground. Worth a real field
(`style.paletteLead`, already wired as an override in `build_captions.py`)
rather than a smarter parser.

Once a scrim is on:

- `build` re-derives the rotation against the *scrim*, not the footage
- the outline comes off entirely (`stroke.color: null`) — it is no longer
  carrying anything
- the lead line takes the **same colour** as the payload, so only one tone is on
  screen at a time
- the text can go bigger and lower, because placement is no longer fighting the
  background

## Backgrounds and shading

Today `captionScrim` is one flat colour with a feathered top edge (the panel
geometry above), and the question card has two textures, `vignette` and
`grain`. That is the whole shading system. Extending it honestly means
saying what is actually landed and what is only specified, because a
treatment that varies colour *through* the payload's own footprint — not
just the panel's leading edge — needs the same worst-case discipline the
bimodal-band bug taught: score the weakest point the type ever sits on, not
the average.

**What's real today, and why its "worst case" is trivial.** The scrim's
feather is already a real gradient — alpha 0 at `captionScrim.top` ramping
to fully opaque by `top + feather`. Its worst-case Lc equals its *only* Lc,
because `build_captions.py` guarantees the panel is fully solid by
`bottomZone.top + 100`, strictly before any payload begins (see "The panel's
top edge" above) — the type never sits anywhere but the flat, fully-opaque
end of that gradient. The numbers already reported everywhere in this
document (57–101 Lc on `pcos-muscle`, 67–89 on `pcos-sleep-cycle`) *are* the
worst case, because there is no variation left to be caught unawares by.
The same logic clears the question card's `vignette`/`grain` textures and a
frame-wide vignette or duotone wash **outside** the caption panel: as long
as they stop at the panel's edge, they never touch what the type sits on, so
they cost nothing to add and need no APCA number at all.

**What's specified but not wired into `DoctorVideo.tsx` yet** — a treatment
that puts variation *through* the payload's own box, which is the one case
that actually needs the worst-case check requested here. Worked example: a
radial vignette centred behind the payload, opacity falling from the
panel's normal value at centre to a weaker value at the text block's own
edge, measured against the darkest/lightest real patch of footage this clip
actually has (not an assumed value):

| Ground | Footage patch (measured) | Payload | Centre Lc | Edge Lc (worst case) |
|---|---|---|---|---|
| `pcos-muscle`-style dark, `#100500`@0.80 | `#B7B54C` saree | warm white `#FFF6E8` | 98.9 | **86.1** at edge alpha 0.55 |
| `pcos-muscle`-style dark, `#100500`@0.80 | `#B7B54C` saree | spring green `#9BE564` | 75.4 | **62.5** at edge alpha 0.55 |
| `pcos-sleep-cycle`-style light, `#FAE9DC`@0.82 | `#7A6A52` shadow | forest `#103D2C` | 72.9 | **54.1** at edge alpha 0.55 |

All three clear the 45 Lc display floor with room to spare at a 0.55 edge
opacity; the weakest of the three (spring green, the pool's palest dark-half
member) crosses the floor only once edge opacity drops below roughly
**0.30–0.32** — a real number to hold a future implementation to, not a
guess. This is measurement and arithmetic only: `DoctorVideo.tsx`'s
`CaptionScrim` renders a single flat-colour linear gradient today and does
not accept a radial shape, a second colour (duotone), or a per-payload
vignette, and that file is outside this task's ownership. Nothing above is
claimed as shipped or visually confirmed — it is the budget the next
render-side change should be measured against, in the same units as
everything else in this document.

## The lead line: one colour, or two — but rotate

Set `style.leadStyle`; a beat can override it.

| `leadStyle` | Lead | Payload | When |
|---|---|---|---|
| `match` | same tone as the payload | rotation colour | quiet; safe on a busy ground |
| `neutral` | a deep or pale **neutral** | rotation colour | the two-colour pairing |
| `tint` | a nearby tint of the payload | rotation colour | default off a scrim |

The rule for two colours is **neutral against colour** — not colour against
colour. Compare:

| | Lead | Payload | Reads as |
|---|---|---|---|
| `pcos-insulin-resistance` | dark neutral brown | forest green | ✅ a pair |
| `pcos-insulin-resistance` | dark neutral brown | rust | ✅ a pair |
| early `pcos-muscle` | `#584438` brown | `#3A2416` chocolate | ❌ mud |
| early `pcos-muscle` | `#FFE9CC` cream | `#FFB01F` amber | ❌ mud |

Two mid-tone colours of similar weight muddy each other. A neutral against a
saturated tone gives hierarchy: the eye reads the payload first.

**Alternate between reels.** `pcos-muscle` runs `match`, `pcos-sleep-cycle`
runs `neutral`. Doing either one every time is what makes a feed look
automated.

## Shadows follow the glyph, not the scrim

A light glyph on a dark panel wants a dark lift. Give a *dark* glyph on a
*light* panel that same treatment and every letter gets a black smear round it
— which shipped once, and looked like a deliberate ugly choice rather than the
bug it was. Dark-on-light gets `none`: the ground is uniform and the contrast
is 80+ Lc, so nothing is holding the letterform up but the fill, and nothing
needs to.

## No outline unless it is earning its place

A black stroke on every glyph flattens colour and cheapens the frame. It exists
to rescue type on a background that cannot be controlled. If you have put a
scrim down, the background *is* controlled — take the stroke off.

## No decoration that carries no information

The thin ladder rule under the payload was removed. If a line, box or flourish
is not telling the viewer something, it is subtracting.

## Size

Payload size is driven by the **longest line**, not by the cap — `avail /
(longest_chars × advanceEm)`. Raising `bottomMaxMultiLine` alone does nothing
for a long line. To get bigger type, break the lines shorter or reduce
`paddingX`. Keep the last line clear of roughly the bottom 250px, where the
platform UI sits.

## The question card

The opening question owns the whole screen, so it is where a reel can change
register completely. Eight grounds ship now, each with its own type colours
and a texture so the panel is never a flat wash:

| `question.preset` | Ground | Type | Lead Lc | Key Lc |
|---|---|---|---|---|
| `ink` | dense near-black `#0C0A07`, vignette | warm white + saffron | — | — |
| `forest` | the Kyros green `#0B2119`, vignette | cream + amber | — | — |
| `paper` | light card `#F4ECDF`, grain | dark brown + forest | — | — |
| `white` | bone white `#FBF8F3`, grain | warm grey + rust | — | — |
| `plum` | deep aubergine `#2A0F22`, vignette | warm white + blush | **101.3** | **67.4** |
| `teal` | deep teal `#0A2B28`, vignette | cream + saffron | **91.5** | **65.5** |
| `clay` | warm terracotta `#E0A07A`, grain | espresso + forest | **57.9** | **52.0** |
| `bone` | bone/sand `#EDE3D0`, grain | warm grey + brick | **74.3** | **65.7** |

(The first four ship un-remeasured from before this pass; the Lc columns are
filled in only for the four added here — every one clears the 45 Lc display
floor, `clay` by the narrowest margin because a mid-light ground has less
lightness range to spend than a near-black or near-white one.)

`clay` is the register the first four didn't have at all: `ink`/`forest` are
both near-black, `paper`/`white` both near-white, so there was no MID-LIGHT
opening. A first pass at `#C97B56` only cleared 41.9 Lc best-case (below the
45 floor) — lightening to `#E0A07A` was what made espresso/forest actually
legible; a mid-light ground has less room to push contrast than a near-black
or near-white one does, which is the whole reason it was missing.

`bone` deliberately does not just repeat `paper`/`white` at a slightly
different lightness — it takes `brick` as its key where `paper` takes
`forest` and `white` takes `rust`, so the three light cards are
distinguishable by more than a lightness percentage.

**Rotate them. Do not repeat the last two reels.** A run of identical openings
is what makes a feed look automated. `scripts/register.py` now proposes the
next one automatically — see "The register" below.

**Keep the card opaque** — 0.985+. At 0.94 it reads as a transparent grey wash
with the doctor ghosting through, which looks like a mistake rather than a
design. The card's job is to make her disappear.

Override any part with an explicit `question.card` block.

## The register: no axis repeats by accident

"Don't repeat the last two reels" used to mean a person reading the running
record table above before writing a new brief. `scripts/register.py` encodes
it: it reads every `projects/*/brief.json`, works out what each already-shot
clip's register was per axis, and proposes the next clip's register with the
reason, printed by `prep` (see below for why `prep` and not `build`).

**The schema** is one dict, `AXES`, name -> ordered option list. Adding an
axis — a reveal mechanic or type pairing another module owns, say — means
appending one entry there, nothing else changes:

| Axis | Kind | Options | Owner |
|---|---|---|---|
| `groundPolarity` | chosen | `none`, `light`, `dark` | `build_captions.py` / `palette.py` |
| `questionPreset` | chosen | `ink`, `forest`, `paper`, `white`, `plum`, `teal`, `clay`, `bone` | `build_captions.py` (`HOOK_CARDS`) |
| `leadStyle` | chosen | `match`, `neutral`, `tint` | `build_captions.py` |
| `paletteLead` | chosen | the pool's named hues (`forest`, `brick`, `plum`, `indigo`, `spring green`, `periwinkle`, …) | `palette.py` |
| `shadingTreatment` | chosen | `flat` (the only kind that renders today — see "Backgrounds and shading") | `build_captions.py` |
| `plateAnchorStyle` | measured | `low`, `high` | `solve_doctor_plate()` |
| `markAnchorStyle` | measured | `upper-right`, `upper-left` | `solve_mark_anchor()` |
| `typePairing` | chosen | read live from `scripts/typography.py:PAIRINGS` | `scripts/typography.py` |
| `revealStyle` | chosen | read live from `scripts/motion.py:REVEAL_STYLES`, minus `legacyMaskWipe` | `scripts/motion.py` |

**Chosen vs. measured** matters. A *chosen* axis is a creative decision with
room to alternate, so the selector proposes an option neither of the last
two clips used. A *measured* axis is an output of a hazard-aware solver — the
plate and mark anchors are picked by what the footage will and won't allow,
per clip, every time. Forcing "not what you did last time" onto a safety
measurement is backwards: the solver already answers to the footage on every
clip, never to a rotation, so measured axes are reported from history for
visibility only and never overridden. The `typePairing`/`revealStyle` rows
are the pattern for a module this task doesn't own registering its own
axis: `register.py` imports `typography.PAIRINGS`/`motion.REVEAL_STYLES`
directly and reads their keys, so populating those dicts *is* registering
the axis — no change needed here when they do.

**A brief's own pin always wins outright** — `register.py` only fills in
what a brief leaves unset. Proposed for the clip after `pcos-sleep-cycle`,
today:

```
groundPolarity    -> none      last 2 clip(s) ran `dark`, `light` -> this one takes `none`
questionPreset    -> forest    last 2 clip(s) ran `ink`, `paper` -> this one takes `forest`
leadStyle         -> tint      last 2 clip(s) ran `match`, `neutral` -> this one takes `tint`
paletteLead       -> brick     last 2 clip(s) ran `forest` -> this one takes `brick`  (see the caveat above)
shadingTreatment  -> flat      every registered option has run in the last 2 clips; `flat` is the one used longest ago
plateAnchorStyle  -> measured by the solver, not chosen
markAnchorStyle   -> measured by the solver, not chosen
typePairing       -> warmEditorial  last 2 clip(s) ran `heritage` -> this one takes `warmEditorial`
revealStyle       -> maskWipeFast  no clip has set this axis yet
```

`typePairing` reads `heritage` on all four shipped clips even though none of
them set the key. They record the pairing as prose — every one says
`"PlayfairDisplay Italic / Anton"` — and that is precisely what `heritage`
names now that the pairing is resolved by key. Discarding that as
unparseable made the selector report "never run" and propose `heritage` for
the fifth clip: the one pairing that has been on screen four reels running,
which is the exact repetition this axis exists to prevent. An absent key is
not an absent choice — the hardcoded default rendered, so it counts as a
run.

## Turning the register into a build

Three brief keys reach the new engines, and every one of them is opt-in —
absent, no new code executes and the clip builds exactly as it did before.
That is what lets four shipped reels and a fifth experimental one share a
pipeline:

```json
{ "style": { "typePairing": "auto",          // or a name from typography.PAIRINGS
             "autoMotion": true,             // reveals chosen from work/audio.json
             "revealStyle": "punchPop" } }   // or pin one for the whole clip
```

Precedence for a reveal runs beat pin -> clip pin -> `autoMotion` -> nothing,
and "nothing" means no `reveal` key is written at all, which `DoctorVideo.tsx`
resolves to the original mask wipe.

The pairing is applied **before** the payload is sized, not after. `key_size`
measures the payload against the actual face's metrics, so a pairing swapped
in later would size Barlow Condensed's text using Anton's widths and overflow
the band. Verified on `pcos-sleep-cycle`: the same three payloads size to
131/150/157px under `warmEditorial` against 116/133/139 under `heritage`.

`autoMotion` also turns on the boundary check, which is where the pipeline
started answering back:

```
chunk boundaries that do NOT fall in a measured pause:
 beat 2->3: boundary gap 0.00s is inside continuous speech (pause threshold
            0.41s, need >= 0.25s) — "properly" runs straight into "in"
```

Twelve of the twenty-six boundaries across the four shipped reels are like
this. A break is written by reading the transcript, where the sentence end
looks obvious on the page; she did not stop there. The check does not move
the boundary — it says so, and a person decides.

**Wired into `prep`, not `build`.** By the time `build` runs, `brief.json`'s
`question`/`style` choices are already written — printing a proposal at that
point would only report a decision already made. `prep` runs before
"Decision two — the style" (Part 1, step 5), which is exactly when a
proposal is useful rather than academic.

**History ordering** comes from each `brief.json`'s file mtime (oldest
first, ties broken by slug name) — nothing in a brief records when it
shipped, and this is a real proxy for "which reel came first" as long as
project folders are never bulk-copied. It reproduces this document's own
running-record order (insulin-resistance, walking, muscle, sleep-cycle) on
this repo today.

---

# Part 3 — how the folder is put together

## Every clip, the commands

```bash
python3 scripts/reels.py library _              who is on file
python3 scripts/reels.py new    <slug>          create the project
python3 scripts/reels.py prep   <slug>          probe + transcribe + measure + scan + palette + register
python3 scripts/reels.py visuals <slug>         optional: supporting visuals — plan / --approve / --generate / --preview
python3 scripts/reels.py build  <slug>          brief -> captions_data.json
python3 scripts/reels.py stage  <slug>          swap this clip into the studio
python3 scripts/reels.py render <slug> [kyros|partner]   render a cut (or both)
python3 scripts/reels.py verify <slug>          check them with numbers
python3 scripts/reels.py push   <slug|all>      back up clip, AI files, audio, cuts to R2
python3 scripts/reels.py pull   <slug|all>      bring them back — a fresh clone has no media
```

Git holds code, briefs and measurements; clips, AI files, audio and renders are
ignored and live in the R2 bucket instead (`docs/MEDIA.md`). Push adds and
never deletes; pull fills in what's missing and never overwrites.

Every `render` keeps the previous cut in `out/versions/` as `…-vN.mp4`, so a new
version never destroys the one you were comparing against.

## The library — the only thing that goes in a project is the clip

Doctors recur. Dr. Bharani will front many clips, and Aster Ramesh pairs with
her each time. So plates and logos live in `brand/` once, not in every project:

```
brand/doctors/bharani-bellam/
   plate.png        her lower-third artwork
   doctor.json      name, title, registration number, usual partner clinic

brand/partners/aster-ramesh/
   logo.png         their mark
   partner.json     end-card style, hold time, background, logo size
```

A brief then just names them:

```json
{ "doctor": "bharani-bellam", "partner": null }
```

`partner: null` uses that doctor's `defaultPartner`. Set it explicitly only when
a clip pairs differently from usual.

**So `projects/<slug>/inbox/` contains one file: the clip.**

**Adding a new doctor or clinic** — copy an existing folder and edit the JSON:

```bash
cp -r brand/doctors/bharani-bellam brand/doctors/krishna-rao
cp -r brand/partners/aster-ramesh  brand/partners/krishna-clinic
```

If the Kyros mark or outro is redesigned, replace the file in `brand/kyros/` and
every future clip picks it up.

## Why staging exists

The studio is one Remotion project reused for every clip — `npm install` is
~460 MB and you only want to do it once. `stage` swaps the current clip's
footage, audio, plate, logos and caption data into it, then renders. Output
filenames carry the slug, so nothing overwrites the previous clip.

**The studio holds one clip at a time.** `stage` overwrites the previous clip's
assets. Finished renders are safe in each project's `out/`, but re-rendering an
older clip means staging it again first.

## Reading the clip — placement follows the footage

A raw clip is not always a blank canvas. Some arrive with graphics already
burned in by the doctor's team, covering part of the frame at certain times. The
reel's own captions, title card and logo must land in the space the footage
leaves free, and that free space moves as the clip plays.

`prep` runs `scan_overlays.py`, which maps when the **top** and **bottom**
caption bands are covered. `build` reads that map and places everything
automatically — captions big at the top over a bare wall, dropping low when a
graphic holds the top, with the title card timed into a blank-top window.

It is measured, not eyeballed, for the same reason colour is: a graphic that
fades in over a few frames is exactly where a person guesses the boundary wrong.

## The logo animation

The supplied mark animates its saffron underline, authored `infinite alternate`,
so it pulses continuously. If it ever competes with the captions, set
`layout.logo.loop: false` in a brief and it plays once and holds.

## Keeping it from going stale

`brief.json` records every decision, including the style and the question
preset. Before starting a new clip, read the last two or three briefs: they say
what was already settled, so you only get asked about what is genuinely new —
and they show which combination to avoid repeating. See `references/styles.md`
in the `kyros-doctor-reels` skill.

## What makes it go faster

- **Send timing notes with the clip** if you have them. Skips a round trip.
- **Say if anything is unusual** — different room, she is sitting lower, harsher
  light. The scene is re-measured every clip regardless, but knowing to look
  closely saves a correction.
- **Add a new doctor to the library the first time they appear.** Every clip
  after that needs only the video file.
# kyros-video-editing
# kyros-video-editing
# kyros-video-editing
# kyros-video-editing
