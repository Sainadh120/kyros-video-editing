#!/usr/bin/env python3
"""Word-level alignment of the clip's audio.

    python scripts/transcribe.py projects/<slug>

Prefers whisperx (wav2vec2 forced alignment, needs torch); falls back to
faster-whisper word timestamps, which is torch-free and accurate to about
one frame at 30fps.

Writes work/words.json and prints the transcript. ALWAYS read the transcript
back to Niranjan before building anything on top of it.
"""
import json, sys
from pathlib import Path

FPS = 30


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = Path(sys.argv[1])
    work = project / "work"
    meta = json.loads((work / "clip.json").read_text())
    audio = meta["alignAudio"]

    words, backend = [], None
    try:
        import whisperx, torch  # noqa
        backend = "whisperx"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisperx.load_model(
            "small.en", device,
            compute_type="float16" if device == "cuda" else "int8")
        a = whisperx.load_audio(audio)
        res = model.transcribe(a, batch_size=8)
        amodel, amdata = whisperx.load_align_model(
            language_code=res["language"], device=device)
        aligned = whisperx.align(res["segments"], amodel, amdata, a, device,
                                 return_char_alignments=False)
        for seg in aligned["segments"]:
            for w in seg.get("words", []):
                if w.get("start") is None:
                    continue
                words.append({"word": w["word"].strip(),
                              "start": float(w["start"]),
                              "end": float(w["end"]),
                              "score": float(w.get("score", 1.0))})
    except ImportError:
        from faster_whisper import WhisperModel
        backend = "faster-whisper"
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            audio, word_timestamps=True, beam_size=5, vad_filter=False,
            condition_on_previous_text=False)
        for seg in segments:
            for w in (seg.words or []):
                words.append({"word": w.word.strip(),
                              "start": float(w.start), "end": float(w.end),
                              "score": float(getattr(w, "probability", 1.0))})

    for w in words:
        w["startFrame"] = round(w["start"] * FPS)
        w["endFrame"] = round(w["end"] * FPS)

    (work / "words.json").write_text(
        json.dumps({"backend": backend, "fps": FPS, "words": words}, indent=2))

    print(f"backend {backend}   {len(words)} words\n")
    print(" ".join(w["word"] for w in words))
    print("\nlargest pauses (candidate question/answer and chunk boundaries):")
    gaps = sorted(
        ((words[i + 1]["start"] - words[i]["end"], i) for i in range(len(words) - 1)),
        reverse=True)[:5]
    for gap, i in gaps:
        print(f"   {gap:5.2f}s after \"{words[i]['word']}\" "
              f"(frame {words[i]['endFrame']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
