"""The checks that belong to delivering a video, not to building one.

These are the things that have gone out wrong: a render made from stale staged
data, a work file that no longer describes the reel it produced, and wording
that should never leave the building."""
import hashlib
import json
import re
import subprocess

import pytest

from conftest import LEGACY, ROOT, SHIPPED

STUDIO = ROOT / "studio" / "src" / "captions_data.json"
BANNED = [
    (r"\bcures?\b", "cure"), (r"\breverses?\b", "reverse"),
    (r"\bguarantee[ds]?\b", "guarantee"), (r"\bpermanently?\b", "permanent"),
    (r"\b100\s?%", "100%"), (r"\bcompletely cured\b", "completely cured"),
]


def work(slug, name="captions_data.json"):
    return ROOT / "projects" / slug / "work" / name


class TestStagingIsNotSkipped:
    """`build` writes work/captions_data.json; `stage` copies it into the
    studio; `render` reads only what the studio holds. Skip `stage` and you
    render the PREVIOUS version — the render succeeds, verify passes, and every
    change is silently absent. This has happened."""

    def test_the_studio_holds_exactly_one_known_clip(self):
        assert STUDIO.exists(), "nothing staged"
        staged = STUDIO.read_bytes()
        # "known" is every project the pipeline has built data for — a clip
        # staged between its kyros render and its partner sign-off is still
        # known, and the studio matching it is exactly the intended state.
        known = sorted(p.parent.parent.name for p in
                       (ROOT / "projects").glob("*/work/captions_data.json"))
        matches = [s for s in known
                   if work(s).exists() and work(s).read_bytes() == staged]
        assert len(matches) == 1, (
            "the staged caption data matches no project's work copy — it is "
            "either mid-edit or stale, and a render now would ship the wrong "
            "version silently")

    def test_the_staged_slug_agrees_with_its_own_metadata(self):
        staged = json.loads(STUDIO.read_text())
        slug = staged["meta"]["slug"]
        assert work(slug).exists()
        assert work(slug).read_bytes() == STUDIO.read_bytes(), (
            f"studio holds {slug} but not the same bytes as its work copy")


class TestRenders:
    """`verify` exists because three bugs shipped past visual inspection: an
    end card holding one frame for three seconds that looked deliberate, a stat
    card that sat as an empty box, and a logo at 1.6:1 against the wall."""

    @staticmethod
    def probe(path):
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", str(path)])
        d = json.loads(out)
        return (int(d["streams"][0]["width"]), int(d["streams"][0]["height"]),
                float(d["format"]["duration"]))

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_the_kyros_cut_exists_and_is_vertical_1080p(self, slug):
        p = ROOT / "projects" / slug / "out" / f"{slug}-kyros.mp4"
        assert p.exists(), p
        w, h, dur = self.probe(p)
        assert (w, h) == (1080, 1920), f"{p.name} is {w}x{h}"
        assert dur > 5, f"{p.name} is only {dur:.2f}s"

    @pytest.mark.parametrize("slug", LEGACY)
    def test_the_partner_cut_exists_and_is_vertical_1080p(self, slug):
        """The flow renders kyros first and the partner cut after sign-off
        (README part 1, step 6), so a clip can legitimately sit with only its
        kyros cut rendered. The legacy four completed that step;
        pcos-build-muscle's partner cut is awaiting Niranjan."""
        p = ROOT / "projects" / slug / "out" / f"{slug}-partner.mp4"
        assert p.exists(), p
        w, h, dur = self.probe(p)
        assert (w, h) == (1080, 1920), f"{p.name} is {w}x{h}"
        assert dur > 5, f"{p.name} is only {dur:.2f}s"

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_the_render_is_at_least_as_long_as_the_body(self, slug):
        """An end card that never arrives, or a body truncated by a short
        composition, both show up here."""
        data = json.loads(work(slug).read_text())
        p = ROOT / "projects" / slug / "out" / f"{slug}-kyros.mp4"
        _, _, dur = self.probe(p)
        expected = data["brands"]["kyros"]["durationInFrames"] / data["meta"]["fps"]
        assert dur >= expected - 0.2, f"{slug}: {dur:.2f}s vs {expected:.2f}s expected"


class TestRenderProvenance:
    """`stage` copies the built data into the studio; `render` reads only what
    the studio holds. Skip `stage` and the render succeeds, verify passes, and
    every change is silently absent — the failure has no symptom. `stage` now
    leaves a receipt and `render` stamps each cut with the digest it was built
    from, so the question is answerable after the fact rather than remembered."""

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_a_stamped_render_matches_the_data_beside_it(self, slug):
        stamp = ROOT / "projects" / slug / "out" / f"{slug}-kyros.render.json"
        if not stamp.exists():
            pytest.skip(f"{slug} was rendered before stamping existed")
        got = json.loads(stamp.read_text())
        live = hashlib.md5(work(slug).read_bytes()).hexdigest()
        assert got["captionsMd5"] == live, (
            f"{slug}: the posted cut was rendered from {got['captionsMd5'][:8]}, "
            f"the work file now hashes to {live[:8]} — one of them is not what "
            f"you think it is")

    def test_the_staging_receipt_describes_what_is_actually_staged(self):
        receipt = ROOT / "studio" / "src" / ".staged.json"
        if not receipt.exists():
            pytest.skip("nothing staged through the receipt-writing path yet")
        got = json.loads(receipt.read_text())
        assert got["captionsMd5"] == hashlib.md5(STUDIO.read_bytes()).hexdigest()


class TestComplianceWording:
    """Schedule J applies to most Kyros verticals. No cure, reverse or
    guarantee language, and no promised timelines."""

    @staticmethod
    def hits(text):
        return [label for pat, label in BANNED if re.search(pat, text.lower())]

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_no_banned_claim_is_ever_set_large(self, slug):
        """The hard rule. She is the clinical authority on her own words and
        they are not quietly reworded — but a cure claim set at 150px as the
        payload is the pipeline making the claim, not her. `pcos-muscle` says
        "it almost cures the pathophysiology" and `pcos-walking` says "reverse
        the pathophysiology"; in both, the word stays in the small italic lead
        and never reaches a payload line."""
        data = json.loads(work(slug).read_text())
        large = []
        for c in data["phases"][1]["chunks"]:
            large += c["keyLines"]
        for row in data["phases"][0]["rows"]:
            large += row.get("lines") or []
        found = self.hits(" ".join(large))
        assert not found, f"{slug} sets {', '.join(found)} as a payload"

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_any_banned_claim_in_a_lead_is_declared_in_the_brief(self, slug, briefs):
        """Raise it rather than quietly reword her — and record the decision.
        An undeclared cure claim means nobody looked at it."""
        data = json.loads(work(slug).read_text())
        leads = " ".join(c["leadText"] for c in data["phases"][1]["chunks"])
        found = self.hits(leads)
        if not found:
            return
        flags = " ".join(briefs[slug].get("openFlags") or []).lower()
        for label in found:
            assert label in flags or label.rstrip("s") in flags, (
                f"{slug} says '{label}' in a caption with no openFlags entry "
                f"acknowledging it")


class TestOptInStaysOptIn:
    """Four shipped reels and a fifth experimental one share one pipeline. The
    new engines must be unreachable unless a brief asks for them, or the older
    clips stop being reproducible."""

    @pytest.mark.parametrize("slug", SHIPPED)
    def test_no_shipped_clip_carries_a_reveal_key(self, slug):
        data = json.loads(work(slug).read_text())
        assert not any("reveal" in c for c in data["phases"][1]["chunks"]), (
            f"{slug} would no longer resolve to the original mask wipe")

    @pytest.mark.parametrize("slug", LEGACY)
    def test_no_legacy_clip_switched_its_faces(self, slug):
        """The type pairing is a rotation axis now — later clips deliberately
        run other pairings — so the faces guarantee is scoped to the
        heritage-era clips it was written for."""
        data = json.loads(work(slug).read_text())
        t = data["theme"]["type"]
        assert t["lead"]["fontFamily"] == "PlayfairDisplay", slug
        assert t["key"]["fontFamily"] == "Anton", slug
