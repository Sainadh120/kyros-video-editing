# Test cases — and the reel behind each one

Run them:

```bash
python3 scripts/reels.py check _        # ~1.5s, no render needed
```

Nothing here is a test written to have tests. Every case is a reel that was
thrown away, a frame that shipped wrong, or a bug found while building the
thing that was supposed to prevent it. The suite exists because the expensive
mistakes on this pipeline all shared one property: **they passed inspection.**
`verify` reported green on a cut whose plate covered a caption. A contrast
check passed against a median colour that existed nowhere on screen. A render
succeeded from data three edits old. None of those announce themselves.

The rule is therefore: **if a mistake was worth catching once, it gets a test
before the next video, not after.**

---

## What each file covers

| File | Rules | Cases |
|---|---|---|
| `tests/test_colour.py` | polarity, the two bars, lead legibility, cards, stroke | 32 |
| `tests/test_placement.py` | plate, mark, rect primitive, payload sizing, safe area | 12 |
| `tests/test_motion_type_audio.py` | reveal budgets, when not to animate, faces, voice | 29 |
| `tests/test_register.py` | non-repetition, legacy history, pins, extensibility | 11 |
| `tests/test_delivery.py` | staging, renders, provenance, compliance, opt-in | 26 + 5 skipped |
| `tests/test_visuals.py` | supporting visuals: off-by-default, timing budgets, cache, approval + lint, failure, metadata, placement, staging, verify, toolkit command, graphics | 104 + 1 slow |
| `tests/test_media.py` | media out of git: what is backed up, push only adds, pull never overwrites, real rclone round trip, `.gitignore` | 37 |

---

## Colour

**Polarity.** `pcos-muscle`. Forest green measures 61 Lc on the pale wall and
**3.9** on the dark scrim. A colour is not legible on its own, only against
what is behind it. Made twice, the most expensive mistake on the pipeline. The
tests assert both directions — the dark half must *fail* on a dark ground, or
the rule is not being enforced, it is being hoped for.

**Two bars, not one.** `pcos-muscle`. Coral was the rotation's weak link at 57
Lc. Apricot cleared contrast at 67.7 — and sat 29° from the saffron accent, so
the rotation read as one colour repeating. A tone must clear APCA ≥62 Lc *and*
≥40° of hue from its neighbours and the accent. The rejected candidates
(apricot, flamingo, lilac) are tested as *still rejected*, so a future pool
change cannot quietly readmit them.

**The lead line.** `pcos-muscle`. The lead was chosen for its distance from the
payload, landed on the parrot-green saree, and vanished. Distance from the
payload is not legibility against the ground.

**The question card.** It is the first thing the viewer sees; type that fails
against its own card is a full-screen mistake. Also: opacity ≥0.98, because at
0.94 the doctor ghosts through and it reads as an error rather than a choice.

**The stroke.** A black stroke on every glyph flattens colour. It exists to
rescue type on a background that cannot be controlled — and a scrim *is* the
background being controlled. Both scrimmed clips correctly carry
`stroke.color: null`.

**Scope note.** These are asserted against `CURRENT_GEN` only.
`pcos-insulin-resistance` and `pcos-walking` were built on 27 Aug and never
rebuilt; their work files predate the lead contrast floor, the card presets,
`listIndex`, `logoHideWindows` and the stroke block. Asserting today's rules
against them tests history against a rule that did not exist yet. Their
staleness is recorded in `test_delivery.py` instead.

## Placement

**The plate over the caption.** `pcos-sleep-cycle`, and it **shipped**. The
plate appears at f233 and holds 57 frames; the top caption opens at f263. They
overlap for 27 frames, both in the top zone. A frame pulled at 9.5s shows the
italic lead rendering underneath the plate pill. `verify` passed it.

The old logic reasoned about zone *names*: it pushed the plate up to dodge a
bottom-zone caption and walked into a top-zone one, with nothing checking
rectangles. The fix applies from the next video on — the clip is not being
re-rendered — so the test is a **canary**: it asserts the old data *still shows
the fault*, proving the detector sees it. If it ever starts passing, either the
file was rebuilt or the detector went blind.

**The rect primitive.** A wrong operator in `rect_overlap` would make every
placement test above pass while checking nothing. Touching edges must not
count; containment must; padding must widen the test.

**The mark and the median trap.** `pcos-sleep-cycle` becomes a full-screen
infographic at 13.2s and the mark landed on the illustration, while the
top-band scan reported nothing — by then the whole frame was graphic. The
mark's own rectangle has to be measured. And the reference frame for that
measurement cannot be the clip median: on a clip that is graphic for more than
half its length the median *is* the graphic, so every clean frame reads as
covered. That bug flagged an entire clip. Tested from both ends — the graphic
clip must hide `13.1–27.0s`, and `pcos-muscle` must hide **nothing**.

**Size.** Payload size follows the longest line, not the cap. Raising
`bottomMaxMultiLine` alone does nothing for a long line. And the last line
stays clear of the bottom 250px where the platform's own UI sits.

## Motion

**The illegible intermediate state.** `pcos-sleep-cycle` at 10.5s: the payload
"UNDER CONTROL" caught mid-wipe, rendering as a flat grey half-drawn line. In
motion it passes; on a still — a paused reel, a thumbnail — it reads as a
rendering fault. The legacy wipe measures **13 illegible frames** (0.43s).
Budget for anything choosable: **2 frames**. `legacyMaskWipe` is tested as
exceeding the budget, because it is the thing being replaced, and
`choose_reveal` is tested as never selecting it.

**When *not* to animate.** The side that gets skipped. A caption that appears
is not automatically a caption that should animate — the same logic that says a
beat under a burned-in graphic wants no caption says a beat under a *moving*
graphic wants no motion. Refusals: sub-second beats (animating is just
flicker), ≥60% graphic coverage, heavy gesture, and three animated beats in a
row, which is a template rather than a style. Every refusal must state a
reason, so the build output explains itself.

**Displacement.** She gestures constantly. A reveal that travels competes with
her; nothing may displace more than 12px.

## Type

Anton is condensed. A pairing that swaps in a wider payload face and is not
re-measured overflows the band — **silently**, because nothing renders during
build. Every pairing is measured in both zones against the worst-case shipped
payloads (`MAINTAINING MUSCLE`, `TREATMENT OF PCOS`) and must keep a positive
margin. Lead and payload must always be different faces. `heritage` must stay
the fallback from both directions — an absent key and an empty rotation history
have to resolve to the same thing, or a brief that opts in and one that does
not stop matching.

## Audio

Nothing listened to the audio for four reels. Captions were timed off forced
alignment alone, so every beat got the same flat treatment however she said it.

The pause threshold is **derived per clip** — the four takes range 0.22s to
0.83s, so one pinned number could not serve them. Same reasoning as the
measured wall: a constant is a guess that happened to suit one clip.

**12 of 26 boundaries** across the four shipped reels land at a 0.00s gap —
inside continuous speech. A break is written by reading the transcript, where
the sentence end looks obvious on the page; she did not stop there. The check
reports; it does not move the boundary. A person decides.

## The register

**Legacy prose counts as a choice.** The selector proposed `heritage` for the
fifth clip — the one pairing that had been on screen four reels running, which
is the exact repetition the axis exists to prevent. All four briefs record the
pairing as prose (`"PlayfairDisplay Italic / Anton"`), which is precisely what
`heritage` names now that pairings resolve by key. Discarding it as unparseable
read as "never run". **An absent key is not an absent choice: the hardcoded
default rendered.**

**Measured axes are never rotated.** Forcing "not what you did last time" onto
a safety measurement is backwards. The plate and mark answer to the footage on
every clip.

**Axes are data, not code.** The type and reveal axes are registered by modules
the selector knows nothing about; the test asserts the options come from those
modules live, so a new axis stays a data addition.

## Delivery

**Staging.** `build` writes `work/captions_data.json`; `stage` copies it into
the studio; `render` reads only what the studio holds. Skip `stage` and the
render succeeds, `verify` passes, and every change is silently absent — a
failure with no symptom.

For four reels the only guard was remembering. Now `stage` writes
`studio/src/.staged.json` (slug + digest) and `render` refuses to run when that
receipt does not match the build in front of it, then stamps each cut with
`<slug>-<cut>.render.json`. The provenance tests **skip** on the four existing
reels, which were rendered before stamping existed, and engage from the next
render on. A skip here means "not yet answerable", not "fine".

**Compliance.** Schedule J applies to most Kyros verticals. Two rules, because
one would be wrong:

- *Hard*: a cure/reverse/guarantee word may **never** be set as a payload. She
  is the clinical authority on her own words and they are not quietly reworded
  — but a cure claim at 150px is the pipeline making the claim, not her.
- *Soft*: such a word in the small italic lead must be **declared** in the
  brief's `openFlags`. `pcos-muscle` ("it almost cures the pathophysiology")
  and `pcos-walking` ("reverse the pathophysiology") both carry the word in the
  lead only, both declared, with the reasoning recorded. An undeclared one
  means nobody looked.

**Opt-in stays opt-in.** Four shipped reels and a fifth experimental one share
one pipeline. No shipped clip may gain a `reveal` key or switch its faces, or
the older clips stop being reproducible.

---

## Supporting visuals

`tests/test_visuals.py`. The generator is faked with ffmpeg writing real
media, so every path — cache, metadata, failure, verify — runs without Modal.

**Off means off.** Six shipped reels share this pipeline. A brief without an
enabled `visuals` block never reaches the visuals engine, the solvers behave
identically with `extra_hazards=None` and `[]`, and the slow case
(`KYROS_SLOW=1`) rebuilds every project against
`tests/fixtures/rebuild_md5.json`. That case **skips** when a project's source
clip is missing — learned the day it was written: every inbox clip vanished
mid-session, the chin, mark and plate measurements silently came back empty,
and three projects "changed" for that reason alone. A missing take proves
nothing about the code.

**She stays the reel.** Cutaway ≤ 2.5s; bubble and inset ≤ 6s; nothing under
1.2s (a flash); 1.5s of her full-frame between two full-frame visuals; she is
full-frame for at least half the answer; nothing covers the question except a
declared backdrop; a beat already carried by a burned-in graphic (≥ 75%) gets
no visual — the same bar as a caption skip.

**Hazards, as rectangles.** An inset card is a burned-in graphic to the
captions (that beat drops low). The plate never appears while she is in the
bubble or cut away — it names her — and an inset only blocks it where their
rectangles meet. The mark steps aside for a card under it. The bubble never
sits on the mark, a live caption, the like/comment column, or outside the safe
area, and it frames her face.

**A caption over a picture.** `pcos-best-exercise`, 20.7s, first render: a
light low caption fading out and a dark top caption were pooled into one
legibility decision; the light one won, and a dark veil covered the frame from
y=208 to y=1640 — burying the dark "8–10,000 STEPS" it was meant to rescue and
dimming her bubble. Now each caption gets its own soft oval ground, measured
under its own words (not the whole zone, which on the meditation still judged
the caption against a head it never touched), never spanning both zones, and
none for a caption only brushing the visual's fade. The mark steps aside only
when the picture under it measures below 45 Lc — it did on the dark trees,
not on the pale meditation room.

**A rejected picture never stands in.** The first gym still (an impossible
plank-lunge, "15" printed on the dumbbell) was rejected and re-prompted.
Until the new one exists, the build shows footage — the manifest's last
picture for that id only counts if its request hash matches the current
prompt.

**The cache.** Same request, one GPU call, across clips. A changed prompt is a
new file beside the old one; moving a visual to another beat or changing its
camera move never regenerates; nothing is overwritten; generated video
carries no soundtrack (her voice is the only audio).

**Approval and lint.** Only approved visuals generate. `--approve all` leaves
anatomy/medicine for an explicit yes; before/after, reports/scans, patients,
testimonials, clinicians and claim words can never be approved; editing an
approved prompt needs approval again. A graphic may only show numbers she
spoke on that beat ("two or three" = 2 and 3; "10 ,000" = 10000).

**Failure is safe.** A failure is recorded with its reason, retried only when
asked, leaves no file, and the build ships that beat as footage. A missing
Modal endpoint fails fast and names the variable. The toolkit is always called
with `--cloud modal`; there is no other provider to fall back to.

---

## Media

**The reel behind it.** On 2026-09-11 every inbox clip was deleted from disk by
another session; git was the only copy. The same day the repo's history stood
at 2.6 GB, with source clips up to 365 MB — GitHub refuses anything over
100 MB, so nothing could be pushed.

**Git holds no media.** Clips, AI files, audio, previews and the studio's
staged copies are ignored; `brand/` artwork, briefs, measurements and AI
sidecars are not. A test fails if any media outside `brand/` is tracked.

**Push only adds; pull never overwrites.** Push is `rclone copy` followed by a
file-by-file `rclone check` — never `sync`, never a delete — so a clip deleted
on disk survives in the bucket. Pull is `copy --ignore-existing`, so a fresh
re-render is never replaced by the older backed-up cut. Previews, drafts in
`out/versions/` and `--overlays` layers stay local. The round trip is tested
against a real rclone with a folder standing in for the bucket.

---

## Adding a case

When something goes wrong on a video, before fixing it:

1. Write the test that fails. Name it for the symptom, not the mechanism.
2. Put the reel and the measured number in the docstring — `3.9 Lc`, `27
   frames`, `13 illegible frames`. A number is arguable; an adjective is not.
3. If the bad output already shipped and is not being re-rendered, make it a
   **canary** against the shipped data, as the plate case is.
4. Then fix it, and add the row to the table above.
