"""Reveals, faces, and the voice they follow."""
import pytest

import motion, typography, measure_audio  # noqa: F401

FPS = 30


class TestNoIllegibleIntermediateState:
    """`pcos-sleep-cycle` shipped with the payload "UNDER CONTROL" caught
    mid-wipe at 10.5s, rendering as a flat grey half-drawn line. In motion it
    passes; on a still — a paused reel, a thumbnail — it reads as a rendering
    fault. The legacy wipe measures 13 illegible frames, 0.43s."""

    BUDGET = 2      # frames a glyph may spend unreadable, at 30fps

    def test_the_legacy_wipe_is_the_thing_being_replaced(self):
        assert motion.REVEAL_STYLES["legacyMaskWipe"]["illegibleFrames"] > self.BUDGET

    @pytest.mark.parametrize("name", [n for n in motion.REVEAL_STYLES
                                      if n != "legacyMaskWipe"])
    def test_every_chooseable_style_stays_inside_the_budget(self, name):
        assert motion.REVEAL_STYLES[name]["illegibleFrames"] <= self.BUDGET

    @pytest.mark.parametrize("name", list(motion.REVEAL_STYLES))
    def test_no_style_displaces_far_enough_to_fight_the_footage(self, name):
        """She gestures constantly. A reveal that travels competes with her."""
        assert motion.REVEAL_STYLES[name]["displacementPx"] <= 12


class TestWhenNotToAnimate:
    """A caption that appears is not automatically a caption that should
    animate — the same logic that says a beat under a burned-in graphic wants
    no caption says a beat under a MOVING graphic wants no motion of its own."""

    def test_a_sub_second_beat_does_not_animate(self):
        on, why = motion.should_animate(20, 0.0, 0.0, 0, False)
        assert not on and why

    def test_a_beat_buried_under_a_graphic_does_not_animate(self):
        on, _ = motion.should_animate(90, 0.95, 0.0, 0, False)
        assert not on

    def test_a_beat_over_heavy_gesture_does_not_animate(self):
        on, _ = motion.should_animate(90, 0.0, 0.9, 0, False)
        assert not on

    def test_three_in_a_row_breaks_the_streak(self):
        """Three staggered reveals running is a template, not a style."""
        on, _ = motion.should_animate(90, 0.0, 0.0, 3, False)
        assert not on

    def test_a_clean_hero_beat_does_animate(self):
        on, _ = motion.should_animate(120, 0.0, 0.0, 0, True)
        assert on

    def test_every_refusal_states_a_reason(self):
        for args in [(20, 0, 0, 0, False), (90, 0.95, 0, 0, False),
                     (90, 0, 0.9, 0, False), (90, 0, 0, 3, False)]:
            _, why = motion.should_animate(*args)
            assert isinstance(why, str) and why.strip()


class TestChooseReveal:
    def test_it_returns_a_registered_style(self):
        got = motion.choose_reveal(120, "top", False, 0.9, True, [])
        assert got["style"] in motion.REVEAL_STYLES

    def test_it_never_chooses_the_legacy_wipe(self):
        """legacyMaskWipe exists only as the implicit resolution of an absent
        key — nothing should ever actively pick it."""
        for dur in (40, 90, 150, 240):
            for zone in ("top", "bottom"):
                got = motion.choose_reveal(dur, zone, False, 0.5, False, [])
                assert got["style"] != "legacyMaskWipe"

    def test_it_varies_when_the_same_style_keeps_coming_up(self):
        prior = ["maskWipeFast"] * 3
        got = motion.choose_reveal(120, "top", False, 0.5, False, prior)
        assert got["style"] != "maskWipeFast"


class TestTypePairings:
    """Anton is condensed. A pairing that swaps in a wider payload face and is
    not re-measured overflows the band — and the overflow is silent, because
    nothing renders during build."""

    def test_lead_and_payload_are_always_different_faces(self):
        for name, p in typography.PAIRINGS.items():
            assert p["lead"]["fontFamily"] != p["key"]["fontFamily"], name

    def test_every_pairing_fits_the_worst_case_shipped_payload(self):
        for (pairing, zone), fit in typography.MEASURED_FIT.items():
            assert fit["marginPx"] > 0, (
                f"{pairing}/{zone}: '{fit['line']}' overruns by "
                f"{-fit['marginPx']}px")
            assert fit["widthPx"] <= fit["availPx"]

    def test_every_pairing_was_measured_in_both_zones(self):
        for name in typography.PAIRINGS:
            for zone in ("top", "bottom"):
                assert (name, zone) in typography.MEASURED_FIT, f"{name}/{zone}"

    def test_heritage_stays_the_fallback(self):
        """An absent key and an empty rotation history must resolve to the same
        thing, or a brief that opts in and one that does not stop matching."""
        assert typography.rotation_pick([]) == "heritage"
        assert list(typography.PAIRINGS)[0] == "heritage"


class TestAudioMeasurement:
    """Nothing listened to the audio for four reels. Captions were timed off
    forced alignment alone, so every beat got the same flat treatment however
    she actually said it."""

    def test_the_pause_threshold_is_derived_per_clip(self, audio):
        """A pinned constant is the same mistake as a pinned wall colour. The
        four takes range 0.22s to 0.83s — one number could not serve them."""
        thresholds = {s: d["takeStats"]["pauseThresholdSeconds"]
                      for s, d in audio.items()}
        assert len(set(thresholds.values())) > 1, thresholds

    def test_emphasis_is_normalised_into_range(self, audio):
        for slug, d in audio.items():
            vals = [w["emphasis"] for w in d["words"]]
            assert min(vals) >= 0.0 and max(vals) <= 1.0, slug

    def test_gaps_line_up_with_the_words(self, audio):
        for slug, d in audio.items():
            assert len(d["gaps"]) == len(d["words"]) - 1, slug

    def test_the_boundary_check_catches_a_mid_phrase_break(self, briefs, audio):
        """12 of 26 boundaries across the four shipped reels land at a 0.00s
        gap. A break is written by reading the transcript, where the sentence
        end looks obvious on the page; she did not stop there."""
        import json
        from conftest import ROOT
        slug = "pcos-sleep-cycle"
        words = json.loads((ROOT / "projects" / slug / "work" / "words.json").read_text())
        words = words["words"] if isinstance(words, dict) else words
        warnings = measure_audio.check_chunk_boundaries(briefs[slug], words, audio[slug])
        assert warnings, "the known mid-phrase breaks are no longer reported"
        assert any("continuous speech" in w for w in warnings)
