# Media — kept on Cloudflare R2, not in git

Git holds what the pipeline decides: scripts, briefs, measurements, caption data,
and one small JSON sidecar per AI file (prompt, seed, model, size, hash). The
files git can't hold — clips, AI pictures and videos, audio, finished cuts — go
to an R2 bucket through `rclone`:

```bash
python3 scripts/reels.py push <slug>    # after every render
python3 scripts/reels.py push all       # every project
python3 scripts/reels.py pull <slug>    # fresh clone, new machine, a deleted clip
python3 scripts/reels.py pull all
```

Why: on 2026-09-11 every inbox clip was deleted from disk by another session and
git happened to be the only copy; and the repo had grown to 2.6 GB of history
with 365 MB source clips, which GitHub refuses (100 MB per file). `.gitignore`
now keeps all media out, and `tests/test_media.py` fails if any is tracked again.

## It only ever adds

- **push never deletes anything in the bucket.** It copies, then checks every
  file against the bucket by size and hash. A clip deleted on disk stays safe
  up there.
- **pull never overwrites a file already on disk.** It only fills in what is
  missing, so a fresh re-render is never replaced by the older backed-up cut.

Removing something from the bucket is a deliberate, manual act:
`rclone delete kyros-r2:kyros-reels/projects/<slug>/<file>`.

## What goes up, what stays on this disk

| Goes up                                  | Stays local only (why)                              |
|------------------------------------------|-----------------------------------------------------|
| `inbox/` — the raw clip                  | `out/previews/` — `verify` remakes them             |
| `assets/ai/` — every generated file      | `out/versions/` — superseded drafts                 |
| `work/*.m4a`, `work/*.wav` — prep audio  | `out/*-overlay.mov` — `--overlays` layers, re-renderable |
| `out/<slug>-kyros.mp4`, `-partner.mp4`   | `studio/public/` — staging copies                   |

`brand/` artwork (plate, logos, outro — about 3 MB) stays in git, because a
fresh clone needs it to build anything.

As of 2026-09-11 a full push is 58 files, 2.6 GB — inside R2's free 10 GB.
Beyond that storage is about $0.015 per GB-month; downloads are free.

## One-time setup

rclone is installed (`brew install rclone`) and `~/.config/rclone/rclone.conf`
already has a `kyros-r2` remote with three placeholders. What's left needs a
Cloudflare login:

1. **Enable R2.** <https://dash.cloudflare.com> → sign up or log in →
   *R2 Object Storage*. Cloudflare asks for a card even on the free tier.
2. **Create the bucket.** *Create bucket* → name `kyros-reels`, location
   *Automatic*, default storage class *Standard*.
3. **Create an API token.** R2 overview → *Manage API tokens* (under
   *Account details*) → *Create Account API token* →
   permission **Object Read & Write**, *Apply to specific buckets only* →
   `kyros-reels` → *Create*. The next page shows the **Access Key ID**, the
   **Secret Access Key** (shown once — copy it now) and the S3 endpoint
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
4. **Paste them into the rclone config yourself** — never into a chat:
   ```bash
   open -e ~/.config/rclone/rclone.conf
   ```
   Replace `PASTE-ACCESS-KEY-ID`, `PASTE-SECRET-ACCESS-KEY` and the
   `PASTE-ACCOUNT-ID` inside the endpoint. Save.
5. **Test, then back everything up.**
   ```bash
   rclone lsf kyros-r2:kyros-reels          # no output, no error = working
   python3 scripts/reels.py push all        # ~2.6 GB the first time
   ```

`no_check_bucket = true` in the config is deliberate: a token scoped to one
bucket may not create or list buckets, and rclone would otherwise try.

## Somewhere other than R2

Any rclone remote or a plain folder works — set `REELS_MEDIA_REMOTE`:

```bash
REELS_MEDIA_REMOTE=gdrive:Kyros/Reels  python3 scripts/reels.py push all   # after `rclone config` for Drive
REELS_MEDIA_REMOTE=/Volumes/Backup/reels python3 scripts/reels.py push all # an external disk
```

Files land under `<remote>/projects/<slug>/` with the same layout as the project.

## Trouble

| rclone says                                | Means                                                  |
|--------------------------------------------|--------------------------------------------------------|
| `no rclone remote 'kyros-r2' yet`          | the config file is missing or has no `[kyros-r2]`      |
| `InvalidAccessKeyId`, `SignatureDoesNotMatch` | a key still reads `PASTE-…`, or was copied with a space |
| `no such host` … `PASTE-ACCOUNT-ID`        | the endpoint still has the placeholder                 |
| `AccessDenied`                             | the token isn't *Read & Write* on `kyros-reels`        |
| `NoSuchBucket`                             | the bucket is named differently — rename it, or set `REELS_MEDIA_REMOTE=kyros-r2:<name>` |

## Git history

The feature branch was rebuilt on GitHub's `main`, so it carries no media and
pushes in a few MB. Local `main` still has one unpushed commit holding the old
clips (the `.git` folder is ~2.6 GB); don't push that commit. Once
`push all` has run and checked clean, local `main` can be moved to the branch and
the history shrunk — that deletes the old copies from `.git`, so it waits for
the bucket to hold them.
