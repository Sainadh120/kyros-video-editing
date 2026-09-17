---
name: kyros-doctor-reels
description: Turns a raw vertical doctor Q&A clip into finished captioned reels for Instagram and YouTube — word-aligned transcription, kinetic captions burned over the footage, doctor lower-third, and a branded end card. Produces both the Kyros cut and a partner-clinic cut of the same edit. Use this skill whenever Niranjan supplies a doctor video clip, mentions captions, subtitles, text animation, reels, shorts, a doctor's lower-third or name plate, a partner clinic cut, supporting visuals / b-roll / AI images or video / number or text animation over a doctor clip, or asks to "make a reel" / "add text to this video" / "caption this clip" / "add visuals" — even if he doesn't name the skill. Also use it when revising a reel produced earlier.
sequence: production skill — read kyros-clinical-compliance BEFORE publishing anything this skill makes
---

# Kyros Doctor Reels

Niranjan sends a vertical clip of a doctor answering one question, every few
days. This turns it into two finished reels: the Kyros cut, and a cut branded
for the doctor's own clinic — the trade that gets Kyros the content.

**The clips are near-identical in shape. The videos must not be.** If every
reel looks the same, the feed reads as one boring template and people scroll.
Varying the treatment is a requirement of the job, not a flourish. See
`references/styles.md`.

## The one rule that matters most

**Ask before you build. Confirm even what you were already given.**

Niranjan would rather answer six questions up front than watch a render come
back with the emphasis on the wrong word. A wrong assumption costs a full
re-render and a round trip; a question costs thirty seconds. When something is
missing, ask. When something is present, read it back and have him confirm it.

This is the skill's whole reason to exist. Everything below is downstream of it.

## Where the work happens

Everything lives in `~/Downloads/Personal/Kyros_Project/Reels`, which already
has the Remotion studio installed and the shared Kyros assets in place. Read
its `README.md` — it's the operating manual.

```
Reels/
  brand/kyros/     mark + outro, same on every clip
  brand/doctors/   one folder per doctor: plate + details + usual partner
  brand/partners/  one folder per clinic: logo + end-card settings
  studio/          the Remotion project, installed once and reused
  scripts/         reels.py and the pipeline
  projects/        one folder per clip — inbox holds ONLY the clip
```

Doctors and clinics recur, so their artwork is stored once and referenced by id.
Check what exists before asking Niranjan for files he has already given:

```bash
python3 scripts/reels.py library _
```

Do not create a new Remotion project per clip. `npm install` is ~460 MB and the
studio is designed to be staged into.

## Step 1 — Intake, before touching the clip

```bash
python3 scripts/reels.py new <slug>
```

That creates the folder and writes a `brief.json` template. **The only file he
drops into `inbox/` is the clip** — the doctor's plate, the partner's logo and
the Kyros assets all resolve from the library.

If the doctor or clinic is new, ask for their artwork and add a library folder
so the next clip needs nothing. If they are already on file, don't ask again.

Then work through `references/intake.md`: the doctor, the partner clinic, the
timing and placement spec, the style, which outputs he wants. Fill the answers
into `brief.json` as you collect them. Don't start transcribing until they're in,
or he's said to proceed without something.

`brief.json` is what makes this improve over time. Record every answer, including
corrections. Before a new clip, read the last two or three briefs — they say what
was already settled, so you ask only about what's genuinely new, and they show
which style combination not to repeat.

## Step 2 — Probe and align

```bash
python3 scripts/reels.py prep <slug>
```

Word-level timestamps come from faster-whisper (`small.en`, int8), which tries
whisperx first and falls back on its own. Every timestamp becomes a frame:
`frame = round(seconds * fps)`.

**Read the transcript before going further.** Two things routinely differ from
what Niranjan said the clip contains: the actual words, and the actual length.
A clip has arrived before that was a completely different Q&A from the one
described. Quote the transcript back to him.

## Step 3 — Measure the footage; never guess colour

`prep` runs this too, and writes `work/scene.json` with a suggested palette.

Different doctors, different rooms. Niranjan keeps framing similar where he
can, but it moves, so measure every time.

This reports the background colour where the text will sit, WCAG contrast for
each candidate palette, and where the subject's head starts.

Why this exists: on one shoot the wall measured `#E9C39F` — light. The obvious
choice, white type like every reference reel uses, scored **1.64:1** and would
have been unreadable. Dark type scored 7.4:1. Taste would have got it wrong;
the meter got it right. Take the palette the script says passes.

If a measurement looks unusual — the head much higher or lower than usual, a
background too busy for any palette — say so and ask, rather than shipping
something that technically passes.

## Step 4 — Cut the script into chunks

This is the editorial decision and where the reel is won or lost. Full detail
in `references/pipeline.md`.

Two to four words on screen at a time, in two registers: a quiet **lead** line,
and the **payload** — the words that carry the medical point, set large.

```
that is around  ->  65–70%
So that's why   ->  ONE MUST / ADDRESS THIS
```

Niranjan often supplies the timing and placement himself — which second range,
top or bottom. Use exactly what he gives. **If he hasn't given it for a
section, ask rather than inventing it.** Record what he says in `brief.json`.

Propose the full chunk breakdown as plain text and wait for his OK before
rendering. He can read it in twenty seconds; a wrong render costs minutes.

## Step 4b — Propose supporting visuals, in the same message

The doctor is the reel. A supporting visual shows **exactly what she is
saying on that beat**, as realistically as possible — never what she didn't
say. Full rules, research and prompt recipes: `references/visuals.md`. Read
it before proposing.

The question opens on pictures of what it asks about — never a blank card —
and her face arrives with her answer. Then, per beat, take the rung that shows
it: **nothing** (her face — nuance, her own advice, the close) →
**text/number animation** (her number, frequency or list, drawn by Remotion,
free) → **AI still with a slow camera move** (FLUX.2) → **AI video** (LTX-2,
wherever motion adds something). Match the count to her words: one thing named
→ one visual; a list named → every item, each on its own word, building up to
all of them on screen (`listBuild`). HD generation, modest wide framing. She
stays full-frame for at least half the answer.

Write them into `brief.json` → `visuals.beats` with `status: "proposed"`, then:

```bash
python3 scripts/reels.py visuals <slug>      # the plan, her words beside each prompt, cost
```

Send that plan with the chunking — one approval covers both. Only a visual the
lint marks `review` (anatomy, medicine) needs its own explicit yes.

```bash
python3 scripts/reels.py visuals <slug> --approve all     # or v1,v3 ; --reject v2
python3 scripts/reels.py visuals <slug> --generate        # Modal, cached, never blocks the reel
python3 scripts/reels.py visuals <slug> --preview         # LOOK at the contact sheet
```

A visual that fails to generate is left out and that beat ships as footage.
A clip with no `visuals` block builds exactly as it always has.

## Step 5 — Render

```bash
python3 scripts/reels.py check  _                # the rule suite, ~8s, no render
python3 scripts/reels.py build  <slug>           # brief + alignment + visuals -> captions_data.json
python3 scripts/reels.py stage  <slug>           # swap this clip's assets (and its AI files) into the studio
python3 scripts/reels.py render <slug> kyros     # finalise this cut first
python3 scripts/reels.py render <slug> partner   # then this one — same edit, same visuals
```

`build` places every visual against the same hazards as the captions: an
inset card pushes that beat's caption low, the plate never appears while she
is in the bubble, the bubble never sits on the mark or a live caption, and a
caption gets a ground of its own if a picture would out-shout it. Read the
"supporting visuals" block it prints.

The component reads every colour, size, position and duration from the staged
`captions_data.json`. Nothing is hardcoded, so a reposition is a number change,
not a code change — keep it that way.

**Only the composed `.mp4`s are what he posts.** Add `--overlays` for the
transparent caption layers, which exist so he can drop his own visuals in an
editor. Ask whether he wants them — they roughly double render time and add
several hundred megabytes, and most weeks he doesn't need them.

## Step 6 — Verify; do not assume

```bash
python3 scripts/reels.py verify <slug>
```

Three real bugs shipped past visual inspection before this existed:

- An end-card clip that never played — `OffthreadVideo` without a `Sequence`
  wrapper read its time from the composition timeline and asked a 3-second clip
  for its frame at 16.4s, so it held one frame. **Frame hashes catch this;
  eyes do not.**
- A stat card that reserved an empty coloured box on screen for seconds before
  its number arrived.
- A logo invisible against the wall because its accent colour scored 1.6:1.

Check the numbers, not the vibe. Report what you actually measured.

With supporting visuals, `verify` also checks every AI file (present,
decodable, long enough, has metadata), proves each visual is actually in the
render, and saves a frame per visual to `out/previews/`. Open those frames.
It cannot judge whether a picture is good or shows what she said — you can.

Then back it up — media is not in git, so until this runs the clip, the AI
files and the cuts exist only on this disk:

```bash
python3 scripts/reels.py push <slug>
```

It copies to the R2 bucket and checks every file; it never deletes anything
there. On a fresh clone or a missing clip, `pull <slug>` fills in what's
missing and never overwrites. Never `git add` media — `.gitignore` blocks it
and `check` fails if any is tracked. Setup: `Reels/docs/MEDIA.md`.

## Step 7 — Compliance: check the wording, not the doctor

Two things Niranjan has settled, so don't re-raise them:

- **Registration details stay off screen.** They're handled at consultation.
  Don't add a registration line, and don't ask for the number.
- **The doctor is the authority on her own figures.** Statistics she states on
  camera are not second-guessed against other sources. Caption what she said.

What still needs a read, because it's about wording rather than facts — see
`kyros-clinical-compliance` for the detail:

- No cure, reverse, eliminate, or guarantee language. No promised timelines.
  Schedule J applies across most Kyros verticals.
- No fabricated testimonials, outcomes, or before/after imagery.
- Caption faithfully. If her own words sit close to awkward framing, raise it
  with Niranjan rather than quietly rewording her.
- Visuals show what she said and nothing else: no before/after, no reports or
  scans, no patients or testimonials, no second doctor, no number she didn't
  say. The prompt lint blocks these; don't write around it.
- Realistic AI imagery is labelled at upload (YouTube "Altered or synthetic
  content", Instagram "AI info") — `verify` reminds you. Nothing is burned in.

## References

- `references/intake.md` — the questionnaire and folder convention
- `references/styles.md` — style presets and the rotation rule
- `references/pipeline.md` — chunking, sizing, layout, the technical gotchas
- `references/visuals.md` — supporting visuals: when, which rung, treatments,
  prompts, safety, Modal, cost, cache, failure
- `Reels/README.md` — the commands, and what's shared vs per-clip
- `Reels/docs/VISUALS.md` — our Modal servers (infra/modal), setup, environment, storage
- `Reels/docs/MEDIA.md` — where media lives (R2 via rclone), push / pull
