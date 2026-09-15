#!/usr/bin/env python3
"""Measure the take's own audio, so captions can stop treating every beat the
same regardless of how she actually said it.

    python scripts/measure_audio.py projects/<slug> [--check-chunks]

Reads   projects/<slug>/work/clip.json     for the 16kHz mono alignment WAV
        projects/<slug>/work/words.json    word-level alignment (transcribe.py)
        projects/<slug>/brief.json         (only for --check-chunks)
Writes  projects/<slug>/work/audio.json

Nothing downstream reads the audio today — captions are timed purely off
forced-alignment word starts, so a shouted word and a murmured one get the
identical spring. This measures four things per word/phrase, each derived
from THIS take rather than pinned:

  energy           RMS over the word's own span, normalised against the take
  pauses           inter-word gaps, split into "breath" vs "pause" by the
                   clip's OWN gap distribution — not a fixed constant, the
                   same reasoning palette.py uses for the caption ground
  speaking rate     words/sec and chars/sec per phrase (a phrase = the run of
                   words between two pauses)
  emphasis          energy + how much longer/shorter the word ran than this
                   take's own per-character average + how far its pitch moved

Only ffmpeg (already required elsewhere) and numpy (already a dependency of
palette.py / measure_scene.py / build_captions.py) are used. The alignment
audio is already a 16kHz mono PCM WAV (probe_and_extract.py's work/align.wav),
so it is read directly with the stdlib `wave` module — no second ffmpeg
decode, no new dependency.

Pitch is estimated with plain autocorrelation over 40ms frames. That is a
coarse F0 tracker, not a production one (no octave-jump correction, no
sub-sample interpolation) — it is used only for a per-word RANGE in
semitones, where coarse errors on unvoiced or very short frames wash out
rather than compound. A real pitch tracker (e.g. via `pyin`/`librosa`) would
be more accurate; it was not added because autocorrelation gets the range
signal cheaply and correctly enough to rank words against each other on THIS
take, which is all emphasis-scoring needs — it never compares pitch across
clips or in absolute Hz.
"""
import json, sys, wave
from pathlib import Path

import numpy as np

FPS = 30

# ---------------------------------------------------------------- pauses --


def pause_threshold(gaps: list[float]) -> float:
    """The gap length that separates "still mid-phrase" from "a real pause",
    derived from this clip's OWN distribution of inter-word gaps rather than a
    pinned constant — the same reasoning the caption ground and the panel
    feather use elsewhere in this pipeline.

    Sorted gaps cluster in two bands: a mass of short intra-phrase gaps (the
    tiny silence between consecutive words of one breath) and a handful of
    longer breaths/pauses between phrases. The boundary between the two bands
    is the largest multiplicative jump between consecutive sorted values —
    a one-dimensional version of a natural-breaks split. Clamped to
    [0.12s, 1.2s] so a clip with almost no pause variance (every gap nearly
    equal) does not collapse the threshold to ~0, and a clip with one huge
    outlier gap does not push it absurdly high.
    """
    if not gaps:
        return 0.25
    s = sorted(g for g in gaps if g > 0)
    if len(s) < 4:
        return float(min(1.2, max(0.12, s[-1] * 0.6 if s else 0.25)))
    best_i, best_ratio = None, 1.15   # require a REAL jump, not noise
    for i in range(1, len(s)):
        if s[i - 1] <= 0.02:
            continue
        ratio = s[i] / s[i - 1]
        if ratio > best_ratio:
            best_ratio, best_i = ratio, i
    thr = (s[best_i - 1] + s[best_i]) / 2 if best_i is not None else float(np.percentile(s, 70))
    return float(min(1.2, max(0.12, thr)))


# ------------------------------------------------------------- pitch/F0 ---


def _autocorr_f0(frame: np.ndarray, sr: int, fmin=70.0, fmax=400.0):
    """One F0 estimate (Hz) from a single windowed frame, or None if the frame
    does not look voiced. Plain time-domain autocorrelation: fast, no extra
    dependency, coarse — adequate for a per-word RANGE, not for absolute
    pitch."""
    frame = frame * np.hanning(len(frame))
    energy = float(np.sum(frame ** 2))
    if energy < 1e-6:
        return None
    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    lag_min, lag_max = int(sr / fmax), int(sr / fmin)
    if lag_max >= len(corr):
        return None
    window = corr[lag_min:lag_max]
    if window.size == 0:
        return None
    peak = int(np.argmax(window)) + lag_min
    if corr[0] <= 0 or corr[peak] / corr[0] < 0.30:   # too little periodicity: unvoiced
        return None
    return sr / peak


def word_pitch_range_semitones(samples: np.ndarray, sr: int) -> tuple[float, float | None]:
    """(range in semitones, mean Hz) of voiced F0 across one word's span.
    Range is 0.0 (not None) when the word is too short/unvoiced to say
    anything about pitch movement — that is a real measurement (flat), not a
    missing one."""
    frame_len, hop = int(sr * 0.04), int(sr * 0.02)
    f0s = []
    for start in range(0, max(1, len(samples) - frame_len), hop):
        f0 = _autocorr_f0(samples[start:start + frame_len].astype(np.float64), sr)
        if f0:
            f0s.append(f0)
    if len(f0s) < 2:
        return 0.0, (f0s[0] if f0s else None)
    lo, hi = min(f0s), max(f0s)
    return float(12 * np.log2(hi / lo)), float(np.mean(f0s))


# ------------------------------------------------------------------ main --


def load_pcm(wav_path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        assert w.getsampwidth() == 2 and w.getnchannels() == 1, (
            "expected 16-bit mono PCM WAV — probe_and_extract.py's align.wav "
            "changed format?")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return samples, sr


def measure(project: Path) -> dict:
    work = project / "work"
    clip = json.loads((work / "clip.json").read_text())
    words = json.loads((work / "words.json").read_text())["words"]
    samples, sr = load_pcm(Path(clip["alignAudio"]))

    def span(w):
        a, b = int(w["start"] * sr), int(w["end"] * sr)
        a, b = max(0, a), min(len(samples), max(a + 1, b))
        return samples[a:b]

    rms = [float(np.sqrt(np.mean(span(w) ** 2))) if span(w).size else 0.0 for w in words]
    rms_p90 = float(np.percentile(rms, 90)) if rms else 1.0
    rms_p90 = rms_p90 or 1.0
    energy_norm = [min(1.5, r / rms_p90) for r in rms]

    # Expected duration per character, from THIS take's own words — a clip
    # spoken quickly has a shorter "normal" per-char duration than one spoken
    # deliberately, so the ratio stays a ratio, not an absolute clock.
    per_char = [ (w["end"] - w["start"]) / max(1, len(w["word"].strip(".,?!")))
                 for w in words if len(w["word"].strip(".,?!")) > 0 ]
    expected_per_char = float(np.median(per_char)) if per_char else 0.12
    duration_ratio = []
    for w in words:
        chars = max(1, len(w["word"].strip(".,?!")))
        expected = expected_per_char * chars
        actual = w["end"] - w["start"]
        duration_ratio.append(actual / expected if expected > 0 else 1.0)

    pitch_range, pitch_mean = [], []
    for w in words:
        r, m = word_pitch_range_semitones(span(w), sr)
        pitch_range.append(r)
        pitch_mean.append(m)

    def norm01(xs):
        xs = np.array(xs, dtype=float)
        lo, hi = float(xs.min()), float(xs.max())
        if hi - lo < 1e-9:
            return [0.5] * len(xs)
        return list((xs - lo) / (hi - lo))

    en_n = norm01(energy_norm)
    dr_n = norm01(duration_ratio)
    pr_n = norm01(pitch_range)
    emphasis = [round(0.4 * e + 0.3 * d + 0.3 * p, 4) for e, d, p in zip(en_n, dr_n, pr_n)]

    gaps = [round(words[i + 1]["start"] - words[i]["end"], 4) for i in range(len(words) - 1)]
    thr = pause_threshold(gaps)

    # Phrases: runs of words separated by a measured pause.
    phrases = []
    start_i = 0
    for i, g in enumerate(gaps):
        if g >= thr:
            phrases.append((start_i, i))
            start_i = i + 1
    phrases.append((start_i, len(words) - 1))

    phrase_out = []
    for a, b in phrases:
        if b < a:
            continue
        dur = words[b]["end"] - words[a]["start"]
        wc = b - a + 1
        chars = sum(len(words[j]["word"].strip(".,?!")) for j in range(a, b + 1))
        phrase_out.append({
            "startIndex": a, "endIndex": b,
            "startSeconds": round(words[a]["start"], 3),
            "endSeconds": round(words[b]["end"], 3),
            "wordCount": wc, "charCount": chars,
            "durationSeconds": round(dur, 3),
            "wordsPerSecond": round(wc / dur, 3) if dur > 0 else 0.0,
            "charsPerSecond": round(chars / dur, 3) if dur > 0 else 0.0,
        })

    words_out = []
    for i, w in enumerate(words):
        words_out.append({
            "index": i, "word": w["word"],
            "start": w["start"], "end": w["end"],
            "rms": round(rms[i], 5),
            "energyNorm": round(energy_norm[i], 4),
            "durationRatio": round(duration_ratio[i], 4),
            "pitchRangeSemitones": round(pitch_range[i], 3),
            "pitchMeanHz": round(pitch_mean[i], 1) if pitch_mean[i] else None,
            "emphasis": emphasis[i],
        })

    return {
        "meta": {"sourceAudio": clip["alignAudio"], "sampleRate": sr, "fps": FPS,
                 "wordCount": len(words)},
        "takeStats": {
            "rmsP90": round(rms_p90, 5),
            "expectedSecondsPerChar": round(expected_per_char, 4),
            "pauseThresholdSeconds": round(thr, 4),
        },
        "words": words_out,
        "gaps": gaps,
        "phrases": phrase_out,
    }


# ------------------------------------------------------- chunk-boundary check


def check_chunk_boundaries(brief: dict, words: list, audio: dict) -> list[str]:
    """Warn when a brief's hand-written chunk break lands inside continuous
    speech rather than in a measured pause. Returns human-readable warning
    lines; does not raise or mutate anything — build_captions decides what to
    do with them (print, like the existing skip-candidate report).

    A boundary is "in a real pause" when the gap immediately before the next
    beat's first word is at least 60% of this clip's measured pause
    threshold. 60%, not 100%: forced-alignment word starts are accurate to
    about one frame, and a beat break is often placed a syllable early on
    purpose to give the reveal a head start, which eats a few tens of ms of
    what would otherwise read as the pause.
    """
    thr = audio["takeStats"]["pauseThresholdSeconds"]
    tol = 0.6 * thr
    specs = brief.get("chunks", [])
    warnings = []
    for n in range(len(specs) - 1):
        cur, nxt = specs[n], specs[n + 1]
        cur_words = (cur.get("lead") or []) + (cur.get("key") or [])
        nxt_words = (nxt.get("lead") or []) + (nxt.get("key") or [])
        if not cur_words or not nxt_words:
            continue
        last_i, first_i = max(cur_words), min(nxt_words)
        if last_i >= len(words) or first_i >= len(words) or first_i <= last_i:
            continue
        gap = words[first_i]["start"] - words[last_i]["end"]
        if gap < tol:
            warnings.append(
                f"beat {n + 1}->{n + 2}: boundary gap {gap:.2f}s is inside "
                f"continuous speech (pause threshold {thr:.2f}s, need >= "
                f"{tol:.2f}s) — \"{words[last_i]['word']}\" runs straight "
                f"into \"{words[first_i]['word']}\"")
    return warnings


# Excluded when ranking words for the PAYLOAD role. Measured on the four
# shipped clips: unfiltered, the top emphasis score is a function word on
# 4 of 4 takes ("of", "is", "in", "Is") — pitch and duration on a short
# connective are a real acoustic signal (she does lean on them) but they are
# never what should go large on screen. This list is short and closed on
# purpose: it removes the connectives that kept winning, not an attempt at
# general stopword filtering.
_PAYLOAD_SKIP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "of", "in", "on",
    "to", "for", "and", "or", "so", "if", "that", "this", "it", "as",
    "with", "at", "by", "from", "but", "not",
}


def suggest_payload_word(word_indices: list[int], audio: dict) -> int | None:
    """The acoustically emphasised word among a beat's own words — usually
    the one that deserves the big type. Connectives are excluded first (see
    `_PAYLOAD_SKIP` — unfiltered, they won on every shipped clip); ties
    broken toward the LATER word, since the punchline tends to land at the
    end of a phrase."""
    if not word_indices:
        return None
    by_index = {w["index"]: w["emphasis"] for w in audio["words"]}
    content = [(by_index.get(i, 0.0), i) for i in word_indices
               if i in by_index and by_index_word(audio, i) not in _PAYLOAD_SKIP]
    scored = content or [(by_index.get(i, 0.0), i) for i in word_indices if i in by_index]
    if not scored:
        return None
    best = max(scored)
    return max(i for s, i in scored if s == best[0])


def by_index_word(audio: dict, i: int) -> str:
    w = audio["words"][i]["word"] if i < len(audio["words"]) else ""
    return w.strip(".,?!").lower()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = Path(sys.argv[1])
    audio = measure(project)
    (project / "work" / "audio.json").write_text(json.dumps(audio, indent=2))

    ts = audio["takeStats"]
    print(f"wrote {project/'work'/'audio.json'}")
    print(f"  {audio['meta']['wordCount']} words, pause threshold "
          f"{ts['pauseThresholdSeconds']:.2f}s (derived from this clip's own "
          f"gap distribution), {ts['expectedSecondsPerChar']:.3f}s/char baseline")
    print(f"  {len(audio['phrases'])} phrases; speaking rate "
          f"{min(p['wordsPerSecond'] for p in audio['phrases']):.2f}-"
          f"{max(p['wordsPerSecond'] for p in audio['phrases']):.2f} words/s")
    top = sorted(audio["words"], key=lambda w: -w["emphasis"])[:5]
    print("  most emphasised words:")
    for w in top:
        print(f"    \"{w['word']}\"  emphasis {w['emphasis']:.2f}  "
              f"(energy {w['energyNorm']:.2f}, duration x{w['durationRatio']:.2f}, "
              f"pitch range {w['pitchRangeSemitones']:.1f} st)")

    if "--check-chunks" in sys.argv:
        brief_path = project / "brief.json"
        if not brief_path.exists():
            print("\n  no brief.json to check")
        else:
            brief = json.loads(brief_path.read_text())
            words = json.loads((project / "work" / "words.json").read_text())["words"]
            warnings = check_chunk_boundaries(brief, words, audio)
            if warnings:
                print(f"\n  CHUNK BOUNDARY WARNINGS ({len(warnings)}) — these breaks "
                      f"land inside continuous speech, not in a measured pause:")
                for w in warnings:
                    print(f"   {w}")
            else:
                print("\n  all chunk boundaries land in a measured pause")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
