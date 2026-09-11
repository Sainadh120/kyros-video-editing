"""Media lives on an rclone remote, never in git.

Two things forced this. On 2026-09-11 every inbox clip was deleted from disk
by another session and git was the only copy; and the repo's history had grown
to 2.6 GB of source clips up to 365 MB each, which GitHub refuses outright. So
git keeps code, briefs and measurements, and `reels.py push` / `pull` keep the
files git can't hold. Both directions only ever add: push never deletes on the
remote, pull never overwrites what is already on disk."""
import os, shutil, subprocess, sys
from pathlib import Path

import pytest

import media

ROOT = Path(__file__).resolve().parent.parent
HAS_RCLONE = shutil.which("rclone") is not None


def make_project(projects, slug="pcos-demo"):
    p = projects / slug
    files = {
        "brief.json": "{}",
        "inbox/clip.mp4": "raw clip",
        "inbox/.DS_Store": "junk",
        "assets/ai/v1-0123456789ab.png": "picture",
        "assets/ai/v1-0123456789ab.json": "{}",
        "assets/ai/h1-0123456789ab.mp4": "ai clip",
        "work/playback.m4a": "audio",
        "work/align.wav": "audio",
        "work/words.json": "[]",
        f"out/{slug}-kyros.mp4": "kyros cut",
        f"out/{slug}-partner.MP4": "partner cut",
        f"out/{slug}-kyros.render.json": "{}",
        "out/previews/v1.jpg": "preview",
        f"out/versions/{slug}-kyros-v1.mp4": "old draft",
        "out/overlays/captions.mov": "overlay layer",
        f"out/{slug}-kyros-overlay.mov": "prores overlay layer",
    }
    for rel, body in files.items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(body)
    return p


class TestWhatGoesUp:
    def test_media_files_are_the_ones_that_cannot_be_remade(self, tmp_path):
        p = make_project(tmp_path)
        assert media.media_files(p) == [
            "assets/ai/h1-0123456789ab.mp4",
            "assets/ai/v1-0123456789ab.png",
            "inbox/clip.mp4",
            "out/pcos-demo-kyros.mp4",
            "out/pcos-demo-partner.MP4",
            "work/align.wav",
            "work/playback.m4a",
        ]

    def test_previews_drafts_and_overlay_layers_stay_local(self, tmp_path):
        """verify remakes previews, versions/ are superseded drafts, and
        overlay layers are only for hand-compositing — none is worth storage."""
        got = media.media_files(make_project(tmp_path))
        assert not [f for f in got if f.startswith(("out/previews", "out/versions",
                                                     "out/overlays"))]
        assert not [f for f in got if f.endswith("-overlay.mov")]

    def test_json_and_hidden_files_are_left_to_git(self, tmp_path):
        got = media.media_files(make_project(tmp_path))
        assert not [f for f in got if f.endswith(".json") or "/." in "/" + f]

    def test_missing_project_has_nothing(self, tmp_path):
        assert media.media_files(tmp_path / "nope") == []


class TestRemote:
    def test_default_is_the_r2_bucket(self, monkeypatch):
        monkeypatch.delenv("REELS_MEDIA_REMOTE", raising=False)
        assert media.remote_root() == "kyros-r2:kyros-reels"
        assert media.remote_for("pcos-demo") == "kyros-r2:kyros-reels/projects/pcos-demo"

    def test_any_rclone_remote_or_folder_can_stand_in(self, monkeypatch):
        monkeypatch.setenv("REELS_MEDIA_REMOTE", "gdrive:Kyros/Reels/")
        assert media.remote_for("x") == "gdrive:Kyros/Reels/projects/x"

    def test_named_remote_must_be_configured(self):
        assert media.remote_name("kyros-r2:kyros-reels") == "kyros-r2"
        assert media.remote_name("/Volumes/Backup/reels") is None
        assert media.configured("kyros-r2:kyros-reels", "gdrive:\nkyros-r2:\n")
        assert not media.configured("kyros-r2:kyros-reels", "gdrive:\n")
        assert media.configured("/Volumes/Backup/reels", "")

    def test_missing_rclone_says_how_to_install(self, monkeypatch):
        monkeypatch.setattr(media.shutil, "which", lambda _: None)
        assert "brew install rclone" in media.not_ready("kyros-r2:kyros-reels")

    def test_unconfigured_remote_points_at_the_setup(self, monkeypatch):
        monkeypatch.setattr(media.shutil, "which", lambda _: "/usr/bin/rclone")
        monkeypatch.setattr(media, "listremotes", lambda: "gdrive:\n")
        msg = media.not_ready("kyros-r2:kyros-reels")
        assert "kyros-r2" in msg and "docs/MEDIA.md" in msg


class TestOnlyEverAdds:
    def test_push_copies_and_never_deletes(self, tmp_path):
        argv = media.push_argv(tmp_path, "r:b/projects/x", tmp_path / "list.txt")
        assert argv[:2] == ["rclone", "copy"]
        assert "--files-from" in argv
        assert not [a for a in argv if a == "sync" or a == "move" or a.startswith("--delete")]

    def test_pull_never_overwrites_what_is_on_disk(self, tmp_path):
        argv = media.pull_argv("r:b/projects/x", tmp_path)
        assert argv[:2] == ["rclone", "copy"] and "--ignore-existing" in argv
        assert argv.index("r:b/projects/x") < argv.index(str(tmp_path))
        assert not [a for a in argv if a == "sync" or a == "move" or a.startswith("--delete")]

    def test_push_is_checked_file_by_file(self, tmp_path):
        argv = media.check_argv(tmp_path, "r:b/projects/x", tmp_path / "list.txt")
        assert argv[:2] == ["rclone", "check"] and "--one-way" in argv


class TestSlugs:
    def test_all_means_every_project_with_a_brief(self, tmp_path):
        make_project(tmp_path, "a")
        make_project(tmp_path, "b")
        (tmp_path / "scratch").mkdir()
        assert media.local_slugs("all", tmp_path) == ["a", "b"]

    def test_unknown_slug_stops(self, tmp_path):
        with pytest.raises(SystemExit):
            media.local_slugs("nope", tmp_path)


@pytest.mark.skipif(not HAS_RCLONE, reason="rclone not installed")
class TestRoundTrip:
    """A real rclone against a folder standing in for the bucket."""

    def test_push_then_pull_restores_a_deleted_clip(self, tmp_path, monkeypatch):
        projects, bucket = tmp_path / "projects", tmp_path / "bucket"
        p = make_project(projects)
        monkeypatch.setenv("REELS_MEDIA_REMOTE", str(bucket))

        assert media.push("pcos-demo", projects) == 0
        up = bucket / "projects/pcos-demo"
        assert (up / "inbox/clip.mp4").read_text() == "raw clip"
        assert not (up / "out/previews").exists() and not (up / "brief.json").exists()

        (p / "inbox/clip.mp4").unlink()
        assert media.pull("pcos-demo", projects) == 0
        assert (p / "inbox/clip.mp4").read_text() == "raw clip"

    def test_pull_leaves_newer_local_work_alone(self, tmp_path, monkeypatch):
        projects, bucket = tmp_path / "projects", tmp_path / "bucket"
        p = make_project(projects)
        monkeypatch.setenv("REELS_MEDIA_REMOTE", str(bucket))
        media.push("pcos-demo", projects)
        (p / "out/pcos-demo-kyros.mp4").write_text("re-rendered")
        media.pull("pcos-demo", projects)
        assert (p / "out/pcos-demo-kyros.mp4").read_text() == "re-rendered"

    def test_a_local_delete_never_reaches_the_bucket(self, tmp_path, monkeypatch):
        projects, bucket = tmp_path / "projects", tmp_path / "bucket"
        p = make_project(projects)
        monkeypatch.setenv("REELS_MEDIA_REMOTE", str(bucket))
        media.push("pcos-demo", projects)
        (p / "inbox/clip.mp4").unlink()
        assert media.push("pcos-demo", projects) == 0
        assert (bucket / "projects/pcos-demo/inbox/clip.mp4").exists()

    def test_pull_all_brings_back_every_project_in_the_bucket(self, tmp_path, monkeypatch):
        projects, bucket = tmp_path / "projects", tmp_path / "bucket"
        make_project(projects, "a")
        make_project(projects, "b")
        monkeypatch.setenv("REELS_MEDIA_REMOTE", str(bucket))
        assert media.push("all", projects) == 0
        fresh = tmp_path / "fresh-clone"
        assert media.pull("all", fresh) == 0
        assert (fresh / "a/inbox/clip.mp4").exists() and (fresh / "b/inbox/clip.mp4").exists()

    def test_cli_wires_push_and_pull(self, tmp_path):
        env = dict(os.environ, REELS_MEDIA_REMOTE=str(tmp_path / "bucket"))
        r = subprocess.run([sys.executable, str(ROOT / "scripts/reels.py"), "pull",
                            "no-such-slug-anywhere"], env=env, capture_output=True, text=True)
        assert r.returncode != 0 and "no-such-slug-anywhere" in (r.stdout + r.stderr)


class TestGitHoldsNoMedia:
    """The .gitignore is the only thing between a render and a 2.6 GB repo."""

    def ignored(self, path):
        return subprocess.run(["git", "check-ignore", "-q", "--no-index", path],
                              cwd=ROOT).returncode == 0

    @pytest.mark.parametrize("path", [
        "projects/x/inbox/clip.mp4", "projects/x/inbox/clip.MOV",
        "projects/x/assets/ai/v1-0123456789ab.png", "projects/x/assets/ai/h1-0123456789ab.mp4",
        "projects/x/out/x-kyros.mp4", "projects/x/out/previews/x-kyros-v1.jpg",
        "projects/x/work/playback.m4a", "projects/x/work/align.wav",
        "studio/public/video.mp4", "studio/public/ai/v1.png",
    ])
    def test_media_is_ignored(self, path):
        assert self.ignored(path)

    @pytest.mark.parametrize("path", [
        "brand/kyros/outro.mp4", "brand/doctors/bharani-bellam/plate.png",
        "brand/partners/aster-ramesh/logo.png",
        "projects/x/assets/ai/v1-0123456789ab.json", "projects/x/brief.json",
        "projects/x/work/captions_data.json", "scripts/media.py",
    ])
    def test_code_briefs_sidecars_and_brand_are_kept(self, path):
        assert not self.ignored(path)

    def test_nothing_heavy_is_tracked(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True).stdout.split("\n")
        heavy = [f for f in tracked if Path(f).suffix.lower() in media.MEDIA_EXT
                 and not f.startswith("brand/")]
        assert heavy == []
