# Pipeline

Technical detail behind the steps in SKILL.md. The gotchas near the bottom all
come from bugs that shipped past visual inspection.

## Chunking

Two to four words on screen, split into a quiet **lead** and a large
**payload**. The payload carries the medical point.

Working from a transcript:

1. Split question from answer at the largest pause in the first half.
2. Split the answer at sentence boundaries — one idea per part.
3. Inside each part, find the clinical entities and the statistics. Those
   become payloads; the connective words around them become leads.
4. A chunk runs from its first word's frame until the next chunk's first word.
   Never gap them — the screen shouldn't go empty mid-sentence.
5. A chunk can be payload-only. A repeated key phrase landing alone is strong.

A worked example:

```
Majority of women with   ->  PCOS
has                      ->  INSULIN / RESISTANCE
that is around           ->  65–70%
So that's why            ->  ONE MUST / ADDRESS THIS
                             INSULIN / RESISTANCE
before starting a        ->  TREATMENT / OF PCOS
```

Propose this as plain text and wait for approval before rendering.

## Sizing

Solve the payload size from character count rather than hardcoding it, so short
words go large and long ones stay inside the column:

```python
size = clamp(column_width / (longest_line_len * advance_em), min_size, ceiling)
```

`advance_em ≈ 0.47` for condensed caps. Ceiling around 240px for a single line,
178px for two — two lines at full size overflow the zone vertically.

Break long payloads into two lines by hand (`INSULIN / RESISTANCE`). Stacked
reads better and allows a larger size than one cramped line.

## Layout

- 1080×1920, 30fps.
- Text zone stops short of the subject's head — `measure_scene.py` reports it.
- Platform UI covers the top and bottom 15%. Keep type outside both.
- Every position, size and colour lives in the data file. A reposition should
  be a number change, never a code change.

## Gotchas

**A video that plays one frame forever.** In Remotion, `OffthreadVideo` without
a `Sequence` wrapper takes its time from the composition timeline. An end card
entering at frame 491 asked a 3-second clip for its frame at 16.4s — past the
end — so it held the last frame. It looked like a still and read as intentional.
Wrap it: `<Sequence from={enterFrame} durationInFrames={n}>`.

**Invisible things still take up space.** An element revealed by a clip-path
wipe or held at zero opacity still occupies layout. A stat card sat as an empty
coloured box for seconds before its number arrived. Either render a ghost of the
content underneath at low opacity, or bring the container in with the content.

**CSS keyframes freeze at t=0.** Remotion renders each frame in a fresh page, so
an animated SVG loaded through `<img>` never advances. Inline it, pause the
animation, and drive `animation-delay` from the frame:

```
animation-play-state: paused;
animation-delay: -{elapsedSeconds}s;
```

Clamp the scrub to one cycle if the animation loops — a bar pulsing for the
whole video pulls focus off the type.

**Position by the artwork, not the file.** Supplied PNGs carry transparent
padding. Measure the visible bounding box and offset by it, so `left` and `top`
mean where the artwork lands.

**A working transparent WebM looks broken.** VP8 stores alpha in a WebM
side-channel, so `ffprobe` reports `yuv420p` on a perfectly good file, and
ffmpeg's default vp8 decoder silently drops the channel — composite it over a
colour and you get opaque black. Decode with `-c:v libvpx` before concluding
anything, and look for the `alpha_mode=1` tag. Don't "fix" a file that was
never broken.

**Fades bleed across cuts.** A caption's fade-out running past the end card's
entry puts text over the end card. Gate the whole body off once the end card
starts, and end the last chunk before that frame.

## Verification

Run these rather than trusting a glance:

- **Motion**: hash three frames inside any clip. Identical hashes mean frozen.
- **Alpha**: composite the overlay over magenta and check the colour shows
  through. Sampling mean alpha per region also works — transparent areas read
  0, opaque cards 255 — but for .webm you must force `-c:v libvpx` first.
- **Fixture timing**: sample where a plate should be visible *and* where it
  should be gone. 192/255 then 0/255 proves it left.
- **Contrast**: recompute the ratio for the final palette against the measured
  background.
- **Duration**: confirm against the intended frame count.

Report the numbers. "Looks right" is what let all three gotchas above ship.
