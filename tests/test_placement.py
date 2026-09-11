"""Where things land. The plate, the mark, the payload, the safe area.

The headline case here is `pcos-sleep-cycle`, which SHIPPED with the doctor
plate covering a caption for 27 frames. `verify` passed it; a frame pulled at
9.5s shows the italic lead rendering underneath the plate pill. The old logic
reasoned about zone NAMES: it pushed the plate up to dodge a bottom-zone
caption and walked straight into a top-zone one, with nothing checking
rectangles. Every test in this file exists to stop a repeat."""
import pytest

import build_captions as bc

FPS = 30
PLATFORM_UI = 250          # bottom strip the platform's own chrome occupies
HEIGHT, WIDTH = 1920, 1080


def band(zone_cfg):
    return (0, zone_cfg["top"], WIDTH, zone_cfg["top"] + zone_cfg["height"])


def plate_box(data):
    dp = data["layout"]["doctorPlate"]
    return bc.plate_rect(dp, dp["top"], dp.get("left"))


def mark_box(data):
    lg = data["layout"]["logo"]
    # The mark is square-ish in its own art; height follows the sting's aspect.
    h = int(lg["width"] * 0.42)
    return (WIDTH - lg["right"] - lg["width"], lg["y"],
            WIDTH - lg["right"], lg["y"] + h)


def live_chunks(data, frm, to, pad):
    """Chunks whose text is on screen at any point in [frm, to), padded by the
    reveal's own in/out frames — a caption that is still animating is still on
    screen, and the old check used raw frame numbers."""
    return [c for c in data["phases"][1]["chunks"]
            if c["fromFrame"] - pad < to and c["toFrame"] + pad > frm]


class TestPlateNeverCoversText:
    """The sleep-cycle bug, as a test."""

    def test_the_shipped_sleep_cycle_collision_is_detected(self, shipped):
        """A canary, not a rule: this asserts the OLD data still shows the
        fault, so the detector is proven to catch it. The clip is not being
        re-rendered — the fix applies from the next video on — so if this ever
        starts passing, either the file was rebuilt or the detector went
        blind."""
        data = shipped["pcos-sleep-cycle"]
        fix, dp = data["fixtures"], data["layout"]["doctorPlate"]
        frm = fix["plateFromFrame"]
        to = frm + dp["holdFrames"]
        m = data["theme"]["motion"]
        pad = max(m["chunkInFrames"], m["chunkOutFrames"])
        overlapping = [c for c in live_chunks(data, frm, to, pad)
                       if bc.rect_overlap(plate_box(data),
                                          band(data["layout"][c["zone"] + "Zone"]))]
        assert overlapping, "the known collision is no longer detected"
        c = overlapping[0]
        frames = min(to, c["toFrame"] + pad) - max(frm, c["fromFrame"] - pad)
        assert frames >= 20, f"expected the ~27-frame overlap, measured {frames}"

    @pytest.mark.parametrize("slug", ["pcos-muscle"])
    def test_current_clips_have_no_plate_over_text(self, shipped, slug):
        data = shipped[slug]
        fix, dp = data["fixtures"], data["layout"]["doctorPlate"]
        frm, to = fix["plateFromFrame"], fix["plateFromFrame"] + dp["holdFrames"]
        m = data["theme"]["motion"]
        pad = max(m["chunkInFrames"], m["chunkOutFrames"])
        for c in live_chunks(data, frm, to, pad):
            assert not bc.rect_overlap(
                plate_box(data), band(data["layout"][c["zone"] + "Zone"])), (
                f"{slug}: plate overlaps {c['id']} ({c['zone']} zone)")

    def test_plate_never_overlaps_the_mark(self, shipped):
        """Two fixtures in one corner reads as a layout accident."""
        for slug, data in shipped.items():
            assert not bc.rect_overlap(plate_box(data), mark_box(data)), slug

    def test_plate_stays_clear_of_the_platform_chrome(self, shipped):
        for slug, data in shipped.items():
            assert plate_box(data)[3] <= HEIGHT - PLATFORM_UI + 60, (
                f"{slug}: plate bottom {plate_box(data)[3]} runs into the "
                f"bottom {PLATFORM_UI}px where the platform UI sits")


class TestRectOverlap:
    """The primitive everything above rests on. A wrong operator here would
    make every placement test pass while checking nothing."""

    def test_touching_edges_do_not_count_as_overlap(self):
        assert not bc.rect_overlap((0, 0, 100, 100), (100, 0, 200, 100))

    def test_containment_counts(self):
        assert bc.rect_overlap((0, 0, 100, 100), (10, 10, 20, 20))

    def test_padding_widens_the_test(self):
        a, b = (0, 0, 100, 100), (120, 0, 200, 100)
        assert not bc.rect_overlap(a, b)
        assert bc.rect_overlap(a, b, pad=30)


class TestMarkObeysTheFootage:
    """`pcos-sleep-cycle` becomes a full-screen infographic at 13.2s and the
    mark landed squarely on the insulin-resistance illustration, while the
    top-band scan reported nothing unusual — by then the whole frame was
    graphic. The mark's own rectangle has to be measured, not the band's."""

    def test_the_graphic_heavy_clip_hides_the_mark(self, shipped):
        wins = shipped["pcos-sleep-cycle"]["fixtures"]["logoHideWindows"]
        assert wins, "the infographic stretch must hide the mark"
        a, b = wins[0]
        assert 12.5 <= a / FPS <= 14.0, f"hide starts at {a/FPS:.1f}s"
        assert 26.0 <= b / FPS <= 28.0, f"hide ends at {b/FPS:.1f}s"

    def test_the_clean_clip_hides_nothing(self, shipped):
        """`pcos-muscle`'s mark is never covered. A measurement that flags it
        anyway is the median trap: on a clip that is graphic for more than half
        its length the median IS the graphic, so every clean frame reads as
        'covered'. That bug flagged an entire clip before the reference frame
        was anchored to a known-clear window."""
        assert shipped["pcos-muscle"]["fixtures"]["logoHideWindows"] == []


class TestPayloadSizing:
    """Payload size is driven by the LONGEST line, not the cap. Raising
    bottomMaxMultiLine alone does nothing for a long line."""

    def test_a_longer_line_gets_smaller_type(self):
        tk = bc.THEME["type"]["key"]
        short = bc.key_size(["PCOS"], tk, 940)
        long = bc.key_size(["MAINTAINING MUSCLE MASS"], tk, 940)
        assert long < short

    def test_size_never_drops_below_the_floor(self):
        tk = bc.THEME["type"]["key"]
        size = bc.key_size(["A VERY LONG PAYLOAD LINE INDEED THAT KEEPS GOING"],
                           tk, 940)
        assert size >= tk["minSize"]

    def test_the_last_line_clears_the_platform_chrome(self, shipped):
        for slug, data in shipped.items():
            bz = data["layout"]["bottomZone"]
            for c in data["phases"][1]["chunks"]:
                if c["zone"] != "bottom":
                    continue
                lines = len(c["keyLines"])
                bottom = bz["top"] + lines * c["keySize"] * 0.92
                assert bottom <= HEIGHT - PLATFORM_UI + 120, (
                    f"{slug} {c['id']} runs to y={bottom:.0f}")
