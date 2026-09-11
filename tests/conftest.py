"""Shared fixtures. Every test in this suite is a reel that had to be thrown
away, or a bug that shipped and was caught later — see docs/TEST-CASES.md for
the history behind each one."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

# The heritage-era four: Anton faces, the original mask wipe, built before the
# opt-in engines existed. Rules that assume "what shipped always looked like
# this" are asserted on LEGACY, not on SHIPPED.
LEGACY = ["pcos-insulin-resistance", "pcos-walking", "pcos-muscle",
          "pcos-sleep-cycle"]

SHIPPED = LEGACY + ["pcos-build-muscle"]

# The clips whose work/captions_data.json was produced by the pipeline as it
# stands. `pcos-insulin-resistance` and `pcos-walking` were built on 27 Aug and
# never rebuilt, so their files predate the lead-line contrast floor, the
# question-card presets, listIndex, logoHideWindows and the stroke block. They
# are a record of what rendered, not a sample of what the pipeline now emits —
# asserting today's rules against them tests history against a rule that did
# not exist yet. Rules are asserted on CURRENT_GEN; the older pair get the
# staleness check in test_delivery.py instead.
CURRENT_GEN = ["pcos-muscle", "pcos-sleep-cycle"]


def _load(slug, name):
    p = ROOT / "projects" / slug / "work" / name
    return json.loads(p.read_text()) if p.exists() else None


@pytest.fixture(scope="session")
def shipped():
    """Every shipped clip's built caption data, keyed by slug. These files are
    the record of what actually rendered, so a rule that holds on them is a
    rule the reels already obey."""
    return {s: d for s in SHIPPED if (d := _load(s, "captions_data.json"))}


@pytest.fixture(scope="session")
def audio():
    return {s: d for s in SHIPPED if (d := _load(s, "audio.json"))}


@pytest.fixture(scope="session")
def briefs():
    out = {}
    for s in SHIPPED:
        p = ROOT / "projects" / s / "brief.json"
        if p.exists():
            out[s] = json.loads(p.read_text())
    return out
