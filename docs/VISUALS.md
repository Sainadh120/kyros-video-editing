# Supporting visuals — setup and operation

The editorial rules (when a beat earns a visual, which treatment, how to write
the prompt, what never appears) live in the skill:
`.claude/skills/kyros-doctor-reels/references/visuals.md`. This file is the
operator's manual: install, configure, run, and what happens to the files.

```
Claude (kyros-doctor-reels skill)      decides: which beats, which rung, the prompt
  └─ brief.json → visuals.beats         the decision, reviewable, versioned
      └─ reels.py visuals --generate    scripts/visuals.py: lint, cache, call
          └─ scripts/modal_client.py    one JSON POST per request, stdlib only
              └─ infra/modal/*_app.py   our own servers: FLUX.2 (A10G) · LTX-2.3 (A100-80GB)
      assets/ai/<id>-<hash>.<ext>       + .json metadata, never overwritten
  └─ reels.py build                     places each visual against every hazard
  └─ reels.py stage                     copies exactly the referenced files into studio/public/ai
  └─ Remotion                           plays files; never calls a model
  └─ reels.py verify                    files, render presence, preview frames, cost
```

Nothing here is required. A brief without `visuals` — or with
`visuals.enabled: false` — builds exactly as it did before this existed.
Text and number animations (`mode: "graphic"`) need no Modal at all.

## 1. Install (once)

The model servers live in this repo (`infra/modal/`), adapted from
claude-code-video-toolkit (MIT; notice in `infra/modal/LICENSE-claude-code-video-toolkit`)
and owned here since 2026-09-17: pins, fixes and upgrades are commits in this
repo, not edits to an untracked clone. The Modal CLI goes into the Python that
runs `reels.py`, together with OpenCV (the doctor bubble measures her face):

```bash
python3 -m pip install modal "opencv-python-headless>=4.10,<5"
```

(OpenCV 5 dropped the face detector used here. Without OpenCV the bubble falls
back to a centred estimate and says so.)

## 2. Connect Modal (once)

```bash
modal setup                    # opens a browser, writes ~/.modal.toml
modal app list                 # proves it worked
```

LTX-2 runs on an A100-80GB, which Modal only allows once a payment method is on
the account. It also needs a Hugging Face read token whose account has
accepted the Gemma licence on huggingface.co (LTX-2.5 also needs its own
licence accepted). The apps read the secret `huggingface-secret`:

```bash
modal secret create huggingface-secret HF_TOKEN=hf_...
```

Type the token yourself; never paste it into a chat.

## 3. Deploy the servers (once, one at a time)

Modal rate-limits app creation, so deploy serially. Every model download is
pinned to a Hugging Face revision in the app file — a rebuild fetches exactly
those weights; upgrading means changing the hash on purpose.

```bash
modal deploy infra/modal/flux2_app.py      # images
modal deploy infra/modal/ltx2_app.py       # LTX-2.3 video — kept for reels pinned to it
modal deploy infra/modal/ltx25_app.py      # LTX-2.5 video — the default since 2026-09-17
modal deploy infra/modal/qwen_image_app.py # Qwen-Image — opt-in per visual (food, anatomy)
```

Each prints an endpoint URL. Put them in `infra/modal/.env` (gitignored —
account-specific):

| Variable | Used for |
|---|---|
| `MODAL_FLUX2_ENDPOINT_URL` | `mode: "image"` |
| `MODAL_LTX2_ENDPOINT_URL` | `engine: "ltx2"` — LTX-2.3, reels pinned to it |
| `MODAL_LTX25_ENDPOINT_URL` | `mode: "video"` — default engine `ltx25` |
| `MODAL_QWEN_IMAGE_ENDPOINT_URL` | `engine: "qwen_image"` |
| `MODAL_IMAGE_EDIT_ENDPOINT_URL` | `mode: "imageEdit"` — its server is not moved in yet |

**Engines.** Each mode has a default (`image` → `flux2`, `video` → `ltx25`).
A brief can set `visuals.engines: {"video": "ltx2"}`; a single visual can set
`engine`. The engine is part of the request hash: switching it regenerates
that visual, and a reel made before a default changed must pin the old engine
to keep its cached files (all reels up to 2026-09-17 pin `video: ltx2`).
`scripts/bakeoff.py` reruns the side-by-side that chose these defaults.

The same names can instead be exported in the shell that runs `reels.py`. A
missing endpoint fails that visual immediately and names the variable; there
is no fallback to another provider. Re-deploying an app under its existing
name keeps its URL.

## 4. Per reel

```bash
python3 scripts/reels.py prep     <slug>
# Claude writes the chunks AND brief.visuals (status "proposed") in one pass
python3 scripts/reels.py visuals  <slug>                  # the plan: her words, each prompt, risk, cost
python3 scripts/reels.py visuals  <slug> --approve all    # low-risk ones; review ones need their id
python3 scripts/reels.py visuals  <slug> --approve v3     # an explicit yes for a review item
python3 scripts/reels.py visuals  <slug> --reject v2      # drop one (= skip)
python3 scripts/reels.py visuals  <slug> --generate       # only approved, only missing
python3 scripts/reels.py visuals  <slug> --generate --only v4 --retry
python3 scripts/reels.py visuals  <slug> --preview        # out/previews/<slug>-visuals.jpg
python3 scripts/reels.py build    <slug>
python3 scripts/reels.py stage    <slug>
python3 scripts/reels.py render   <slug> kyros
python3 scripts/reels.py render   <slug> partner
python3 scripts/reels.py verify   <slug>
```

### Review

`visuals` prints every beat with her words beside it, so a proposal can be
checked against what she actually said. Each prompt is linted:

- **blocked** — before/after, outcomes, reports/scans/prescriptions, patients
  or testimonials, a clinician, claim words. Can never be approved.
- **review** — anatomy/physiology, medicine, minors. `--approve all` skips
  these; approve each by id after reading it.
- **warn** — asks the model for text. Remotion sets every word; rewrite it.

A graphic may only show numbers she spoke on that beat (checked against the
transcript). Approval is bound to the exact request: edit an approved prompt
and it needs approving again.

After `--generate`, open the preview sheet and look — hands, faces, stray text,
and whether each picture shows what she said. Reject anything that doesn't.

### Skip all visuals

Set `"enabled": false` under `visuals` (or delete the block) and rebuild. Or
reject individual ones. Nothing generated is deleted either way.

### Regenerate one visual

The same request is the same picture, so "regenerate" means change the request:

- a different take of the same idea — set `"seed": <any int>` on that beat
- a better idea — edit its `prompt`

Then `--approve <id>` and `--generate --only <id>`. The old file stays.

## 5. Where the files go

```
projects/<slug>/
  brief.json                    visuals.beats — the decisions (status, prompt, why)
  assets/ai/v2-3fa9c0d1e2b4.png the asset: <visual id>-<first 12 of the request hash>
  assets/ai/v2-3fa9c0d1e2b4.json its metadata (below)
  work/visuals.json             the manifest: per visual, complete / failed / blocked + reason; every run's counts and cost
  out/previews/                 contact sheet + one render frame per visual (from verify)
studio/public/ai/               copies of exactly what the staged build references; cleared on every stage
```

The metadata sidecar answers, for any asset: which model (`tool`, `model`,
`gpu`, `infraCommit` — `toolkitCommit` on assets made before 2026-09-17), what prompt (`prompt`, `negative`, `seed`, full
`request`), which beat asked for it and why (`visualIds`, `sourceBeats`,
`says`, `why`), when (`createdAt`), how long (`elapsedSec`) and roughly what it
cost (`costEstimateUsd`, `costBasis`).

## 6. Caching

The cache key is a SHA-256 of everything that changes pixels — tool, model,
prompt, negative, width, height, seed, frames, fps, quality, and the input
image. Not the beat, not the timing, not the treatment's position, not the
camera move (`motion`). So:

- rebuilding, restaging, re-rendering, moving a visual to another beat, or
  changing its camera move → nothing regenerates;
- the same request in another clip → the file is copied from that project;
- a changed prompt or seed → a new file beside the old one.

Files are written to a temporary folder and moved into place only after they
decode; an existing asset is never overwritten.

## 7. Cost

Every generation records an **estimate**: the seconds the call took × Modal's
published per-second price for the GPU that app runs on (checked 2026-09-11):

| Tool | GPU | $/s | Typical |
|---|---|---|---|
| FLUX.2 Klein 4B | A10G | 0.000306 | ~$0.002 warm, ~$0.014 with a cold start |
| LTX-2.3 | A100-80GB | 0.000694 | ~$0.06–0.25 per ~5s clip |
| Qwen image edit | A100-80GB | 0.000694 | ~$0.01–0.3 (5–8 min cold start) |

The wall-clock includes cold start and transfer and excludes Modal's region
multipliers, so it is approximate. `verify` and `--generate` print the reel's
totals (images, videos, text animations, reused, failed, estimated cost). For
real charges: `modal billing report --for today --json`.
The Starter plan includes $30/month of compute.

## 8. When generation fails

It is allowed to. A failure is written to `work/visuals.json` with the reason
(missing endpoint, Modal unavailable, timeout, empty or undecodable output),
nothing is written to `assets/ai/`, and `build` leaves that visual out — the
beat ships as footage and the build log says so. `--generate --retry` tries
again; `--reject <id>` gives up on it. The reel is never blocked by a visual.

### Known failure: the LTX-2 app crash-loops on start

Symptom: `--generate` on a video waits until `timed out after 1500s`; the Modal
logs for `video-toolkit-ltx2` repeat
`AttributeError: module 'torch.compiler' has no attribute 'nested_compile_region'`.

Cause (found 2026-09-11): the app pins
`torch==2.7.0` but cloned LTX-2's latest code unpinned; LTX-2 commit
`2362161` (2026-08-11) started calling a torch ≥2.8 API. Every container died
in `load_pipeline`, Modal kept restarting it, and the request just waited.

Fix: `infra/modal/ltx2_app.py` checks out LTX-2 at
`4f8905737aac86a554637cac86c178877a39c744`, the last commit before the break,
which already supports the LTX-2.3 weights the app bakes. Moving past it means
moving torch past 2.7 in the same change.

A failed call's time is reported as an upper bound ("Failed calls: up to $…"),
not as generation cost — on this failure the estimate said $1.04 and Modal
billed $0.15, because the time was spent waiting, not on the GPU.

## 9. Verify

`reels.py verify <slug>` runs the original render checks, then for each visual:
the file exists, is not empty, decodes, is big enough, a video is at least as
long as its window, the metadata is there — and in each rendered cut the
visual's region at mid-window differs from the raw take (so it is really on
screen). It saves that frame to `out/previews/<slug>-<cut>-<id>.jpg`. It cannot
judge whether a picture is good; look at the frames.

Posting: a reel with realistic AI imagery gets the platform's AI label at
upload (YouTube "Altered or synthetic content", Instagram "AI info"). `verify`
prints the reminder.

## 10. Tests

`reels.py check _` includes `tests/test_visuals.py`: off-by-default, timing
budgets, cache reuse and invalidation, approval and lint, failure handling,
metadata, placement against captions/plate/mark/safe area, staging, verify,
the Modal request bodies, and the graphics' spoken-number rule. The fake
generator writes real media with ffmpeg, so none of it needs Modal.

`KYROS_SLOW=1 python3 -m pytest tests/test_visuals.py -k byte_identical`
rebuilds every shipped project and compares against
`tests/fixtures/rebuild_md5.json` — the proof that clips without visuals are
untouched. It needs the source clips in each `inbox/`.
