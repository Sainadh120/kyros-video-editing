# Intake

Ask these before transcribing. Confirm the ones already answered — reading a
detail back costs a sentence, and getting it wrong costs a re-render.

Don't fire all of these as a wall of text. Group them, lead with what you can
already see from the files, and ask only about the genuine gaps. Ending with
"anything else about this one I should know?" catches things no list predicts.

## 1. The clip

- Which file, and is its audio the take you want captioned? *(Verify yourself:
  probe the duration and read the transcript back. A clip has arrived before
  that was a different Q&A from the one described.)*
- Is there a question spoken at the top, or does she start straight into the
  answer?
- Should the doctor be hidden while the question is on screen, or stay visible?

## 2. The doctor

- Full name, qualification, specialty. *(Registration details are handled at
  consultation and are not shown on screen — don't ask for a number.)*
- Is there a name-plate asset, or should one be built? *(Check
  `reels.py library _` first — if this doctor is already on file, her plate and
  details are stored and you only need to confirm them, not re-request them.)*
- How long should the plate hold, and where? *(Past choice: bottom-left, ~1.9s
  as she begins the answer, then gone. It should not sit there all video.)*

## 3. The partner clinic

The pairing changes every clip — Dr. Bharani with Aster Ramesh today, Dr.
Krishna with Krishna Clinic next. Never carry the last one forward.

- Which clinic is this doctor's, and what's the exact name as it should read?
  *(Each doctor record carries a `defaultPartner`; confirm it still holds rather
  than asking from scratch.)*
- Logo asset? Ask for **PNG at 1500px+ or SVG**. Say why: a small JPEG forced a
  3.3× upscale once and the partner's mark rendered soft. A better file arrived
  in a minute and the problem vanished.
- Does the partner cut carry their mark during the video, or only on the end
  card? *(Past choice: end card only.)*
- End card: a clip, or a still? For how long? *(Past: Kyros 3s clip played as
  delivered; partner 1s still.)*

## 4. Timing and placement

Niranjan often specifies this himself, second by second. Use exactly what he
gives — he is describing something he can already picture.

- Which time ranges carry text, and where does it sit in each — top or bottom?
- Anything that must be on screen at an exact moment?
- **If a section has no instruction, ask.** Don't infer placement for one part
  from another.

Write every answer into `brief.json`, including corrections. It's the record
that stops you re-asking settled questions next time.

## 5. Style

- Anything specific in mind, or should you propose one? See `styles.md`.
- Reference screenshots to match? Ask for them — they resolve in one image what
  a paragraph of description can't.
- Anything from last time to avoid repeating?

## 6. Output

- Just the posted `.mp4`, or transparent overlays too? *(Overlays cost about
  half the render time and several hundred MB. Most weeks he doesn't need them
  — ask rather than producing them by default.)*
- Instagram, YouTube, both? Affects safe-area margins.
- Both cuts this time, or only one?

## Folder convention

```
projects/<clip-slug>/
  inbox/          clip, doctor plate, partner logo, outro assets
  brief.json      every answer, written as collected
  out/            finished files
```

Tell him the folder path and exactly which files to drop in. Before starting,
list what has arrived and what is still missing — a short checklist beats
discovering a gap halfway through a render.
