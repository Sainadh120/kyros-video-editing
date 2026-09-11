# Style

Niranjan's constraint, in his words: *"It should not feel monotone or boring,
because people should not think this is very boring content."*

The clips arrive nearly identical — same framing, same pacing, one doctor
answering one question. If the treatment is also identical, the feed becomes
one template on repeat and people scroll past. **Variation is part of the
brief.**

The trap is variation that reads as inconsistency. What follows keeps the
skeleton fixed — word-synced, two registers, measured contrast, type over
footage — and varies the surface.

## The five axes

Change two or three between reels. Changing one is invisible; changing all
five makes the account look like five different accounts.

**1. Type pairing** — the contrast between lead and payload is the whole look.
- Italic serif lead + condensed caps payload *(Playfair Display Italic / Anton)*
- Light grotesque lead + heavy grotesque payload *(DM Sans 300 / DM Sans 900)*
- Small-caps serif lead + display serif payload *(Cormorant SC / Fraunces)*
- Mono lead + condensed caps payload *(JetBrains Mono / Oswald)*

**2. Where text sits** — top over clear background, lower third, or centred
full-bleed for a hook. Driven by where the subject's head actually is, which
`measure_scene.py` reports.

**3. Reveal mechanic**
- Clip-path mask wipe, left to right
- Word cascade, each word landing on its own beat
- Line-by-line rise with the payload snapping in
- Whole chunk cross-dissolving, payload scaling slightly

**4. Payload treatment** — plain caps; caps on a filled block; caps with a rule
drawing beneath; stacked over two lines; numeral oversized against small words.

**5. Accent colour** — always from the measured palette, never picked by eye.
Rotating *which* passing colour carries the payload changes the feel at zero
risk to legibility.

## Rotation

Read the last two or three `brief.json` files before proposing. Record the
combination used under `"style"`. Don't repeat the previous reel's pairing and
mechanic together.

When a reel lands especially well, note that too — a style that works is worth
returning to after a gap, just not next in line.

## What doesn't vary

These aren't stylistic, they're what makes the reels readable and legally
publishable:

- Contrast comes from measurement. A style that needs white on a light wall is
  not available on that wall — pick another, or add a scrim and re-measure.
- Two to four words on screen. Density is the difference between a reel and a
  document.
- Word-synced to the audio.
- Clear of the platform's top and bottom 15% UI bands.
- Registration number on screen for a doctor on camera.

## Matching a reference

Reference screenshots resolve in one image what a paragraph can't — ask for
them. But adapt rather than copy: the references that led to the current look
were white-on-dark, and the wall in that footage was light. The *structure*
transferred, the palette had to invert.
