#!/usr/bin/env python3
"""Probe a supplied clip and extract its audio twice.

    python scripts/probe_and_extract.py projects/<slug>/inbox/<clip>

Writes alignment audio (16kHz mono WAV) and playback audio (48kHz AAC) beside
the project, and prints what it found. Read the printed duration back to
Niranjan — a clip has arrived before that was a different take from the one
described.
"""
import json, subprocess, sys
from pathlib import Path


def probe(path: Path) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path)])
    return json.loads(out)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    clip = Path(sys.argv[1])
    if not clip.exists():
        print(f"no such file: {clip}")
        return 1

    project = clip.parent.parent
    work = project / "work"
    work.mkdir(parents=True, exist_ok=True)

    info = probe(clip)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])

    if video is None:
        print("no video stream")
        return 1

    w, h = int(video["width"]), int(video["height"])
    num, den = (video.get("r_frame_rate") or "30/1").split("/")
    fps = round(float(num) / float(den), 3)

    print(f"clip      {clip.name}")
    print(f"size      {w}x{h}   aspect {w/h:.4f}   (9:16 = {9/16:.4f})")
    print(f"fps       {fps}")
    print(f"duration  {duration:.3f}s  ->  {round(duration * 30)} frames at 30fps")
    print(f"audio     {'yes' if audio else 'NO AUDIO STREAM'}")

    if abs(w / h - 9 / 16) > 0.01:
        print(f"\n  NOTE: not 9:16. Ask how to frame it before rendering.")

    if audio is None:
        print("\n  No audio to transcribe. Ask Niranjan for the take with sound.")
        return 1

    align = work / "align.wav"
    play = work / "playback.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                    str(align)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip),
                    "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-ac", "2", str(play)], check=True)

    meta = {"clip": str(clip), "width": w, "height": h, "sourceFps": fps,
            "durationSeconds": round(duration, 3),
            "frames30": round(duration * 30),
            "alignAudio": str(align), "playbackAudio": str(play)}
    (work / "clip.json").write_text(json.dumps(meta, indent=2))
    print(f"\nwrote {work/'clip.json'}, {align.name}, {play.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
