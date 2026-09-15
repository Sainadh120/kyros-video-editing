# Supporting visuals

The doctor is the reel. Her face, her voice, her words. Everything in this
file exists to make what she is saying land harder — never to replace her,
never to decorate.

## The one rule

**Show what she says.** Every visual is a literal, realistic picture of the
words coming out of her mouth on that beat. She says "swimming, running,
jogging, cycling" — the viewer sees someone swimming. She says "8 to 10,000
steps per day" — the number counts up. She says "reduce stress" — a quiet,
real moment of someone breathing out.

Never what she didn't say. No invented results, no before/after, no lab
reports or scans, no patients, no testimonials, no second doctor. If a beat
has nothing literal to show, it gets nothing — her face is the visual.

Hierarchy, in order: her spoken content → clinical clarity → caption
readability → brand → supporting visuals → decoration.

## What the research says (September 2026)

- Healthcare Reels where a clinician teaches directly get the highest organic
  engagement — the doctor stays the anchor ([GrowLimo][r1]).
- The first 1–3 seconds decide whether anyone stays; the strongest openings
  change the picture immediately and state the promise on screen
  ([Aibrify][r3]; [OpusClip][r2]). A dark card with type on it is clean but
  visually blank. So the opening is pictures of what the question asks about,
  with the question in big type — and her face arrives the moment she answers
  (Niranjan, 2026-09-11: "why do we need to show the doctor while asking the
  question?").
- Pacing that holds attention changes something on screen every 1.5–2s. Our
  captions already do that; visuals add a bigger interrupt every 5–8s
  ([Aibrify][r3]).
- B-roll that runs longer than 3–5s pulls focus from the narrator's voice
  ([OpusClip][r4]).
- Kinetic type, animated statistics, progress bars and minimal UI-style
  overlays are the dominant educational motion language of 2026
  ([MonkyVision][r5]; [GarageFarm][r6]).
- AI generation now matches stock footage for environments, objects and
  establishing shots, but still struggles with close-up faces and complex body
  motion — which reads uncanny ([Envato][r7]). So realistic people are shown
  as stills with a slow camera move, or in medium/wide shots where the body,
  not the face, carries the action.
- Photorealistic AI people and events need the platform's AI label at upload
  (YouTube "altered or synthetic", Instagram "AI info"; India's IT Rules 2026
  put the label duty on platforms, which ask the uploader) ([Freshfields][r8];
  [InfluencerMarketingHub][r9]). `verify` reminds you; nothing is burned in.

## The ladder — the cheapest thing that shows it

Walk down this list per beat and stop at the first rung that works.

| Rung | What | Cost | When |
|---|---|---|---|
| 0 | **Nothing.** Her face is the picture. | $0 | Hook, nuance, caveats, personal advice, the close, any beat under ~1.4s, connective speech ("so", "let me explain") |
| 1 | **Text / number animation** (`mode: "graphic"`) — Remotion draws it | $0 | She states a number, a frequency, a duration, or a list |
| 2 | **AI still + slow camera move** (`mode: "image"`, FLUX.2) | ~$0.002–0.01 | A thing, a place, a person doing something simple. Default for realistic people |
| 3 | **AI still, animated** (`mode: "video"` with `input: {visual: <still id>}`, LTX-2 image-to-video) | ~$0.05–0.25 | The action IS the point and the still already looks right |
| 4 | **AI video from text** (`mode: "video"`, LTX-2) | ~$0.05–0.25 | Simple continuous motion: water, walking feet, a turning wheel, steam |
| — | Image edit (`mode: "imageEdit"`, Qwen) | ~$0.01–0.05 | Only when a real reference image exists (a clinic photo, a partner asset) |

Rung 1 before rung 2 when the beat is a number. Rung 2 before rung 3 always —
a still that looks real beats a video that looks generated.

## Deciding per beat

Score each beat; propose a visual at **3 or more**.

| Signal | Score |
|---|---|
| She names something concrete you can literally show — an activity, object, food, place | +3 |
| She states a number, frequency, duration or list | +3 (→ graphic) |
| She explains a mechanism a picture makes clearer (insulin, ovaries, muscle) | +2 (review) |
| Beat is ≥ 2s | +1 |
| Beat is < 1.4s | −2 |
| Connective or meta speech | −3 |
| Nuance, caveat, reassurance, personal advice — her delivery IS the message | −3 |
| The footage already carries a burned-in graphic (≥ 75% of the beat) | −4 (hard stop) |
| A full-frame visual ended less than 1.5s ago | −2 |

Budget: as many as the words earn — typically 3–6 moments in a 30–50s reel,
where a list counts as one moment. The question always opens on pictures
(see "The opening"). Nothing on a closing line that is her own advice or
reassurance — she closes. She is full-frame for at least half of the answer.

**Match the count to what she says.** She names one thing → one visual. She
names four exercises → four images, each on its own word (a `listBuild`),
never one standing in for all of them. On the pilot she said "swimming,
running, jogging, cycling" and the reel showed only a swimmer — that is the
mistake this rule exists to stop.

## Treatments — how a visual shares the frame with her

| Treatment | Doctor | Visual | Use for |
|---|---|---|---|
| `doctorBubble` | shrinks into a circle or rounded square in a corner, then pops back full-frame | fills the frame | the default for realistic scenes — the viewer sees the thing AND her |
| `inset` | stays full-frame | a card on the bare wall above her head; that beat's caption drops low | graphics and objects when her delivery is lively and she should stay big |
| `cutaway` | gone (voice continues), ≤ 2.5s | fills the frame | one quick literal shot on a list rung |
| `hookBackdrop` | not shown while the question is asked | the whole frame from frame 1, one picture or a short sequence cut on the question's words; the card disappears and only the words get a measured glow | **every reel** — the opening is never a blank card |
| `listBuild` | in her bubble | each item of a spoken list arrives centre stage on its own word, then glides into a tile; all end on screen together, optionally labelled | she names 2–6 things in a row |

Measured rules the build enforces, so you don't have to:

- An inset is a burned-in graphic as far as the captions know: that beat goes low.
- The plate never appears while she is in the bubble or cut away — it names her.
- The mark never sits on an inset; the bubble never sits on the mark, a live
  caption, the platform's right-side button column, or outside the safe area.
- Two full-frame visuals always have ≥ 1.5s of her full-frame between them.
- Cutaway ≤ 2.5s; bubble and inset ≤ 6s; anything under 1.2s is dropped, not flashed.
- A video never outlasts its clip; the window shortens to fit.
- Captions over a full-frame visual get a soft ground of their own when the
  measured contrast would fall under 45 Lc.
- The bubble shape rotates between reels (`bubbleShape`, a register axis).

## Graphics (rung 1) — her numbers, drawn exactly

`mode: "graphic"`, no model, no cost. Four types:

| `graphic.type` | Shows | Fields | Example beat |
|---|---|---|---|
| `counter` | a number counting up, with a label | `value`, optional `from`, `prefix`, `suffix`, `label` | "8 to 10,000 steps per day" → `{"value": 10000, "from": 8000, "label": "STEPS / DAY"}` |
| `frequency` | seven day-dots, the spoken count lit | `count` (int or `[2, 3]`), `label` | "two or three times a week" |
| `ring` | a ring filling to its value | `value`, `unit`, `label` | "150 minutes per week" |
| `checklist` | items ticking in as she names them | `items` (≤ 4, 1–3 words each) | "daily movement, cardio, strength training" |

**Every number in a graphic must be a number she spoke on that beat.** The
build checks it against the transcript ("two or three" counts as 2 and 3;
"10 ,000" as 10000) and blocks a graphic that shows one she didn't say. When a
graphic carries the beat, set `"skip": true` on that beat's caption so the
same number is not on screen twice.

## Image or video?

Default to an animated still (slow push, pan) and text animation; use video
wherever motion genuinely adds something — there is no cap, only the test
"does movement carry the meaning here?".

- **People** → still + slow move (`motion: "pushIn"`), medium or wide shot,
  body doing the action, face not the subject. Video for simple continuous
  motion (walking, jogging, swimming, cycling seen wide).
- **Objects and places** → still, or video when something moves.
- **Motion that is the point** (swimming stroke, pedal turning, water, breath)
  → video, ideally animating an approved still (`input: {"visual": "v3"}`).
- **Anatomy / physiology** → realistic educational 3D visualisation, clearly a
  medical illustration, never styled as a real patient's scan. Always `review`.
  FLUX Klein is weak at anatomy: on `pcos-blood-tests` three ovary attempts gave
  a heart-shaped balloon on a stem, literal jewellery pearls ("string of
  pearls" taken at its word), and a ring studded with black beads. Describe the
  shape plainly (no metaphors), allow two retries, then drop the picture — her
  face and the caption carry the beat. Wrong anatomy never ships.
- **Tests, reports, numbers** → never a generated report or result. Text
  animation for the test names and numbers she says; realistic non-evidential
  pictures (a sample tube in a gloved hand, a calm lab bench, a measuring tape
  at the waist) for the act, never the outcome.

**Quality.** `visuals.quality: "hd"` (the default) generates stills at
720x1280 (cards 1024x576, list tiles 768x768) and video at 576x1024, and cuts
each video to its beat's length. That is enough under captions in a 1080x1920
master, and about half the GPU time. `"full"` is the pilot's old size, kept
only so its cached pictures stay valid.

**People, modestly.** The audience is Indian women with PCOS. Modest
activewear or everyday clothes, medium or wide shots, no close-ups of the
body. Swimming is a wide shot, head and shoulders in the water.

## The opening — the first 3 seconds

The question is the hook, so it opens on pictures, never a blank card:

- `hookBackdrop` visuals fill the frame from frame 1 to the moment she
  starts answering. One picture with a slow push, or a short sequence cut on
  the question's own words (`at: [start, end]` per picture, contiguous).
- They show what the question asks about, realistically ("what blood tests"
  → a sample tube in a gloved hand, a lab bench in morning light).
- When the pictures cover the whole question, the dark card disappears and
  `build` puts a soft glow behind the question's words only, measured against
  the pictures (45 Lc). If they leave a gap, the card stays, thinned, so she
  never peeks through mid-question.
- Her face arrives with her answer, full-frame.
- Every spoken word of the question belongs in `question.rows` — including
  an interviewer's "Ma'am," before it. The build times her answer from the
  first word *outside* the rows; leave "Ma'am" out and her answer "starts" at
  0.8s, the opening has no room, and the question clears early. A key row's
  `lines` decide what is shown, so extra words can sit in `words` unseen.

## Lists — show every item

When she names things in a row, the list is the visual: one `listBuild` item
per thing she names, sharing a `group`, each with the `word` (index) where she
says it and a short `label`.

- Each item pops out on its word — about 35% larger, centred over its own
  tile — and settles into the tile as the next one arrives. Tiles already
  placed stay visible, so the grid visibly fills one item at a time; the last
  settles with a beat to spare and every item holds together before she moves
  on. (Arriving over the whole stage hid every earlier tile until the last
  second — `pcos-blood-tests`, first render.)
- Tiles: 2 stacked, 3 as one over two, 4 as a 2x2, 5–6 as two rows.
- Labels on the tiles are the text list — set `"skip": true` on that beat's
  caption (the build warns if a caption is still on).
- Items that look alike (four blood tests are four tubes) are better as a
  text animation (`checklist`) than four near-identical pictures. Match the
  choreography to the situation.
- The group counts once against her screen time; her bubble stays on.

## Writing the prompt

Write the prompt you want sent — it goes to the model verbatim, and it is
what the cache keys on.

**FLUX.2 (images).** Subject first — word order matters. 30–80 words. No
negative prompts (not supported); describe what you want instead. Tie
colours to objects with hex codes when the palette matters.

> subject + action → setting (real Indian context) → composition for 9:16 →
> camera/lens → light → realism cue → one colour tie-in

```
A woman in her early thirties in a navy t-shirt and grey track pants walks
briskly along a tree-lined park track in Hyderabad at sunrise, mid-stride,
seen side-on from a slight distance. Vertical 9:16 frame, calm open sky in the
upper third. Shot on a 35mm lens at eye level, soft golden light, candid
documentary photograph, natural skin texture, true-to-life colour.
```

**LTX-2 (video).** One flowing paragraph, present tense, 4–8 sentences.
Say what moves, how the camera moves and when, and one lighting logic.
Always pass a `negative`.

```
Clear turquoise water in an outdoor community pool at morning. A swimmer in a
dark swimsuit and cap glides forward doing an easy freestyle stroke, arms
rising and entering the water in a steady rhythm. The camera tracks slowly
alongside at water level, keeping the swimmer in the lower half of the frame.
Sunlight ripples across the pool floor. Realistic, natural motion, true colour.
```
negative: `flickering, jitter, warping, distorted limbs, extra fingers,
blurry, low quality, text, watermark, logo, cartoon`

**Realism vocabulary.** candid documentary photograph · shot on a 35mm/50mm
lens · natural window light · golden hour · shallow depth of field · true-to-
life colour · natural skin texture · real Indian setting (a Hyderabad
apartment balcony, a park walking track, a neighbourhood gym, a community
pool, a kitchen with steel vessels).

**Composition for captions.** Say where the calm space is: "calm open sky in
the upper third" (top captions) or "uncluttered floor in the lower third"
(low captions). Keep the subject out of the bubble's corner.

**Never ask a model for exact text.** No numbers, words or logos in the
image — Remotion sets every word. Avoid "sign", "label", "poster", "screen".

**Models invent text on anything that could carry it.** Tubes grow printed
labels, test strips grow gibberish, scales and meters show digits. FLUX has no
negative prompt, so describe surfaces that cannot carry text: "a bare
transparent glass tube with no sticker", "a plain white blank test strip", a
viewpoint that keeps a display out of frame ("side view at floor level, only
the scale's edge visible"), "the meter turned away". A digit on a scale is a
number she never said — reject it.

**Visual style** (`visuals.style`, a register axis — rotates between reels,
but content suitability always wins): `naturalLight` (soft daylight,
documentary), `goldenHour` (warm low sun, cinematic), `brightAiry` (high-key,
clean, minimal), `documentary` (handheld realism, available light).

## Worked example — `pcos-best-exercise` (46s)

| Beat | She says | Rung | Proposal |
|---|---|---|---|
| hook | "What is the best exercise for PCOS?" | 0 | nothing — the question card owns it |
| 1 | "no single best exercise" | 0 | her face — a nuance line |
| 2 | "combine daily movement, cardiovascular exercise, strength training" | 1 | `checklist` inset: DAILY MOVEMENT / CARDIO / STRENGTH |
| 3 | "8 to 10,000 steps per day" | 1 + 2 | `counter` 8,000→10,000 STEPS / DAY, or a still of feet on a morning walking track |
| 4 | "resistance or strength training, gym or yoga, 2 or 3 times a week" | 2 | bubble + still: a woman doing a dumbbell row in a neighbourhood gym |
| 5 | "swimming, running, jogging, cycling, 150 minutes per week" | 3/4 | bubble + video: easy freestyle in a community pool; `ring` 150 MIN if the budget allows |
| 6 | "meditation, reduce stress, 2 or 3 times a week" | 2 | bubble + still: a woman seated cross-legged by a sunlit window, eyes closed |
| close | — | 0 | her face |

## Safety — what never appears

Kept because the law and the brief both require it:

- before/after, transformation, "results" imagery of any kind
- lab reports, scans (MRI/CT/X-ray/ultrasound), prescriptions, charts,
  journals or studies — anything that looks like evidence or a record
- a patient, a testimonial, a rating, a quote
- a doctor, nurse, white coat or stethoscope — the real doctor is the only
  clinician on screen
- branded medicine, labels, dosages
- a number she didn't say

`reels.py visuals` lints every prompt: **blocked** ones can never be approved;
**review** ones (anatomy, medicine, children) need an explicit
`--approve <id>` — `--approve all` skips them. Everything else is low risk.

## The brief

Everything lives in `brief.json` under `visuals`. Absent — or
`enabled: false`, or no approved beats — and the reel builds exactly as it
always has.

```json
"visuals": {
  "enabled": true,
  "style": "naturalLight",
  "bubbleShape": "circle",
  "beats": [
    {"id": "v1", "beat": 2, "mode": "graphic", "treatment": "inset",
     "graphic": {"type": "checklist",
                 "items": ["DAILY MOVEMENT", "CARDIO", "STRENGTH"]},
     "status": "proposed",
     "_why": "she lists the three; the list is the point"},
    {"id": "v2", "beat": 4, "mode": "image", "treatment": "doctorBubble",
     "motion": "pushIn",
     "prompt": "A woman in her thirties does a one-arm dumbbell row ...",
     "status": "proposed",
     "_why": "she names gym strength training"},
    {"id": "v3", "beat": 5, "mode": "video", "treatment": "doctorBubble",
     "prompt": "Clear turquoise water in an outdoor community pool ...",
     "negative": "flickering, jitter, warping, ...",
     "status": "proposed",
     "_why": "swimming is the first cardio she names; motion is the point"}
  ]
}
```

| Field | Values | Notes |
|---|---|---|
| `id` | `v1`, `v2`, … | stable — the manifest and filenames use it |
| `beat` | 1-based chunk number, as `build` prints it | or `at: [startSec, endSec]` for a window of your own |
| `mode` | `graphic`, `image`, `imageEdit`, `video` | |
| `treatment` | `doctorBubble`, `inset`, `cutaway`, `hookBackdrop`, `listBuild` | |
| `group`, `word`, `label` | list id; word index she says it on; 1–3 word tile label | `listBuild` only |
| `aspect` | `16:9` (default), `4:5`, `1:1` | inset only |
| `motion` | `pushIn` (default), `pullOut`, `panLeft`, `panRight`, `none` | stills only; composition, not generation — changing it never regenerates |
| `input` | `{"visual": "v2"}` or `{"path": "assets/ref/x.jpg"}` | image-to-video / edit source |
| `seed` | int | change it to get a different take of the same prompt |
| `status` | `proposed`, `approved`, `rejected` | `approve` stamps `approvedHash`; editing the prompt afterwards needs approval again |

## Workflow

After the chunk breakdown is agreed (same pass, one approval):

```bash
python3 scripts/reels.py visuals  <slug>                 # the plan: beat by beat, her words beside each prompt, cost
python3 scripts/reels.py visuals  <slug> --approve all   # or --approve v1,v3 ; --reject v2
python3 scripts/reels.py visuals  <slug> --generate      # approved + missing only; cached ones are reused
python3 scripts/reels.py visuals  <slug> --preview       # contact sheet -> out/previews/<slug>-visuals.jpg — LOOK at it
python3 scripts/reels.py build    <slug>
python3 scripts/reels.py stage    <slug>
python3 scripts/reels.py render   <slug> kyros
python3 scripts/reels.py verify   <slug>                 # checks every asset + pulls a frame per visual
```

Propose the visuals together with the chunking — one message Niranjan can
read in thirty seconds, with her words beside each proposal. Don't ask about
each visual separately unless the lint says `review`.

**Look at every generated asset before building.** Check: hands and fingers,
faces (uncanny?), stray text or logos, anything a viewer could read as a
result or a record, and — above all — does it show what she said on that beat.
Reject and re-prompt anything that fails; the old file is kept.

## Modal, cost, cache, failure

- Generation runs through the toolkit at `../claude-code-video-toolkit`
  (override with `KYROS_TOOLKIT_DIR`), always `--cloud modal`. Endpoints come
  from the toolkit's `.env`: `MODAL_FLUX2_ENDPOINT_URL`,
  `MODAL_IMAGE_EDIT_ENDPOINT_URL`, `MODAL_LTX2_ENDPOINT_URL`. A missing one
  fails that visual fast and names the variable. There is no fallback to
  another provider.
- Cost is an **estimate**: seconds the call took × Modal's published
  per-second rate for the GPU that app runs on (A10G $0.000306/s for FLUX.2;
  A100-80GB $0.000694/s for LTX-2 and image edit). Cold starts are included,
  so the first call of a session costs more. Real charges:
  `uv run modal billing report --for today --json` in the toolkit.
- Assets live in `projects/<slug>/assets/ai/<id>-<hash12>.<ext>` with a JSON
  sidecar (model, prompt, seed, beat, why, cost, time). The hash covers only
  what changes pixels — model, prompt, negative, size, frames, seed, input.
  Moving a visual to another beat, changing its treatment timing or its
  `motion` never regenerates. The same request made for another clip is
  copied, not regenerated. Nothing is ever overwritten.
- A different take of the same prompt: set a new `seed`.
- A failed generation is recorded in `work/visuals.json` with its reason and
  left out of the build — the reel ships as footage. `--generate --retry`
  tries failures again. `--reject <id>` drops a visual for good.
- Remotion never calls a model. It only plays files `stage` copied into
  `studio/public/ai/`.

[r1]: https://growlimo.com/blog/instagram-reels-healthcare-best-practices/
[r2]: https://www.opus.pro/blog/instagram-reels-hook-formulas
[r3]: https://aibrify.com/blog/youtube-shorts-retention-curve-playbook
[r4]: https://www.opus.pro/research/broll-visual-effects-short-form
[r5]: https://monkyvision.com/blog/motion-design-trends/
[r6]: https://garagefarm.net/blog/animation-trends-to-watch
[r7]: https://elements.envato.com/learn/ai-video-generators-vs-stock-footage
[r8]: https://www.freshfields.com/en/our-thinking/blogs/technology-quotient/india-targets-deepfakes-and-ai-generated-content-key-changes-under-meitys-2026-102mjwn
[r9]: https://influencermarketinghub.com/ai-disclosure-rules/
