"""The register: no axis repeats by accident.

"Don't repeat the last two reels" was a human reading a table for four clips.
This is that rule as code — and the tests below are the ways it was found to
misfire."""
import register


class TestNonRepetition:
    def test_no_chosen_axis_repeats_the_last_two_clips(self):
        axes, _ = register.propose()
        hist, _ = register.read_history()
        for name, spec in register.AXES.items():
            if spec["kind"] != "chosen" or "value" not in axes[name]:
                continue
            recent = [v for v in hist[name][-2:] if v in spec["options"]]
            if len(recent) < len(spec["options"]):
                assert axes[name]["value"] not in recent, (
                    f"{name} proposes {axes[name]['value']}, used in {recent}")

    def test_every_proposal_states_a_reason(self):
        axes, _ = register.propose()
        for name, got in axes.items():
            assert got.get("reason") or got.get("note"), name

    def test_history_is_ordered_oldest_first(self):
        _, slugs = register.read_history()
        # the shipped running record, oldest first; later briefs append
        assert slugs[:4] == [
            "pcos-insulin-resistance",
            "pcos-walking",
            "pcos-muscle",
            "pcos-sleep-cycle",
        ]


class TestLegacyProseCounts:
    """The selector proposed `heritage` for the fifth clip — the one pairing
    that had been on screen four reels running. All four briefs record the
    pairing as prose ("PlayfairDisplay Italic / Anton"), which is exactly what
    `heritage` names now that pairings resolve by key. Discarding that as
    unparseable read as "never run". An absent or unstructured key is not an
    absent choice: the hardcoded default rendered."""

    def test_the_shipped_clips_count_as_heritage(self):
        hist, _ = register.read_history()
        assert hist["typePairing"][:4] == ["heritage"] * 4

    def test_the_next_clip_is_not_offered_whats_just_run(self):
        """The original form: after four reels of `heritage`, the selector
        (mis)parsed the prose and offered it a fifth time. The durable rule
        underneath is the pairing axis must propose outside the last two
        runs — which `heritage` re-earns the right to once other pairings
        have been on screen."""
        axes, _ = register.propose()
        hist, _ = register.read_history()
        recent = hist["typePairing"][-2:]
        assert axes["typePairing"]["value"] not in recent

    def test_an_unknown_prose_value_is_left_alone(self):
        """Only the known legacy string is normalised; a genuinely unknown
        value must not be silently rewritten into a real pairing."""
        got = register._type_pairing({"style": {"typePairing": "Something Else"}})
        assert got == "Something Else"

    def test_a_brief_with_no_style_block_still_counts_as_heritage(self):
        assert register._type_pairing({}) == "heritage"


class TestPinsWin:
    def test_a_pinned_axis_is_returned_verbatim(self):
        brief = {"question": {"preset": "ink"}, "style": {"leadStyle": "match"}}
        axes, _ = register.propose(brief)
        assert axes["questionPreset"]["value"] == "ink"
        assert axes["leadStyle"]["value"] == "match"
        assert "pinned" in axes["questionPreset"]["reason"]


class TestMeasuredAxesAreNeverRotated:
    """Forcing "not what you did last time" onto a safety measurement is
    exactly backwards. The plate and mark answer to the footage on every clip,
    not to a rotation."""

    def test_measured_axes_carry_no_proposal(self):
        axes, _ = register.propose()
        for name, spec in register.AXES.items():
            if spec["kind"] == "measured":
                assert "value" not in axes[name], name


class TestAxesAreExtensible:
    """A new axis must be a data addition, not a code change — the type and
    reveal axes were registered by a module the selector knows nothing about."""

    def test_the_type_and_motion_modules_register_their_own_options(self):
        import typography, motion
        assert register.AXES["typePairing"]["options"] == list(typography.PAIRINGS)
        expected = [s for s in motion.REVEAL_STYLES if s != "legacyMaskWipe"]
        assert register.AXES["revealStyle"]["options"] == expected

    def test_every_axis_declares_a_kind_and_options(self):
        for name, spec in register.AXES.items():
            assert spec["kind"] in ("chosen", "measured"), name
            assert spec["options"], name
