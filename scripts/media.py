"""Media storage outside git. `reels.py push` / `pull` copy a project's clips,
AI files, audio and final cuts to an rclone remote — Cloudflare R2 by default —
and back.

Git holds code, briefs, measurements and each AI file's metadata sidecar; the
remote holds the files git can't. Both directions only ever add: push never
deletes anything on the remote, so a clip deleted on disk stays safe up there,
and pull never overwrites a file already on disk, so a fresh re-render is never
replaced by the older one that was backed up. Setup is in docs/MEDIA.md.

What goes up is what can't be remade cheaply: the raw clip, every generated AI
file, the audio `prep` extracted, and the cuts at the top of `out/`. Previews
(`verify` remakes them), superseded drafts in `out/versions/`, `--overlays`
ProRes layers and any other folder under `out/` stay on this disk only.

REELS_MEDIA_REMOTE points somewhere else — any rclone remote (`gdrive:Kyros`)
or a plain folder (`/Volumes/Backup/reels`).
"""
import os, shutil, subprocess, tempfile
from pathlib import Path

DEFAULT_REMOTE = "kyros-r2:kyros-reels"
MEDIA_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4a", ".wav", ".mp3",
             ".png", ".jpg", ".jpeg", ".webp"}
PROGRESS = ["--stats-one-line", "--stats", "30s", "-v"]


def remote_root():
    return os.environ.get("REELS_MEDIA_REMOTE", DEFAULT_REMOTE).rstrip("/")


def remote_for(slug, root=None):
    return f"{(root or remote_root()).rstrip('/')}/projects/{slug}"


def remote_name(root):
    """'kyros-r2' for 'kyros-r2:kyros-reels'; None for a plain folder or an
    on-the-fly ':backend,...:' string, which need no configured remote."""
    if root.startswith(("/", ".", "~")) or ":" not in root:
        return None
    return root.split(":", 1)[0] or None


def configured(root, remotes):
    name = remote_name(root)
    return not name or f"{name}:" in remotes.split()


def listremotes():
    return subprocess.run(["rclone", "listremotes"], capture_output=True,
                          text=True).stdout


def not_ready(root):
    """Why push/pull can't run yet, or None."""
    if not shutil.which("rclone"):
        return "rclone is not installed — brew install rclone"
    if remote_name(root) and not configured(root, listremotes()):
        return (f"no rclone remote '{remote_name(root)}' yet — set it up once, see "
                f"docs/MEDIA.md (or point REELS_MEDIA_REMOTE at another remote)")
    return None


def media_files(project):
    """Project-relative paths of the media worth keeping, sorted."""
    project = Path(project)
    if not project.is_dir():
        return []
    keep = []
    for f in project.rglob("*"):
        rel = f.relative_to(project)
        if not f.is_file() or f.suffix.lower() not in MEDIA_EXT:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts[0] == "out" and (len(rel.parts) > 2 or f.stem.endswith("-overlay")):
            continue
        keep.append(rel.as_posix())
    return sorted(keep)


def push_argv(project, dest, files_from):
    return ["rclone", "copy", str(project), dest, "--files-from", str(files_from),
            *PROGRESS]


def check_argv(project, dest, files_from):
    return ["rclone", "check", str(project), dest, "--one-way",
            "--files-from", str(files_from)]


def pull_argv(src, project):
    return ["rclone", "copy", src, str(project), "--ignore-existing", *PROGRESS]


def local_slugs(arg, projects):
    projects = Path(projects)
    if arg == "all":
        if not projects.is_dir():
            return []
        return sorted(d.name for d in projects.iterdir() if (d / "brief.json").exists())
    if not (projects / arg).is_dir():
        raise SystemExit(f"no project '{arg}' in {projects}")
    return [arg]


def remote_slugs(root):
    r = subprocess.run(["rclone", "lsf", f"{root}/projects", "--dirs-only"],
                       capture_output=True, text=True)
    return sorted(x.strip().rstrip("/") for x in r.stdout.splitlines() if x.strip())


def human(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"


def push(slug, projects, root=None):
    root = root or remote_root()
    msg = not_ready(root)
    if msg:
        print(msg)
        return 2
    rc = 0
    for s in local_slugs(slug, projects):
        p = Path(projects) / s
        files = media_files(p)
        if not files:
            print(f"{s}: no media on disk — nothing to push")
            continue
        dest = remote_for(s, root)
        size = sum((p / f).stat().st_size for f in files)
        print(f"{s}: {len(files)} file(s), {human(size)} -> {dest}")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("\n".join(files) + "\n")
        listing = Path(fh.name)
        try:
            if subprocess.run(push_argv(p, dest, listing)).returncode:
                print(f"   PROBLEM the copy failed — keys and bucket: docs/MEDIA.md")
                rc = 1
                continue
            check = subprocess.run(check_argv(p, dest, listing), capture_output=True,
                                   text=True)
            if check.returncode:
                print(f"   PROBLEM not everything matches after the copy:")
                print("   " + "\n   ".join(check.stderr.strip().splitlines()[-8:]))
                rc = 1
            else:
                print(f"   backed up — every file checked against {dest}")
        finally:
            listing.unlink(missing_ok=True)
    return rc


def pull(slug, projects, root=None):
    root = root or remote_root()
    msg = not_ready(root)
    if msg:
        print(msg)
        return 2
    have = remote_slugs(root)
    if slug != "all" and slug not in have:
        print(f"{slug}: nothing backed up at {remote_for(slug, root)}")
        return 1
    slugs = have if slug == "all" else [slug]
    if not slugs:
        print(f"nothing backed up at {root}/projects yet")
        return 1
    rc = 0
    for s in slugs:
        p = Path(projects) / s
        before = set(media_files(p))
        r = subprocess.run(pull_argv(remote_for(s, root), p))
        got = len(set(media_files(p)) - before)
        print(f"{s}: restored {got} file(s)" if got else f"{s}: nothing missing")
        if r.returncode:
            print(f"   PROBLEM the copy failed — keys and bucket: docs/MEDIA.md")
            rc = 1
    return rc
