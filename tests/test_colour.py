"""Colour rules. Every one of these is a reel that was thrown away or a frame
that shipped wrong — the docstrings name which."""
import pytest
from coloraide import Color

import palette as pal
import build_captions as bc

SAFFRON = "#FFB01F"          # the brand accent every rotation tone is measured against
DISPLAY_FLOOR = 45           # APCA floor for display type
STRONG = 60                  # "strong" per README
ROTATION_FLOOR = 62          # a rotation tone must clear this, not just the display floor
HUE_FLOOR = 40               # degrees, minimum separation between rotation neighbours


def hue(hexs):
    h = Color(hexs).convert("oklch")["hue"]
    return 0.0 if h is None else float(h)


def hue_gap(a, b):
    d = abs(hue(a) - hue(b)) % 360
    return min(d, 360 - d)


class TestPolarity:
    """`pcos-muscle`: forest green measured 61 Lc on the pale wall and 3.9 Lc
    on the dark scrim. A colour is not legible on its own — only against what
    is behind it. This was the most expensive mistake on the pipeline, made
    twice."""

    def test_dark_half_fails_on_a_dark_ground(self):
        # The exact numbers from the README's table. If these ever pass on a
        # dark scrim, the polarity rule has been broken somewhere upstream.
        scrim = "#1C1410"
        assert abs(pal.apca("#103D2C", scrim)) < DISPLAY_FLOOR   # forest
        assert abs(pal.apca("#A6371C", scrim)) < DISPLAY_FLOOR   # brick

    def test_light_half_fails_on_a_pale_wall(self):
        wall = "#E0B794"
        assert abs(pal.apca("#FFF6E8", wall)) < DISPLAY_FLOOR    # warm white

    def test_each_half_clears_its_own_ground(self):
        assert abs(pal.apca("#103D2C", "#E0B794")) >= STRONG
        assert abs(pal.apca("#FFF6E8", "#1C1410")) >= STRONG


class TestRotationClearsTwoBars:
    """`pcos-muscle`: coral was the rotation's weak link at 57 Lc, and apricot
    replaced it at 67.7 Lc — but sat 29 degrees from the saffron accent, so the
    rotation read as one colour repeating. Contrast alone is not enough."""

    ROTATION = ["#9BE564", "#FFF6E8", "#FFA8B6", "#5FE3C0"]   # the shipped mix

    def test_every_tone_clears_the_contrast_bar(self):
        for tone in self.ROTATION:
            lc = abs(pal.apca(tone, "#1C1410"))
            assert lc >= ROTATION_FLOOR, f"{tone} only reaches {lc:.1f} Lc"

    def test_every_tone_clears_the_hue_bar_against_the_accent(self):
        for tone in self.ROTATION:
            if tone == "#FFF6E8":
                continue          # a near-neutral has no meaningful hue to separate
            g = hue_gap(tone, SAFFRON)
            assert g >= HUE_FLOOR, f"{tone} sits {g:.0f}deg from the saffron accent"

    def test_the_rejected_candidates_are_still_rejected(self):
        """Regression on the worked example: if a future change lets apricot or
        flamingo back in, the rotation goes monotone or goes dark again."""
        assert hue_gap("#FFB38F", SAFFRON) < HUE_FLOOR              # apricot: 29deg
        assert abs(pal.apca("#FF8FA3", "#1C1410")) < ROTATION_FLOOR  # flamingo: 56.4
        assert abs(pal.apca("#C0A6FF", "#1C1410")) < ROTATION_FLOOR  # lilac: 58.3


class TestNewPoolColours:
    """The blue family the pool never had. Added after four reels ran warm."""

    def test_periwinkle_and_indigo_are_in_the_pool(self):
        assert "periwinkle" in pal.POOL_HEX and "indigo" in pal.POOL_HEX

    def test_they_clear_both_bars_on_their_own_polarity(self):
        peri, indigo = pal.POOL_HEX["periwinkle"], pal.POOL_HEX["indigo"]
        assert abs(pal.apca(peri, "#1C1410")) >= ROTATION_FLOOR
        assert abs(pal.apca(indigo, "#E0B794")) >= ROTATION_FLOOR
        assert hue_gap(peri, SAFFRON) >= HUE_FLOOR
        assert hue_gap(indigo, SAFFRON) >= HUE_FLOOR


class TestLeadLine:
    """`pcos-muscle`: the lead was picked for its distance from the payload and
    landed on the parrot-green saree, where it vanished. Distance from the
    payload is not the same as legibility against the ground."""

    @pytest.mark.parametrize("payload,ground", [
        ("#103D2C", "#E0B794"), ("#9BE564", "#1C1410"),
        ("#A6371C", "#FAE9DC"), ("#FFF6E8", "#0B2119"),
    ])
    def test_nearby_lead_never_returns_something_illegible(self, payload, ground):
        lead = pal.nearby_lead(payload, ground)
        assert abs(pal.apca(lead, ground)) >= pal.LEAD_FLOOR

    @pytest.mark.parametrize("polarity,ground", [("light", "#E0B794"),
                                                 ("dark", "#1C1410")])
    def test_neutral_lead_clears_its_ground(self, polarity, ground):
        lead = pal.neutral_lead("#E0B794", polarity, ground)
        assert abs(pal.apca(lead, ground)) >= 45


class TestQuestionCards:
    """A card whose own type does not clear its own ground is a full-screen
    mistake — it is the first thing the viewer sees."""

    @pytest.mark.parametrize("name", list(bc.HOOK_CARDS))
    def test_card_type_clears_its_own_ground(self, name):
        card = bc.HOOK_CARDS[name]
        for role in ("lead", "key"):
            lc = abs(pal.apca(card[role], card["bg"]))
            assert lc >= DISPLAY_FLOOR, f"{name}.{role} only reaches {lc:.1f} Lc"

    @pytest.mark.parametrize("name", list(bc.HOOK_CARDS))
    def test_card_is_opaque_enough_to_hide_the_doctor(self, name):
        """At 0.94 she ghosts through the card and it reads as a mistake."""
        assert bc.HOOK_CARDS[name]["opacity"] >= 0.98


class TestShippedFramesObeyTheRules:
    """The strongest test available without rendering: every colour that
    actually went out must clear its own measured ground."""

    def test_a_scrimmed_clip_carries_no_stroke(self, shipped):
        """A black stroke on every glyph flattens colour and cheapens the
        frame. It exists to rescue type on a background that cannot be
        controlled — and a scrim IS the background being controlled. Both
        clips that put a panel down correctly switch the stroke off."""
        for slug, data in shipped.items():
            if not (data["layout"].get("captionScrim") or {}).get("enabled"):
                continue
            stroke = data["theme"]["type"].get("stroke") or {}
            assert stroke.get("color") is None, (
                f"{slug} has both a scrim and a live stroke")

    @staticmethod
    def ground_of(data, chunk):
        """What the type actually sits on: the composited scrim where a beat is
        low and a panel is down, the measured wall where it is not. Composited
        rather than taken flat, because a panel at 0.8 over a pale wall is not
        the panel's own colour — assuming it was is how the first contrast
        checks passed against a ground that existed nowhere on screen."""
        wall = data["theme"]["palette"]["scene"]["wall"]
        scrim = data["layout"].get("captionScrim") or {}
        if chunk["zone"] == "bottom" and scrim.get("enabled"):
            return bc.over(scrim["color"], wall, scrim.get("opacity", 1.0))
        return wall

    def test_every_shipped_caption_clears_the_display_floor(self, shipped):
        from conftest import CURRENT_GEN
        failures = []
        for slug in CURRENT_GEN:
            data = shipped[slug]
            for c in data["phases"][1]["chunks"]:
                bg = self.ground_of(data, c)
                for role in ("keyColor", "leadColor"):
                    lc = abs(pal.apca(c[role], bg))
                    if lc < DISPLAY_FLOOR:
                        failures.append(f"{slug} {c['id']} {role} {c[role]} on {bg}: {lc:.1f} Lc")
        assert not failures, "\n".join(failures)
