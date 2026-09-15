# Supporting visuals — setup and operation

The editorial rules (when a beat earns a visual, which treatment, how to write
the prompt, what never appears) live in the skill:
`.claude/skills/kyros-doctor-reels/references/visuals.md`. This file is the
operator's manual: install, configure, run, and what happens to the files.

```
Claude (kyros-doctor-reels skill)      decides: which beats, which rung, the prompt
  └─ brief.json → visuals.beats         the decision, reviewable, versioned
      └─ reels.py visuals --generate    scripts/visuals.py: lint, cache, call
          └─ claude-code-video-toolkit  tools/flux2.py · tools/ltx2.py · tools/image_edit.py
              └─ Modal GPU              FLUX.2 (A10G) · LTX-2 / Qwen edit (A100-80GB)
      assets/ai/<id>-<hash>.<ext>       + .json metadata, never overwritten
  └─ reels.py build                     places each visual against every hazard
  └─ reels.py stage                     copies exactly the referenced files into studio/public/ai
  └─ Remotion                           plays files; never calls a model
  └─ reels.py verify                    files, render presence, preview frames, cost
```

Nothing here is required. A brief without `visuals` — or with
`visuals.enabled: false` — builds exactly as it did before this existed.
Text and number animations (`mode: "graphic"`) need no toolkit and no Modal.

## 1. Install the toolkit (once)

The toolkit lives beside this folder, not inside it:

```bash
cd ~/Downloads/Personal/Kyros_Project
git clone https://github.com/digitalsamba/claude-code-video-toolkit.git
cd claude-code-video-toolkit
uv sync --extra modal          # its own .venv, including the Modal CLI
```

Somewhere else? Set `KYROS_TOOLKIT_DIR=/path/to/claude-code-video-toolkit`.

`uv` is required (`brew install uv`). The doctor bubble measures her face with
OpenCV; install it into the Python that runs `reels.py`:

```bash
python3 -m pip install "opencv-python-headless>=4.10,<5"
```

(OpenCV 5 dropped the face detector used here. Without OpenCV the bubble falls
back to a centred estimate and says so.)

## 2. Connect Modal (once)

From the toolkit folder — or run `/setup` inside a Claude Code session opened
there, which walks the same steps:

```bash
uv run modal setup             # opens a browser, writes ~/.modal.toml
uv run modal app list          # proves it worked
```

LTX-2 (video) and Qwen image edit run on an A100-80GB, which Modal only allows
once a payment method is on the account. LTX-2 also needs a Hugging Face
read token (and the Gemma licence accepted on huggingface.co):

```bash
uv run modal secret create huggingface-token HF_TOKEN=hf_...
```

Type the token yourself; never paste it into a chat.

## 3. Deploy the apps (once, one at a time)

Modal rate-limits app creation, so deploy serially:

```bash
uv run modal deploy docker/modal-flux2/app.py        # images — the one you need first
uv run modal deploy docker/modal-ltx2/app.py         # video — ~15 min, bakes ~62 GB of weights
uv run modal deploy docker/modal-image-edit/app.py   # optional — edits of a reference image
```

Each prints an endpoint URL. Put them in the toolkit's `.env`
(`cp .env.example .env` first if it doesn't exist):

| Variable | Used for |
|---|---|
| `MODAL_FLUX2_ENDPOINT_URL` | `mode: "image"` |
| `MODAL_LTX2_ENDPOINT_URL` | `mode: "video"` |
| `MODAL_IMAGE_EDIT_ENDPOINT_URL` | `mode: "imageEdit"` |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | optional — only if you locked the endpoints |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | optional — faster transfer of large results |

The same names can instead be exported in the shell that runs `reels.py`. A
missing endpoint fails that visual immediately and names the variable; there
is no fallback to another provider.

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
`gpu`, `toolkitCommit`), what prompt (`prompt`, `negative`, `seed`, full
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
real charges: `uv run modal billing report --for today --json` in the toolkit.
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

Cause (found 2026-09-11): the toolkit's `docker/modal-ltx2/app.py` pins
`torch==2.7.0` but cloned LTX-2's latest code unpinned; LTX-2 commit
`2362161` (2026-08-11) started calling a torch ≥2.8 API. Every container died
in `load_pipeline`, Modal kept restarting it, and the request just waited.

Fix applied in the local toolkit clone (not yet upstream): the clone is pinned
to `4f8905737aac86a554637cac86c178877a39c744`, the last LTX-2 commit before the
break, which already supports the LTX-2.3 weights the app bakes. After pulling
a newer toolkit, check that pin is still there before redeploying:

```bash
grep -n "checkout 4f89057" docker/modal-ltx2/app.py
uv run modal deploy docker/modal-ltx2/app.py
```

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
the toolkit command line, and the graphics' spoken-number rule. The fake
generator writes real media with ffmpeg, so none of it needs Modal.

`KYROS_SLOW=1 python3 -m pytest tests/test_visuals.py -k byte_identical`
rebuilds every shipped project and compares against
`tests/fixtures/rebuild_md5.json` — the proof that clips without visuals are
untouched. It needs the source clips in each `inbox/`.
