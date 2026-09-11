#!/usr/bin/env python3
"""Check a finished render with numbers instead of a glance.

    python scripts/verify_render.py projects/<slug>/out [--expect-seconds 19.4]

Three bugs shipped past visual inspection before this existed: an end card that
held one frame forever, a stat card that sat as an empty box, and a logo at
1.6:1 against the wall. Each was invisible to the eye and obvious to a hash.
"""
import hashlib, subprocess, sys
from pathlib import Path


def probe(path: Path, entries: str, stream: bool = False) -> str:
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)]
    return subprocess.check_output(cmd).decode().strip()


def frame_digest(path: Path, at: float) -> str:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
         "-vf", "scale=64:114", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    return hashlib.md5(raw).hexdigest()[:12] if raw else "unreadable"


def mean_alpha(path: Path, at: float, crop: str):
    """Mean alpha of a region, 0 transparent to 255 opaque."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
         "-vf", f"crop={crop},alphaextract,scale=1:1", "-f", "rawvideo",
         "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return raw[0] if raw else None


def alpha_really_works(path: Path, at: float) -> bool:
    """Composite over magenta and look for it showing through.

    Checking pix_fmt is not enough. VP8 keeps alpha in a WebM side-channel, so
    a perfectly good transparent .webm still reports yuv420p — and ffmpeg's
    default vp8 decoder silently drops that channel, which makes a working file
    look broken. Forcing libvpx is what actually reads it.
    """
    pre = ["-c:v", "libvpx"] if path.suffix == ".webm" else []
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", "color=magenta:s=1080x1920:d=1"] + pre +
        ["-ss", str(at), "-i", str(path),
         "-filter_complex",
         "[0:v][1:v]overlay=0:0,crop=300:300:0:0,scale=1:1[o]",
         "-map", "[o]", "-frames:v", "1", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(out) < 3:
        return False
    r, g, b = out[0], out[1], out[2]
    return r > 200 and b > 200 and g < 80


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    expect = None
    if "--expect-seconds" in sys.argv:
        expect = float(sys.argv[sys.argv.index("--expect-seconds") + 1])

    videos = sorted(p for p in out.glob("*") if p.suffix in {".mp4", ".mov", ".webm"})
    if not videos:
        print(f"nothing to check in {out}")
        return 1

    failures = 0
    for v in videos:
        dur = float(probe(v, "format=duration"))
        print(f"\n=== {v.name} ===")
        print(f"duration {dur:.2f}s   {probe(v, 'stream=width,height', True).replace(chr(10), 'x')}")

        if expect and abs(dur - expect) > 0.15:
            print(f"  MISMATCH: expected ~{expect}s")
            failures += 1

        if v.suffix in {".mov", ".webm"}:
            prof = probe(v, "stream=profile,pix_fmt", True).replace("\n", ", ")
            works = alpha_really_works(v, dur * 0.5)
            print(f"alpha    {prof}  -> "
                  f"{'transparent where it should be' if works else 'OPAQUE'}")
            if not works:
                print("  WARNING: this overlay will not composite — it is opaque.")
                print("  For .webm remember VP8 hides alpha in a side-channel;")
                print("  decode with -c:v libvpx before concluding it is broken.")
                failures += 1

        # Motion: three points across the last third, where end cards live.
        print("motion in the final third (identical digests = frozen):")
        marks = [dur * 0.70, dur * 0.82, dur * 0.94]
        digests = [frame_digest(v, t) for t in marks]
        for t, d in zip(marks, digests):
            print(f"   {t:5.2f}s  {d}")
        if len(set(digests)) == 1:
            print("   FROZEN — if a clip should be playing here, it is not.")
            print("   Check for an OffthreadVideo without a <Sequence> wrapper.")
            failures += 1
        else:
            print("   moving")

    print("\n" + ("all checks passed" if not failures
                  else f"{failures} problem(s) — do not ship until resolved"))
    print("\nStill to check by hand, with numbers not eyes:")
    print("  - fixture timing: sample where a plate should be visible AND where")
    print("    it should be gone (192/255 then 0/255 proves it left)")
    print("  - contrast of the final palette against the measured background")
    print("  - nothing from the body bleeding onto the end card")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
