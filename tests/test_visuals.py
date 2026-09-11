"""Supporting visuals — planning, the generation cache, placement, verify.

The doctor is the reel. A generated visual only ever shows what she is saying
at that moment, as realistically as possible, and it is a hazard like any
burned-in graphic: it has a window and a rectangle, and the captions, the
plate, the mark and the doctor bubble all answer to it.

Nothing here calls Modal. Generation goes through a fake runner that writes
real (tiny) media with ffmpeg, so the cache, metadata, failure and verify
paths are exercised end to end; `TestToolkitCommand` pins the command line the
real runner hands to the toolkit instead."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import build_captions as bc
import register
import visuals as vz
from conftest import ROOT, SHIPPED

FPS = 30
VIDEO_FRAMES = 420          # a 14s take
ANSWER_START = 90           # beat 1's first word, 3.0s
QUESTION_END = 84


def word_list(n=40, t0=1.0, step=0.5):
    out = []
    for i in range(n):
        s = t0 + i * step
        e = s + 0.4
        out.append({"word": f"w{i}", "start": s, "end": e,
                    "startFrame": round(s * FPS), "endFrame": round(e * FPS)})
    return out


WORDS = word_list()
# Five beats, two seconds each: beat n starts at frame 90 + 60*(n-1).
SPECS = [{"lead": [4 + 4 * i, 5 + 4 * i], "key": [6 + 4 * i, 7 + 4 * i],
          "lines": [f"BEAT {i + 1}"]} for i in range(5)]


def visual(vid, beat, treatment="doctorBubble", mode="image", status="approved",
           prompt=None, **kw):
    v = {"id": vid, "beat": beat, "treatment": treatment, "mode": mode,
         "status": status,
         "prompt": prompt or f"A woman in her thirties walks briskly along a "
                             f"tree-lined park path at sunrise, beat {beat}",
         "_why": "she names the action on this beat"}
    v.update(kw)
    return v


def resolve(beats, top_win=None, asset_seconds=None):
    return vz.resolve_timing(beats, SPECS, WORDS, VIDEO_FRAMES, ANSWER_START,
                             QUESTION_END, top_win=top_win or [],
                             asset_seconds=asset_seconds or {})


def make_project(tmp_path, beats, name="clip-a", enabled=True):
    p = tmp_path / name
    (p / "work").mkdir(parents=True)
    brief = {"slug": name, "clip": "inbox/x.mp4", "doctor": "bharani-bellam",
             "chunks": SPECS,
             "visuals": {"enabled": enabled, "style": "naturalLight",
                         "bubbleShape": "circle", "beats": beats}}
    (p / "brief.json").write_text(json.dumps(brief, indent=2))
    (p / "work" / "words.json").write_text(json.dumps({"words": WORDS}))
    (p / "work" / "clip.json").write_text(json.dumps(
        {"frames30": VIDEO_FRAMES, "width": 1080, "height": 1920}))
    return p


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


class FakeRunner:
    """Stands in for the toolkit: writes real media of the requested size, or
    fails the way a Modal call fails."""

    def __init__(self, fail=False, empty=False, elapsed=10.0):
        self.fail, self.empty, self.elapsed = fail, empty, elapsed
        self.calls = []

    def available(self, tool):
        return True, ""

    def run(self, tool, request, out_path):
        out_path = Path(out_path)
        self.calls.append((tool, request, out_path))
        if self.fail:
            return {"ok": False, "elapsedSec": 2.0,
                    "error": "Modal endpoint is scaling up or unavailable"}
        if self.empty:
            out_path.write_bytes(b"")
            return {"ok": True, "elapsedSec": self.elapsed, "error": None}
        w, h = request["width"], request["height"]
        if vz.TOOLS[tool]["kind"] == "video":
            n = request["numFrames"]
            # LTX-2 generates its own soundtrack; the fake does too, so the
            # test proves the pipeline strips it.
            ffmpeg("-f", "lavfi", "-i", f"testsrc=s={w}x{h}:r=24",
                   "-f", "lavfi", "-i", "sine=f=440:r=48000",
                   "-frames:v", str(n), "-shortest", "-c:v", "libx264",
                   "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", str(out_path))
        else:
            ffmpeg("-f", "lavfi", "-i", f"color=c=0xE6BE9B:s={w}x{h}",
                   "-frames:v", "1", str(out_path))
        return {"ok": True, "elapsedSec": self.elapsed, "error": None}


def brief_of(p):
    return json.loads((p / "brief.json").read_text())


def manifest_of(p):
    return json.loads((p / "work" / "visuals.json").read_text())


# ---------------------------------------------------------------------------
class TestOffByDefault:
    """Absent `visuals`, nothing new runs. Six shipped reels share this
    pipeline; they must rebuild to the same bytes they always did."""

    def test_no_visuals_block_resolves_to_nothing(self, tmp_path):
        assert vz.enabled({}) is False
        assert vz.enabled({"visuals": {"enabled": False,
                                       "beats": [visual("v1", 2)]}}) is False
        assert vz.enabled({"visuals": {"enabled": True, "beats": []}}) is False

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_shipped_clips_carry_no_visuals(self, slug, briefs, shipped):
        assert "visuals" not in briefs[slug]
        assert "visuals" not in shipped[slug]

    def test_the_plate_solver_is_unchanged_without_extra_hazards(self, tmp_path):
        a = solve_plate(tmp_path, extra=None)
        b = solve_plate(tmp_path, extra=[])
        assert a == b

    @pytest.mark.skipif(not os.environ.get("KYROS_SLOW"),
                        reason="rebuilds every project (~1 min); KYROS_SLOW=1")
    def test_every_project_rebuilds_byte_identical(self, tmp_path):
        golden = json.loads((ROOT / "tests/fixtures/rebuild_md5.json").read_text())
        for slug, want in golden.items():
            got = rebuild_md5(tmp_path, slug)
            assert got == want, f"{slug}: rebuild {got} != golden {want}"


def rebuild_md5(tmp_path, slug):
    src = ROOT / "projects" / slug
    clip = json.loads((src / "work" / "clip.json").read_text())["clip"]
    if not Path(clip).exists():
        # Without the take every footage measurement (chin, mark, plate)
        # silently comes back empty and the hash differs for that reason
        # alone — which says nothing about the code.
        pytest.skip(f"{slug}: source clip missing ({clip})")
    t = tmp_path / slug
    (t / "work").mkdir(parents=True)
    shutil.copy(src / "brief.json", t / "brief.json")
    for j in (src / "work").glob("*.json"):
        if j.name != "captions_data.json":
            shutil.copy(j, t / "work" / j.name)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_captions.py"), str(t)],
                   check=True, capture_output=True, cwd=ROOT)
    return hashlib.md5((t / "work/captions_data.json").read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
class TestTiming:
    def test_one_image_visual_takes_its_beat(self):
        items, _ = resolve([visual("v1", 2)])
        assert len(items) == 1
        it = items[0]
        assert (it["fromFrame"], it["toFrame"]) == (150, 210)
        assert it["kind"] == "image" and it["treatment"] == "doctorBubble"

    def test_one_video_visual_never_outlasts_its_clip(self):
        items, _ = resolve([visual("v1", 2, mode="video")],
                           asset_seconds={"v1": 1.5})
        it = items[0]
        assert it["kind"] == "video"
        assert it["toFrame"] - it["fromFrame"] <= 45

    def test_multiple_visuals_are_sorted_and_never_overlap(self):
        items, _ = resolve([visual("v2", 4), visual("v1", 1, treatment="inset")])
        assert [i["id"] for i in items] == ["v1", "v2"]
        for a, b in zip(items, items[1:]):
            assert a["toFrame"] <= b["fromFrame"]

    def test_the_doctor_returns_between_two_full_frame_visuals(self):
        """Back-to-back full-frame visuals would take her face away for four
        seconds straight. She pops back up for at least 1.5s in between."""
        items, report = resolve([visual("v1", 1), visual("v2", 2)])
        assert [i["id"] for i in items] == ["v1"]
        assert any("v2" in line and "doctor" in line for line in report)
        items, _ = resolve([visual("v1", 1), visual("v2", 3)])
        assert [i["id"] for i in items] == ["v1", "v2"]
        assert items[1]["fromFrame"] - items[0]["toFrame"] >= vz.DOCTOR_RETURN_FRAMES

    def test_an_inset_does_not_need_the_doctor_to_return(self):
        """She stays full-frame under an inset card, so nothing is taken away."""
        items, _ = resolve([visual("v1", 1), visual("v2", 2, treatment="inset")])
        assert [i["id"] for i in items] == ["v1", "v2"]

    @pytest.mark.parametrize("treatment", ["cutaway", "doctorBubble", "inset"])
    def test_every_treatment_is_clamped_to_its_budget(self, treatment):
        items, _ = resolve([visual("v1", None, treatment=treatment, at=[3.0, 13.0])])
        dur = (items[0]["toFrame"] - items[0]["fromFrame"]) / FPS
        assert dur <= vz.MAX_SECONDS[treatment] + 1e-6

    def test_a_cutaway_is_short(self):
        assert vz.MAX_SECONDS["cutaway"] <= 2.5

    def test_nothing_covers_the_question_except_a_hook_backdrop(self):
        items, _ = resolve([visual("v1", None, at=[0.5, 5.0])])
        assert items[0]["fromFrame"] >= ANSWER_START
        items, _ = resolve([visual("hb", None, treatment="hookBackdrop")])
        assert (items[0]["fromFrame"], items[0]["toFrame"]) == (0, QUESTION_END)

    def test_she_is_on_screen_for_at_least_half_the_answer(self):
        beats = [visual("v1", 1, at=[3.0, 8.9]), visual("v2", None, at=[10.5, 13.5])]
        items, report = resolve(beats)
        away = sum(i["toFrame"] - i["fromFrame"] for i in items
                   if i["treatment"] in vz.FULL_FRAME)
        assert away <= vz.MAX_AWAY_SHARE * (VIDEO_FRAMES - ANSWER_START)

    def test_too_short_a_window_is_dropped_not_flashed(self):
        items, report = resolve([visual("v1", None, at=[5.0, 5.5])])
        assert items == []
        assert any("v1" in line for line in report)

    def test_a_beat_already_carried_by_a_burned_in_graphic_gets_no_visual(self):
        """When the footage already shows a graphic, a generated visual
        competes with it. Same rule that skips a caption under a graphic."""
        items, report = resolve([visual("v1", 2)], top_win=[[140, 215]])
        assert items == []
        assert any("burned-in graphic" in line for line in report)

    def test_unapproved_visuals_never_reach_the_timeline(self):
        items, _ = resolve([visual("v1", 2, status="proposed"),
                            visual("v2", 4, status="rejected")])
        assert items == []


# ---------------------------------------------------------------------------
class TestRequestsAndCache:
    def test_the_request_hash_is_stable(self):
        v = visual("v1", 2)
        assert vz.request_hash(vz.request_for(v)) == vz.request_hash(vz.request_for(dict(v)))

    def test_a_changed_prompt_is_a_new_request(self):
        a = vz.request_for(visual("v1", 2, prompt="a bicycle leaning on a wall"))
        b = vz.request_for(visual("v1", 2, prompt="a bicycle on a quiet lane"))
        assert vz.request_hash(a) != vz.request_hash(b)

    def test_moving_a_visual_to_another_beat_does_not_regenerate(self):
        a = vz.request_for(visual("v1", 2))
        b = vz.request_for(dict(visual("v1", 2), beat=4, id="v9", motion="panLeft"))
        assert vz.request_hash(a) == vz.request_hash(b)

    def test_the_default_seed_is_deterministic(self):
        v = visual("v1", 2)
        assert vz.request_for(v)["seed"] == vz.request_for(v)["seed"]

    def test_flux_sizes_are_multiples_of_16_and_near_2mp(self):
        for t in ("doctorBubble", "cutaway", "inset", "hookBackdrop"):
            r = vz.request_for(visual("v1", 2, treatment=t))
            assert r["width"] % 16 == 0 and r["height"] % 16 == 0
            assert r["width"] * r["height"] <= 2.2e6

    def test_ltx_sizes_and_frame_counts_are_legal(self):
        r = vz.request_for(visual("v1", 2, mode="video"))
        assert r["width"] % 64 == 0 and r["height"] % 64 == 0
        assert (r["numFrames"] - 1) % 8 == 0 and 25 <= r["numFrames"] <= 121
        assert r["negative"]

    @pytest.mark.parametrize("seconds", [1.0, 2.2, 4.0, 5.0, 9.0])
    def test_ltx_frames_cover_the_window(self, seconds):
        n = vz.ltx_frames(seconds)
        assert (n - 1) % 8 == 0
        assert n >= min(121, seconds * 24)

    def test_full_frame_is_vertical(self):
        r = vz.request_for(visual("v1", 2))
        assert r["height"] > r["width"]

    def test_a_cached_asset_is_reused_without_a_gpu_call(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        runner = FakeRunner()
        first = vz.generate(p, runner, log=lambda *a: None)
        second = vz.generate(p, runner, log=lambda *a: None)
        assert len(runner.calls) == 1
        assert first["images"] == 1 and second["reused"] == 1
        assert second["costUsd"] == 0

    def test_a_request_generated_for_another_clip_is_reused(self, tmp_path):
        same = "A rolled yoga mat by a sunlit window in a Hyderabad apartment"
        a = make_project(tmp_path, [visual("v1", 2, prompt=same)], name="clip-a")
        b = make_project(tmp_path, [visual("v7", 3, prompt=same)], name="clip-b")
        runner = FakeRunner()
        vz.generate(a, runner, log=lambda *a: None)
        vz.generate(b, runner, log=lambda *a: None)
        assert len(runner.calls) == 1
        assert list((b / "assets" / "ai").glob("*.png"))

    def test_a_changed_prompt_makes_a_new_file_and_keeps_the_old(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2, prompt="a rolled yoga mat")])
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        old = sorted((p / "assets/ai").glob("*.png"))
        b = brief_of(p)
        b["visuals"]["beats"][0]["prompt"] = "a rolled yoga mat by a sunny window"
        (p / "brief.json").write_text(json.dumps(b))
        vz.generate(p, runner, log=lambda *a: None)
        new = sorted((p / "assets/ai").glob("*.png"))
        assert len(runner.calls) == 2
        assert set(old) < set(new)

    def test_a_rejected_picture_never_stands_in_for_its_replacement(self, tmp_path):
        """v3 on pcos-best-exercise: the first gym still was rejected and
        re-prompted. Until the new one exists, the build must show footage —
        not quietly fall back to the picture that was just rejected."""
        p = make_project(tmp_path, [visual("v1", 2, prompt="a woman doing a plank")])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        assert "v1" in vz.ready_assets(p)[0]
        b = brief_of(p)
        b["visuals"]["beats"][0]["prompt"] = "a woman doing a standing dumbbell curl"
        (p / "brief.json").write_text(json.dumps(b))
        ready, report = vz.ready_assets(p)
        assert "v1" not in ready
        assert any("v1" in line and "changed" in line for line in report)
        assert "$0 (cached)" not in vz.plan_text(p)

    def test_nothing_is_ever_overwritten(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        f = next((p / "assets/ai").glob("*.png"))
        before = f.read_bytes()
        vz.generate(p, FakeRunner(), log=lambda *a: None, retry=True)
        assert f.read_bytes() == before

    def test_generated_video_carries_no_soundtrack(self, tmp_path):
        """Her voice is the only audio. LTX-2 invents one; it is stripped."""
        p = make_project(tmp_path, [visual("v1", 2, mode="video", treatment="inset",
                                           aspect="1:1")])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        f = next((p / "assets/ai").glob("*.mp4"))
        streams = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(f)]).decode().split()
        assert streams == ["video"]


# ---------------------------------------------------------------------------
class TestHDAndLength:
    """Niranjan, after the pilot: HD is enough for a supporting visual — it
    sits under captions in a 1080x1920 master — and a video should be only as
    long as the beat it serves. Both halve the GPU bill."""

    def test_new_reels_generate_at_hd(self):
        full = vz.request_for(visual("v1", 2))
        inset = vz.request_for(visual("v1", 2, treatment="inset"))
        assert (full["width"], full["height"]) == (720, 1280)
        assert (inset["width"], inset["height"]) == (1024, 576)
        for r in (full, inset):
            assert max(r["width"], r["height"]) <= 1280
            assert r["width"] % 16 == 0 and r["height"] % 16 == 0

    def test_hd_video_is_576x1024_and_as_long_as_its_beat(self):
        short = vz.request_for(visual("v1", 2, mode="video"), seconds=2.0)
        assert (short["width"], short["height"]) == (576, 1024)
        assert short["numFrames"] == vz.ltx_frames(2.0 + vz.VIDEO_PAD_SECONDS)
        assert short["numFrames"] < 121
        assert vz.request_for(visual("v1", 2, mode="video"), seconds=6.0)["numFrames"] == 121

    def test_full_quality_keeps_the_pilots_requests_byte_stable(self):
        """pcos-best-exercise was generated before HD existed. Its pictures
        are keyed by request hash; if "full" drifted, every one of them would
        read as stale and the pilot would silently rebuild as footage."""
        p = ROOT / "projects" / "pcos-best-exercise" / "brief.json"
        if not p.exists():
            pytest.skip("pilot not present")
        beats = {b["id"]: b for b in json.loads(p.read_text())["visuals"]["beats"]}
        v2 = beats["v2"]
        assert vz.request_hash(vz.request_for(v2, beats, quality="full")) == v2["approvedHash"]
        v4 = vz.request_for(beats["v4"], beats, quality="full", seconds=2.0)
        assert v4["numFrames"] == 121 and (v4["width"], v4["height"]) == (768, 1344)

    def test_generation_sends_the_beats_length_for_video(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2, mode="video", treatment="inset",
                                           aspect="1:1")])
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        assert runner.calls[0][1]["numFrames"] == vz.ltx_frames(2.0 + vz.VIDEO_PAD_SECONDS)


# ---------------------------------------------------------------------------
class TestListBuild:
    """The pilot's worst miss: she named four exercises and the reel showed
    one swimmer. A spoken list shows every item, each landing on its own word,
    building up until all of them are on screen together."""

    def members(self, words=(8, 9, 10, 11), beat=2):
        return [visual(f"s{i}", beat, treatment="listBuild", group="g1", word=w,
                       label=f"ITEM {i}", prompt=f"A woman doing exercise {i}")
                for i, w in enumerate(words)]

    def test_each_item_lands_on_its_word_and_all_hold_to_the_end(self):
        items, _ = resolve(self.members())
        assert [i["id"] for i in items] == ["s0", "s1", "s2", "s3"]
        assert [i["fromFrame"] for i in items] == [WORDS[w]["startFrame"] for w in (8, 9, 10, 11)]
        assert {i["toFrame"] for i in items} == {210}
        assert {i["group"] for i in items} == {"g1"}

    def test_the_group_counts_once_against_her_screen_time(self):
        items, report = resolve(self.members())
        assert len(items) == 4, report

    def test_the_doctor_returns_between_a_list_and_another_full_frame_visual(self):
        items, report = resolve(self.members() + [visual("v9", 3)])
        assert "v9" not in [i["id"] for i in items]
        assert any("v9" in line and "doctor" in line for line in report)

    @pytest.mark.parametrize("n", [1, 2, 3, 5])
    def test_an_item_pops_out_over_its_own_tile_and_leaves_the_others_visible(self, n):
        """pcos-blood-tests, first render: every item arrived over the WHOLE
        stage, hiding each tile already placed — the grid only appeared in the
        last second. An item now arrives larger over its own tile only."""
        region = (48, 300, 1032, 1168)
        tiles = vz.list_tiles(n, region)
        for t in tiles:
            pop = vz.pop_rect(t, region)
            assert pop[0] <= t[0] and pop[1] <= t[1] and pop[2] >= t[2] and pop[3] >= t[3]
            assert region[0] <= pop[0] and pop[2] <= region[2]
            assert region[1] <= pop[1] and pop[3] <= region[3]
            if n > 1:
                assert (pop[2] - pop[0]) * (pop[3] - pop[1]) < 0.8 * (
                    (region[2] - region[0]) * (region[3] - region[1]))

    @pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
    def test_tiles_fill_the_region_without_overlapping(self, n):
        region = (48, 300, 1032, 1160)
        tiles = vz.list_tiles(n, region)
        assert len(tiles) == n
        for t in tiles:
            assert region[0] <= t[0] < t[2] <= region[2]
            assert region[1] <= t[1] < t[3] <= region[3]
        for i, a in enumerate(tiles):
            for b in tiles[i + 1:]:
                assert not bc.rect_overlap(a, b)


# ---------------------------------------------------------------------------
class TestHookSequence:
    """The first three seconds decide whether anyone stays. The question
    opens on pictures of what it asks about — never a blank card — and they
    can run as a short sequence, all inside the question."""

    def test_hook_pictures_run_in_sequence_inside_the_question(self):
        beats = [visual("h1", None, treatment="hookBackdrop", at=[0.0, 1.3]),
                 visual("h2", None, treatment="hookBackdrop", at=[1.3, 9.0])]
        items, _ = resolve(beats)
        h1, h2 = items
        assert (h1["fromFrame"], h1["toFrame"]) == (0, 39)
        assert h2["fromFrame"] == 39 and h2["toFrame"] == QUESTION_END

    def test_a_hook_never_reaches_into_the_answer(self):
        items, _ = resolve([visual("h1", None, treatment="hookBackdrop", at=[0.0, 20.0])])
        assert items[0]["toFrame"] <= QUESTION_END


# ---------------------------------------------------------------------------
class TestApproval:
    def test_only_approved_visuals_generate(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 1), visual("v2", 3, status="proposed"),
                                    visual("v3", 5, status="rejected")])
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        assert [c[1]["prompt"] for c in runner.calls] == [visual("v1", 1)["prompt"]]

    def test_approve_all_leaves_review_items_for_an_explicit_yes(self, tmp_path):
        p = make_project(tmp_path, [
            visual("v1", 1, status="proposed"),
            visual("v2", 3, status="proposed",
                   prompt="Realistic 3D medical visualisation of an ovary with "
                          "small follicles, soft studio light"),
        ])
        vz.approve(p, "all")
        st = {b["id"]: b["status"] for b in brief_of(p)["visuals"]["beats"]}
        assert st == {"v1": "approved", "v2": "proposed"}
        vz.approve(p, ["v2"])
        st = {b["id"]: b["status"] for b in brief_of(p)["visuals"]["beats"]}
        assert st["v2"] == "approved"

    def test_a_blocked_prompt_can_never_be_approved(self, tmp_path):
        p = make_project(tmp_path, [visual(
            "v1", 1, status="proposed",
            prompt="Before and after photos of a woman's weight loss")])
        vz.approve(p, ["v1"])
        assert brief_of(p)["visuals"]["beats"][0]["status"] == "proposed"
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        assert runner.calls == []

    def test_editing_an_approved_prompt_needs_approval_again(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 1, status="proposed")])
        vz.approve(p, ["v1"])
        b = brief_of(p)
        b["visuals"]["beats"][0]["prompt"] += ", seen from above"
        (p / "brief.json").write_text(json.dumps(b))
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        assert runner.calls == []
        assert "approval" in manifest_of(p)["items"]["v1"]["reason"]

    def test_reject_is_skip(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 1)])
        vz.reject(p, ["v1"])
        assert brief_of(p)["visuals"]["beats"][0]["status"] == "rejected"


# ---------------------------------------------------------------------------
class TestFailure:
    """Generation is allowed to fail. The reel is not."""

    def test_a_failed_call_is_never_counted_as_generation_cost(self, tmp_path):
        """pcos-best-exercise, v4: the video app crash-looped for 25 minutes.
        Wall-clock × the A100 rate said $1.04; Modal billed $0.15. A failure's
        time is mostly waiting, so it is reported apart, as an upper bound."""
        p = make_project(tmp_path, [visual("v1", 2), visual("v2", 4)])
        vz.generate(p, FakeRunner(elapsed=10.0), log=lambda *a: None, only=["v1"])
        vz.generate(p, FakeRunner(fail=True), log=lambda *a: None, only=["v2"])
        text = vz.summary_text(p)
        ok = 10.0 * vz.TOOLS["flux2"]["usdPerSec"]
        assert f"Estimated GPU generation cost: ${ok:.4f}" in text
        assert "Failed calls: up to" in text and "upper bound" in text

    def test_a_failure_is_recorded_with_its_reason(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        s = vz.generate(p, FakeRunner(fail=True), log=lambda *a: None)
        m = manifest_of(p)["items"]["v1"]
        assert s["failed"] == 1
        assert m["status"] == "failed" and "unavailable" in m["error"]
        assert not list((p / "assets" / "ai").glob("*.png"))

    def test_failures_are_retried_only_when_asked(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(fail=True), log=lambda *a: None)
        runner = FakeRunner()
        vz.generate(p, runner, log=lambda *a: None)
        assert runner.calls == []
        vz.generate(p, runner, log=lambda *a: None, retry=True)
        assert len(runner.calls) == 1
        assert manifest_of(p)["items"]["v1"]["status"] == "complete"

    def test_a_zero_byte_result_is_a_failure(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(empty=True), log=lambda *a: None)
        assert manifest_of(p)["items"]["v1"]["status"] == "failed"
        assert not list((p / "assets" / "ai").glob("*.png"))

    def test_a_failed_visual_is_left_out_and_the_reel_still_builds(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2), visual("v2", 4)])
        vz.generate(p, FakeRunner(fail=True), log=lambda *a: None, only=["v1"])
        vz.generate(p, FakeRunner(), log=lambda *a: None, only=["v2"])
        ready, report = vz.ready_assets(p)
        assert set(ready) == {"v2"}
        assert any("v1" in line and "footage" in line for line in report)

    def test_a_missing_endpoint_fails_fast_and_names_the_fix(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MODAL_FLUX2_ENDPOINT_URL", raising=False)
        runner = vz.ToolkitRunner(toolkit_dir=tmp_path / "toolkit")
        ok, why = runner.available("flux2")
        assert not ok and "MODAL_FLUX2_ENDPOINT_URL" in why
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, runner, log=lambda *a: None)
        assert "MODAL_FLUX2_ENDPOINT_URL" in manifest_of(p)["items"]["v1"]["error"]


# ---------------------------------------------------------------------------
class TestMetadata:
    FIELDS = ["assetId", "type", "provider", "tool", "model", "prompt", "negative",
              "width", "height", "seed", "requestHash", "visualIds", "sourceBeats",
              "slug", "why", "createdAt", "elapsedSec", "costEstimateUsd",
              "costBasis", "status", "file"]

    def test_every_asset_has_a_complete_sidecar(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        side = next((p / "assets/ai").glob("*.json"))
        meta = json.loads(side.read_text())
        missing = [k for k in self.FIELDS if k not in meta]
        assert not missing, missing
        assert meta["provider"] == "modal" and meta["status"] == "complete"
        assert meta["sourceBeats"] == [2] and meta["visualIds"] == ["v1"]
        assert meta["requestHash"][:12] in meta["file"]

    def test_the_cost_estimate_uses_the_gpu_it_ran_on(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(elapsed=10.0), log=lambda *a: None)
        meta = json.loads(next((p / "assets/ai").glob("*.json")).read_text())
        assert meta["costEstimateUsd"] == pytest.approx(10.0 * vz.TOOLS["flux2"]["usdPerSec"])
        assert "estimate" in meta["costBasis"]

    def test_the_summary_counts_what_happened(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 1), visual("v2", 3, mode="video",
                                                           treatment="inset", aspect="1:1")])
        s = vz.generate(p, FakeRunner(), log=lambda *a: None)
        assert (s["images"], s["videos"], s["reused"], s["failed"]) == (1, 1, 0, 0)
        text = vz.summary_text(p)
        assert "Images: 1" in text and "Videos: 1" in text and "Estimated" in text


# ---------------------------------------------------------------------------
class TestSafetyLint:
    """Show what she says. Never what she didn't — no invented results,
    records, testimonials, or clinicians."""

    @pytest.mark.parametrize("prompt", [
        "Before and after photos of a woman's weight loss",
        "A woman's body transformation after twelve weeks",
        "A lab report showing normal hormone levels",
        "A prescription pad with dosage written on it",
        "An MRI scan result of a patient's ovaries",
        "A smiling patient giving a five-star testimonial",
        "A doctor in a white coat with a stethoscope explaining",
    ])
    def test_invented_evidence_is_blocked(self, prompt):
        assert vz.risk(vz.lint_prompt(prompt)) == "blocked"

    @pytest.mark.parametrize("prompt", [
        "Realistic 3D medical visualisation of an ovary with small follicles",
        "Unbranded white tablets in a small glass dish",
    ])
    def test_anatomy_and_medicine_need_an_explicit_yes(self, prompt):
        assert vz.risk(vz.lint_prompt(prompt)) == "review"

    @pytest.mark.parametrize("prompt", [
        "A woman in her thirties walks briskly along a tree-lined park path at "
        "sunrise, candid documentary photograph, natural light",
        "Close-up of a step counter on a woman's wrist as she walks",
    ])
    def test_everyday_reality_is_low_risk(self, prompt):
        assert vz.risk(vz.lint_prompt(prompt)) == "low"

    def test_text_in_an_image_is_flagged(self):
        levels = {f["level"] for f in vz.lint_prompt('A sign that says "10,000 STEPS"')}
        assert levels & {"warn", "review", "blocked"}


# ---------------------------------------------------------------------------
def plate_layout():
    layout = bc.deep_merge(bc.LAYOUT, {})
    layout["doctorPlate"].update({"fileWidth": 900, "fileHeight": 200, "pillX": 20,
                                  "pillY": 40, "pillWidth": 860, "pillHeight": 120})
    return layout


def chunks_top():
    return [{"id": f"chunk-{i+1}", "zone": "top", "fromFrame": 90 + 60 * i,
             "toFrame": 150 + 60 * i} for i in range(5)]


def solve_plate(tmp_path, extra):
    layout = plate_layout()
    clip = {"clip": str(tmp_path / "missing.mp4"), "frames30": VIDEO_FRAMES,
            "height": 1920}
    f0, ok, _ = bc.solve_doctor_plate({}, layout, layout["captionScrim"], chunks_top(),
                                      [], tmp_path, clip, bc.THEME["motion"],
                                      extra_hazards=extra)
    return f0, ok, layout["doctorPlate"]["top"], layout["doctorPlate"]["holdFrames"]


class TestHazards:
    def test_an_inset_sends_that_beats_caption_low(self):
        items, _ = resolve([visual("v1", 2, treatment="inset")])
        block = vz.top_block_windows(items)
        assert bc.auto_zone({}, 150, 210, 160, block) == "bottom"
        assert bc.auto_zone({}, 270, 330, 280, block) == "top"

    def test_a_full_frame_visual_does_not_move_captions(self):
        items, _ = resolve([visual("v1", 2)])
        assert vz.top_block_windows(items) == []

    def test_the_plate_never_appears_while_she_is_off_screen(self, tmp_path):
        """The plate names the doctor. It belongs to frames where she is the
        picture, never over a cutaway or while she is in the bubble."""
        base_f0, *_ = solve_plate(tmp_path, extra=None)
        assert base_f0 == ANSWER_START
        items, _ = resolve([visual("v1", 1, at=[3.0, 8.0])])
        f0, ok, *_ = solve_plate(tmp_path, extra=vz.plate_hazards(items))
        assert ok and f0 >= items[0]["toFrame"]

    def test_an_inset_only_blocks_the_plate_where_they_meet(self, tmp_path):
        items, _ = resolve([visual("v1", 1, treatment="inset")])
        items[0]["rect"] = [70, 300, 1010, 760]
        f0, ok, *_ = solve_plate(tmp_path, extra=vz.plate_hazards(items))
        assert ok and f0 == ANSWER_START      # the low plate never meets a wall card

    def test_the_mark_steps_aside_for_an_inset_under_it(self, tmp_path):
        layout = plate_layout()
        clip = {"clip": str(tmp_path / "missing.mp4"), "frames30": VIDEO_FRAMES,
                "height": 1920}
        inset = ("AI visual v1 (inset)", (0, 700, 1080, 950), [(150, 210)])
        name, logo, hide = bc.solve_mark_anchor(
            {}, layout, layout["captionScrim"], chunks_top(), None, (0, 0), clip, [],
            120, VIDEO_FRAMES, bc.THEME["motion"], extra_hazards=[inset])
        rect = (bc.WIDTH - logo["right"] - logo["width"], logo["y"],
                bc.WIDTH - logo["right"], logo["y"] + logo["width"] * 0.42)
        assert (not bc.rect_overlap(rect, inset[1])
                or bc.occupied_frac(hide, 150, 210) == 1.0)

    def test_the_bubble_never_covers_the_mark_or_a_live_caption(self):
        mark = ("mark", (784, 778, 1042, 886), [(0, VIDEO_FRAMES)])
        top_caption = ("top caption", (0, 268, 1080, 754), [(150, 210)])
        got = vz.solve_bubble((150, 210), [mark, top_caption])
        assert got["ok"]
        assert not bc.rect_overlap(got["rect"], mark[1])
        assert not bc.rect_overlap(got["rect"], top_caption[1])

    def test_the_bubble_moves_up_when_the_caption_is_low(self):
        low_caption = ("bottom caption", (0, 1150, 1080, 1580), [(150, 210)])
        got = vz.solve_bubble((150, 210), [low_caption])
        assert got["ok"] and got["rect"][3] <= 1150

    def test_the_bubble_stays_inside_the_platform_safe_area(self):
        for corner, rect in vz.bubble_candidates(340).items():
            ok = vz.inside_safe_area(rect)
            if corner == "lower-right":
                assert not ok, "the like/comment column sits there"
            else:
                assert ok, corner

    def test_the_bubble_frames_her_face(self):
        crop = vz.bubble_crop((430, 830, 650, 1080))
        assert 430 < crop["cx"] < 650 and 830 < crop["cy"] < 1080
        assert crop["r"] >= 0.6 * (1080 - 830)

    def test_an_inset_card_sits_on_the_wall_above_her_head(self):
        r = vz.inset_rect(815, bc.LAYOUT, "16:9")
        x0, y0, x1, y1 = r
        assert x0 >= 60 and x1 <= 1020 and y0 >= 288 and y1 <= 815 - 30
        assert abs((x1 - x0) / (y1 - y0) - 16 / 9) < 0.02

    def test_no_room_on_the_wall_means_no_inset(self):
        assert vz.inset_rect(420, bc.LAYOUT, "16:9") is None

    def test_captions_over_a_dark_visual_get_a_ground(self):
        assert vz.wash_for(["#2A1B10"], ["#1A1A1A", "#202020"]) is not None
        assert vz.wash_for(["#2A1B10"], ["#F0E6D8", "#EADFCC"]) is None

    def _chunk(self, zone, a, b, key, lead):
        return {"id": f"c-{zone}-{a}", "zone": zone, "fromFrame": a, "toFrame": b,
                "keyColor": key, "leadColor": lead, "keyLines": ["A", "B"],
                "keySize": 145, "leadWords": [1], "leadSize": 70}

    def test_a_caption_ground_is_per_caption_and_never_spans_both_zones(self):
        """pcos-best-exercise, 20.7s: a light low caption fading out and a dark
        top caption were pooled into one decision — the dark one won, and a
        dark veil covered the frame from y=208 to y=1640, burying the dark
        '8–10,000 STEPS' it was meant to rescue."""
        layout = bc.LAYOUT
        top = self._chunk("top", 150, 240, "#7A4E1C", "#7A4E1C")
        low = self._chunk("bottom", 60, 155, "#FFF6E8", "#FFF6E8")

        def dark_picture(box, at):
            return ["#1C1A14", "#2B2A20", "#E9E4DA"]

        washes = vz.caption_washes(150, 240, [low, top], layout, dark_picture)
        assert len(washes) == 1, "the low caption only brushed the fade"
        w = washes[0]
        assert w["zone"] == "top" and w["color"] == "#FAF1E4", "dark words need a light ground"
        tz = layout["topZone"]
        assert w["rect"][3] <= tz["top"] + tz["height"] + vz.WASH_MARGIN
        assert w["rect"][1] >= tz["top"] - vz.WASH_MARGIN - 1

    def test_a_ground_is_measured_under_the_words_not_the_whole_zone(self):
        box = vz.text_box(self._chunk("top", 0, 60, "#000000", "#000000"), bc.LAYOUT)
        tz = bc.LAYOUT["topZone"]
        assert tz["top"] < box[1] and box[3] < tz["top"] + tz["height"]

    def test_the_mark_steps_aside_only_when_a_picture_would_swallow_it(self):
        assert vz.mark_should_hide(["#1C2A1E", "#243322", "#3A3A2A"])
        assert not vz.mark_should_hide(["#EFE6DA", "#E2D6C6"])


# ---------------------------------------------------------------------------
class TestStageAndVerify:
    def _data(self, src):
        return {"visuals": {"items": [{"id": "v1", "kind": "image", "src": src,
                                       "fromFrame": 150, "toFrame": 210}]}}

    def test_stage_copies_exactly_the_referenced_assets(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        f = next((p / "assets/ai").glob("*.png"))
        pub = tmp_path / "public"
        (pub / "ai").mkdir(parents=True)
        (pub / "ai" / "stale-from-last-clip.png").write_bytes(b"x")
        copied = vz.stage_assets(p, self._data(f"ai/{f.name}"), pub)
        assert copied == [f"ai/{f.name}"]
        assert sorted(x.name for x in (pub / "ai").iterdir()) == [f.name]

    def test_a_clip_without_visuals_stages_no_ai_folder(self, tmp_path):
        pub = tmp_path / "public"
        (pub / "ai").mkdir(parents=True)
        (pub / "ai" / "stale.png").write_bytes(b"x")
        assert vz.stage_assets(tmp_path, {}, pub) == []
        assert not (pub / "ai").exists()

    def test_a_new_asset_changes_what_render_will_check(self, tmp_path):
        """The staging receipt hashes captions_data.json. Asset filenames carry
        the request hash, so a regenerated visual changes that file and a
        stale studio can no longer render silently."""
        a = vz.asset_name("v1", "a" * 64, "png")
        b = vz.asset_name("v1", "b" * 64, "png")
        assert a != b

    def test_verify_passes_a_good_asset(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        vz.generate(p, FakeRunner(), log=lambda *a: None)
        f = next((p / "assets/ai").glob("*.png"))
        assert vz.verify_assets(p, self._data(f"ai/{f.name}")) == []

    @pytest.mark.parametrize("content,expect", [
        (None, "missing"), (b"", "zero-byte"), (b"not an image", "decode")])
    def test_verify_catches_a_broken_asset(self, tmp_path, content, expect):
        p = make_project(tmp_path, [visual("v1", 2)])
        (p / "assets/ai").mkdir(parents=True)
        if content is not None:
            (p / "assets/ai/v1-deadbeef0000.png").write_bytes(content)
        problems = vz.verify_assets(p, self._data("ai/v1-deadbeef0000.png"))
        assert problems and any(expect in x for x in problems)

    def test_verify_catches_a_video_shorter_than_its_window(self, tmp_path):
        p = make_project(tmp_path, [])
        (p / "assets/ai").mkdir(parents=True)
        f = p / "assets/ai/v1-feedface0000.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc=s=320x576:r=24", "-frames:v", "25",
               "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(f))
        data = {"visuals": {"items": [{"id": "v1", "kind": "video",
                                       "src": f"ai/{f.name}",
                                       "fromFrame": 150, "toFrame": 300}]}}
        assert any("shorter" in x for x in vz.verify_assets(p, data))


# ---------------------------------------------------------------------------
class TestPartnerAndStudio:
    TSX = ROOT / "studio" / "src"

    def test_the_partner_cut_renders_through_the_same_component(self):
        src = (self.TSX / "PartnerVideo.tsx").read_text()
        assert '<DoctorVideo {...props} brandId="partner" />' in src

    def test_the_visual_layers_are_not_gated_by_brand(self):
        src = (self.TSX / "DoctorVideo.tsx").read_text()
        for comp in ("<SupportingVisuals", "<DoctorBubble", "<CaptionWash"):
            assert comp in src, comp
            line = next(l for l in src.splitlines() if comp in l)
            assert "brand" not in line

    def test_remotion_never_calls_a_model(self):
        """Remotion consumes finished files. A render must never be able to
        spend GPU money."""
        src = (self.TSX / "DoctorVideo.tsx").read_text().lower()
        for word in ("modal.run", "fetch(", "flux", "ltx"):
            assert word not in src, word


# ---------------------------------------------------------------------------
class TestToolkitCommand:
    def test_images_go_through_the_toolkit_on_modal(self, tmp_path):
        req = vz.request_for(visual("v1", 2))
        argv = vz.toolkit_argv("flux2", req, Path("/abs/out.png"), Path("/tk"))
        assert argv[:6] == ["uv", "run", "--directory", "/tk", "python", "tools/flux2.py"]
        assert argv[argv.index("--cloud") + 1] == "modal"
        assert argv[argv.index("--output") + 1] == "/abs/out.png"
        assert "--no-open" in argv and "runpod" not in argv

    def test_video_carries_frames_and_a_negative_prompt(self):
        req = vz.request_for(visual("v1", 2, mode="video"))
        argv = vz.toolkit_argv("ltx2", req, Path("/abs/out.mp4"), Path("/tk"))
        assert argv[argv.index("--num-frames") + 1] == str(req["numFrames"])
        assert "--negative-prompt" in argv
        assert argv[argv.index("--cloud") + 1] == "modal"

    def test_the_real_runner_never_falls_back_to_another_provider(self):
        assert set(vz.TOOLS) == {"flux2", "image_edit", "ltx2"}
        assert all(t["provider"] == "modal" for t in vz.TOOLS.values())


# ---------------------------------------------------------------------------
class TestMotionGraphics:
    """Rung 1: when she says a number, a frequency or a list, Remotion draws it
    — exact, free, and never a number she didn't say."""

    def graphic(self, vid="g1", beat=2, **g):
        return visual(vid, beat, treatment="inset", mode="graphic", prompt="",
                      graphic=g or {"type": "checklist",
                                    "items": ["DAILY MOVEMENT", "CARDIO", "STRENGTH"]})

    def test_a_graphic_calls_no_model_and_costs_nothing(self, tmp_path):
        p = make_project(tmp_path, [self.graphic()])
        runner = FakeRunner()
        s = vz.generate(p, runner, log=lambda *a: None)
        assert runner.calls == [] and s["costUsd"] == 0
        ready, _ = vz.ready_assets(p)
        assert "g1" in ready

    def test_a_graphic_takes_its_beat(self):
        items, _ = resolve([self.graphic()])
        assert items[0]["kind"] == "graphic"
        assert (items[0]["fromFrame"], items[0]["toFrame"]) == (150, 210)

    @pytest.mark.parametrize("said,graphic,ok", [
        ("at least 8 to 10 ,000 steps per day",
         {"type": "counter", "value": 10000, "from": 8000}, True),
        ("at least 8 to 10 ,000 steps per day",
         {"type": "counter", "value": 12000}, False),
        ("weekly two or three times",
         {"type": "frequency", "count": [2, 3]}, True),
        ("weekly two or three times",
         {"type": "frequency", "count": 4}, False),
        ("of at least 150 minutes per week",
         {"type": "ring", "value": 150, "unit": "MIN"}, True),
        ("daily movement cardiovascular exercise strength training",
         {"type": "checklist", "items": ["DAILY MOVEMENT", "CARDIO", "STRENGTH"]}, True),
    ])
    def test_a_graphic_only_shows_numbers_she_said(self, said, graphic, ok):
        assert (vz.lint_graphic(graphic, said) == []) is ok

    def test_an_unknown_graphic_type_is_refused(self):
        assert vz.lint_graphic({"type": "pieChart", "value": 3}, "3")
        assert set(vz.GRAPHIC_TYPES) == {"counter", "frequency", "ring", "checklist"}

    def test_a_checklist_stays_short(self):
        long = {"type": "checklist", "items": ["A", "B", "C", "D", "E"]}
        assert vz.lint_graphic(long, "a b c d e")

    def test_the_plan_marks_graphics_as_free(self, tmp_path):
        p = make_project(tmp_path, [self.graphic()])
        text = vz.plan_text(p)
        assert "TEXT ANIMATION" in text and "$0" in text


# ---------------------------------------------------------------------------
class TestPlanAndRegister:
    def test_the_plan_names_every_beat_and_the_cost(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2, status="proposed"),
                                    visual("v2", 4, mode="video")])
        text = vz.plan_text(p)
        assert "VISUAL PLAN" in text
        for n in range(1, 6):
            assert f"Beat {n}" in text
        assert "no visual" in text and "Estimated" in text
        assert "PROPOSED" in text and "APPROVED" in text

    def test_the_plan_prints_her_words_beside_the_prompt(self, tmp_path):
        p = make_project(tmp_path, [visual("v1", 2)])
        assert "w8 w9 w10 w11" in vz.plan_text(p)

    def test_visual_axes_are_registered_and_rotate(self):
        assert register.AXES["visualStyle"]["options"] == vz.VISUAL_STYLES
        assert register.AXES["bubbleShape"]["options"] == vz.BUBBLE_SHAPES
        assert register.AXES["visualStyle"]["kind"] == "chosen"

    def test_a_clip_without_visuals_records_no_visual_style(self):
        assert register.AXIS_READERS["visualStyle"]({}) is None
        assert register.AXIS_READERS["bubbleShape"]({"visuals": {"bubbleShape": "circle"}}) == "circle"
