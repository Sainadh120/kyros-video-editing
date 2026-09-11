#!/usr/bin/env python3
"""Reels CLI — one command per stage, so nothing has to be re-derived.

    reels.py library _           list the doctors and partner clinics on file
    reels.py new <slug>          create the project folder, list what to drop in
    reels.py prep <slug>         probe, extract audio, transcribe, measure, scan
    reels.py build <slug>        brief.json + alignment -> captions_data.json
    reels.py stage <slug>        swap this clip's assets into the studio
    reels.py render <slug> [kyros|partner] [--overlays]   render the posted videos
    reels.py verify <slug>       check the renders with numbers
    reels.py check _             run the rule suite (colour, placement, motion,
                                 type, audio, register, delivery, visuals)
    reels.py visuals <slug>      the supporting-visuals plan (brief.visuals)
             [--approve all|v1,v2] [--reject v3]
             [--generate [--only v1,v2] [--retry]]   through the toolkit on Modal
             [--preview]                             contact sheet of what was generated

`prep` also scans the raw clip for anything already burned into it (graphics,
lower-thirds, on-screen text), derives the caption palette from the measured
background, and proposes the next clip's REGISTER — question card, ground
polarity, lead style, palette lead, and (once populated) type pairing and
reveal style — read from the prior briefs so it differs from the last two
reels automatically (see README "The register"). `build` reads all of that:
it drops each caption to whichever half of the frame is clear at that moment,
solves the doctor plate's and the mark's placement against every hazard as
real rectangles rather than a zone name, and colours each beat from an
APCA-checked elegant mix that adapts to this clip's wall and saree — no
placement or colour is hand-figured. A clip with a clean wall throughout
scans clear and keeps the original top layout.

`render <slug> kyros` and `render <slug> partner` render one cut at a time.
Finish and sign off the Kyros cut before rendering the partner one.

Typical clip, start to finish:

    reels.py new pcos-thyroid-link
    # drop the clip, doctor plate and partner logo into inbox/, fill brief.json
    reels.py prep pcos-thyroid-link     # read the transcript back to Niranjan
    # agree the chunk breakdown, write it into brief.json
    reels.py build  pcos-thyroid-link
    reels.py stage  pcos-thyroid-link
    reels.py render pcos-thyroid-link
    reels.py verify pcos-thyroid-link

The Kyros mark and outro live in brand/ and are shared by every clip — they are
staged automatically and never belong in a project's inbox.
"""
import hashlib, json, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO, BRAND, PROJECTS = ROOT / "studio", ROOT / "brand", ROOT / "projects"
KYROS, DOCTORS, PARTNERS = BRAND / "kyros", BRAND / "doctors", BRAND / "partners"

BRIEF_TEMPLATE = {
    "slug": "",
    "clip": "inbox/<clip>.mp4",
    "doctor": "<doctor-id from brand/doctors/>",
    "partner": None,   # None uses the doctor's defaultPartner

    "palette": {"_comment": "fill from `reels.py prep` output — measured, not chosen",
                "scene": {"wall": "", "wallShadow": ""},
                "onLight": {"lead": "", "key": "", "keyAlt": "", "muted": ""},
                "onDark": {"scrim": "#1C1410", "lead": "#FFF6E8",
                           "key": "#E8A33C", "keyAlt": "#F2C879", "muted": "#C9B39A"}},
    "question": {"scrimOpacity": 0.94, "rows": []},
    "chunks": [],
    # Placement is automatic: `prep` scans the clip for burned-in graphics and
    # `build` drops each beat to the clear half. Override only if you must —
    # a per-chunk "zone": "top"|"bottom", or a "layout" block tuning
    # bottomZone / captionScrim / doctorPlate.appearFrame.
    "style": {"_comment": "see references/styles.md — vary 2-3 axes from last "
              "time. textPosition is dynamic when the clip has burned-in graphics.",
              "typePairing": "", "textPosition": "", "revealMechanic": "",
              "payloadTreatment": "", "accent": ""},
    "openFlags": [],
}


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def library():
    docs = sorted(d.name for d in DOCTORS.iterdir() if d.is_dir()) if DOCTORS.exists() else []
    pars = sorted(d.name for d in PARTNERS.iterdir() if d.is_dir()) if PARTNERS.exists() else []
    return docs, pars


def cmd_library(_=None):
    docs, pars = library()
    print("doctors (brand/doctors/) — plate and details stored once, reused every clip")
    for d in docs:
        rec = json.loads((DOCTORS / d / "doctor.json").read_text())
        print(f"   {d:22s} {rec['name']} — {rec['title']}")
        print(f"   {'':22s} usual partner: {rec.get('defaultPartner', '(none set)')}")
    print("\npartner clinics (brand/partners/)")
    for pn in pars:
        rec = json.loads((PARTNERS / pn / "partner.json").read_text())
        print(f"   {pn:22s} {rec['name']}")
    print("\nTo add a doctor:   brand/doctors/<id>/{plate.png, doctor.json}")
    print("To add a partner:  brand/partners/<id>/{logo.png, partner.json}")
    print("Copy an existing folder as the template.")
    return 0


def cmd_new(slug):
    p = PROJECTS / slug
    (p / "inbox").mkdir(parents=True, exist_ok=True)
    (p / "work").mkdir(exist_ok=True)
    (p / "out").mkdir(exist_ok=True)
    brief = p / "brief.json"
    if not brief.exists():
        t = dict(BRIEF_TEMPLATE, slug=slug)
        brief.write_text(json.dumps(t, indent=2))
    docs, _ = library()
    print(f"created {p}\n")
    print("Drop into inbox/:  the clip (vertical mp4). That is all.\n")
    print("Everything else comes from the library and is staged for you:")
    print("   the Kyros mark and outro          brand/kyros/")
    print("   the doctor's plate and details    brand/doctors/<id>/")
    print("   the partner clinic's logo         brand/partners/<id>/")
    print(f"\nDoctors on file: {', '.join(docs) or '(none yet — run: reels.py library _)'}")
    print(f"\nSet \"doctor\" in {brief} to one of those ids, then:")
    print(f"   reels.py prep {slug}")


def cmd_prep(slug):
    p = PROJECTS / slug
    brief = json.loads((p / "brief.json").read_text())
    clip = p / brief["clip"]
    if not clip.exists():
        print(f"clip not found: {clip}")
        return 1
    sh([sys.executable, str(ROOT / "scripts/probe_and_extract.py"), str(clip)])
    print("\n" + "=" * 60 + "\n")
    sh([sys.executable, str(ROOT / "scripts/transcribe.py"), str(p)])
    print("\n" + "=" * 60 + "\n")
    sh([sys.executable, str(ROOT / "scripts/measure_scene.py"), str(p)])
    print("\n" + "=" * 60 + "\n")
    # Listen to the take, not just to what she said: per-word energy, the
    # pauses she actually leaves, and which words she leans on. `build` reads
    # work/audio.json for style.autoMotion and for the boundary check, and
    # both go quiet if the file is missing — so this runs here, unconditionally,
    # rather than being something to remember. --check-chunks reports beat
    # boundaries that land mid-phrase while the breakdown is still being
    # agreed, which is the only moment the report is any use.
    sh([sys.executable, str(ROOT / "scripts/measure_audio.py"), str(p),
        "--check-chunks"])
    print("\n" + "=" * 60 + "\n")
    # Read the raw clip for anything already burned into it — illustrations,
    # lower-thirds, on-screen text. Captions then drop to the clear half on
    # their own; nothing about placement has to be hand-figured.
    sh([sys.executable, str(ROOT / "scripts/scan_overlays.py"), str(p)])
    print("\n" + "=" * 60 + "\n")
    # Derive the caption palette from the measured background: an APCA-checked,
    # elegant multi-colour mix that adapts to this clip's wall and saree.
    sh([sys.executable, str(ROOT / "scripts/palette.py"), str(p)])
    print("\n" + "=" * 60 + "\n")
    # The register: propose the axes that make this reel look unmistakably
    # different from the last two, before "Decision two — the style" gets
    # made. Wired here rather than into `build` because by the time `build`
    # runs, brief.json's question/style choices are already written — a
    # proposal at that point would be too late to act on, only a report of
    # what was already decided.
    sh([sys.executable, str(ROOT / "scripts/register.py"), slug])
    print("\n" + "=" * 60)
    print("NEXT: read the transcript back to Niranjan and confirm it is the")
    print("right take. Then agree the chunk breakdown and write it into")
    print(f"{p/'brief.json'}, along with the measured palette above. Caption")
    print("placement (top vs low) follows the overlay scan automatically, and")
    print("the register above proposes the rest — a brief that pins an axis")
    print("still wins.")
    print("With the chunking, propose supporting visuals in brief.visuals (the")
    print("kyros-doctor-reels skill, references/visuals.md), then:")
    print(f"   reels.py visuals {slug}")
    return 0


def cmd_build(slug):
    return sh([sys.executable, str(ROOT / "scripts/build_captions.py"),
               str(PROJECTS / slug)]).returncode


def cmd_stage(slug):
    """Swap this clip's assets into the studio so the compositions see them."""
    p = PROJECTS / slug
    brief = json.loads((p / "brief.json").read_text())
    pub = STUDIO / "public"
    pub.mkdir(exist_ok=True)

    doc_id = brief["doctor"]
    doc = json.loads((DOCTORS / doc_id / "doctor.json").read_text())
    par_id = brief.get("partner") or doc["defaultPartner"]
    par = json.loads((PARTNERS / par_id / "partner.json").read_text())

    shutil.copy(p / brief["clip"], pub / "video.mp4")
    shutil.copy(p / "work/playback.m4a", pub / "audio.m4a")
    shutil.copy(DOCTORS / doc_id / doc["plate"], pub / "doctor-plate.png")
    shutil.copy(PARTNERS / par_id / par["logo"], pub / "partner-logo.png")
    shutil.copy(KYROS / "outro.mp4", pub / "outro.mp4")
    shutil.copy(p / "work/captions_data.json", STUDIO / "src/captions_data.json")
    # Supporting visuals: exactly the files this build references, and nothing
    # left over from the previous clip. A clip without visuals stages none.
    import visuals as visuals_engine
    visuals_engine.stage_assets(
        p, json.loads((p / "work/captions_data.json").read_text()), pub)

    # The animated mark is inlined, not <img>-loaded: Remotion renders each
    # frame in a fresh page, so a CSS keyframe animation in an <img> stays
    # frozen at t=0. Inlining lets it be scrubbed from the frame number.
    svg = (KYROS / "mark-animated.svg").read_text(encoding="utf-8")
    (STUDIO / "src/kyrosSting.ts").write_text(
        "/* AUTO-GENERATED by reels.py stage — do not edit. */\n"
        "export const KYROS_STING_SVG = " + json.dumps(svg) + ";\n",
        encoding="utf-8")

    # A receipt of what is in the studio right now. `render` copies it beside
    # the video it produces, which is what finally makes "was this cut built
    # from this data?" a question with an answer. Skipping `stage` used to be
    # undetectable: the render succeeded, verify passed, and the change was
    # silently absent.
    digest = hashlib.md5((p / "work/captions_data.json").read_bytes()).hexdigest()
    (STUDIO / "src/.staged.json").write_text(json.dumps(
        {"slug": slug, "captionsMd5": digest,
         "stagedAt": datetime.now().isoformat(timespec="seconds")}, indent=2))

    print(f"staged {slug} — {doc['name']} / {par['name']}")
    for f in sorted(pub.iterdir()):
        print(f"   public/{f.name}  {f.stat().st_size//1024} KB")
    return 0


def cmd_render(slug, overlays=False, only=None):
    """Render the posted cuts. `only` in {'kyros','partner'} renders one cut —
    the standing rule is to finish and sign off the Kyros cut before the
    partner one, never both blind in a single pass."""
    p = PROJECTS / slug
    out = p / "out"
    out.mkdir(exist_ok=True)
    kyros = [("Composed", out / f"{slug}-kyros.mp4", [])]
    partner = [("PartnerComposed", out / f"{slug}-partner.mp4", [])]
    if overlays:
        pro = ["--codec=prores", "--prores-profile=4444",
               "--pixel-format=yuva444p10le", "--image-format=png"]
        kyros.append(("TextOverlay", out / f"{slug}-kyros-overlay.mov", pro))
        partner.append(("PartnerTextOverlay", out / f"{slug}-partner-overlay.mov", pro))
    jobs = {"kyros": kyros, "partner": partner}
    picked = [only] if only else ["kyros", "partner"]

    # The studio renders what IT holds, not what this project's work/ holds.
    # For four reels the only guard against that was remembering to run
    # `stage`. Now it is checked: a mismatch stops the render instead of
    # producing a cut of the previous version that looks fine and passes
    # verify.
    receipt = STUDIO / "src/.staged.json"
    live = hashlib.md5((p / "work/captions_data.json").read_bytes()).hexdigest()
    if not receipt.exists():
        print("the studio has no staging receipt — run: reels.py stage " + slug)
        return 1
    staged = json.loads(receipt.read_text())
    if staged["slug"] != slug or staged["captionsMd5"] != live:
        print(f"the studio holds {staged['slug']} "
              f"({staged['captionsMd5'][:8]}), not this build of {slug} "
              f"({live[:8]}).")
        print(f"run: reels.py stage {slug}")
        return 1

    def archive(target):
        """Never overwrite a render — move the previous one into versions/ with
        the next number, so old and new sit side by side to compare."""
        if not target.exists():
            return
        vdir = out / "versions"
        vdir.mkdir(exist_ok=True)
        n = 1 + len(list(vdir.glob(f"{target.stem}-v*{target.suffix}")))
        dest = vdir / f"{target.stem}-v{n}{target.suffix}"
        shutil.move(str(target), str(dest))
        print(f"   kept previous as versions/{dest.name}")

    for cut in picked:
        for comp, target, extra in jobs[cut]:
            archive(target)
            print(f"rendering {comp} -> {target.name}")
            sh(["npx", "remotion", "render", comp, str(target), "--log=error"] + extra,
               cwd=STUDIO)
            target.with_suffix(".render.json").write_text(json.dumps(
                {"slug": slug, "cut": cut, "composition": comp,
                 "captionsMd5": live,
                 "renderedAt": datetime.now().isoformat(timespec="seconds")},
                indent=2))
    if only:
        print(f"\ndone. Post {out}/{slug}-{only}.mp4")
    else:
        print(f"\ndone. Post {out/f'{slug}-kyros.mp4'} and {out/f'{slug}-partner.mp4'}")
    return 0


def cmd_check(_=None):
    """The rule suite. Every test is a reel that had to be thrown away or a bug
    that shipped and was caught later — docs/TEST-CASES.md names which. Runs in
    about a second and needs no render, so there is no reason not to run it
    before staging."""
    return sh([sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q"],
              cwd=ROOT).returncode


def cmd_verify(slug):
    rc = sh([sys.executable, str(ROOT / "scripts/verify_render.py"),
             str(PROJECTS / slug / "out")]).returncode
    p = PROJECTS / slug
    cd = p / "work/captions_data.json"
    data = json.loads(cd.read_text()) if cd.exists() else {}
    if not data.get("visuals"):
        return rc
    import visuals as visuals_engine
    print("\n=== supporting visuals ===")
    problems = visuals_engine.verify_assets(p, data)
    for cut in ("kyros", "partner"):
        found, saved = visuals_engine.verify_render(p, slug, data, cut)
        problems += [f"{cut}: {x}" for x in found]
        for s in saved:
            print(f"   preview frame: {s.relative_to(p)}")
    for x in problems:
        print(f"   PROBLEM {x}")
    if not problems:
        print(f"   {len(data['visuals']['items'])} visual(s): files present, decodable, "
              f"long enough, with metadata; each one is visibly in the render")
    print("\n" + visuals_engine.summary_text(p))
    print("\nLook at the preview frames — semantic quality (hands, faces, does it")
    print("show what she said) is checked by a person, not by this.")
    if visuals_engine.photoreal(json.loads((p / "brief.json").read_text())):
        print("\nPOSTING: this reel contains realistic AI-generated imagery. Tick the")
        print("platform's AI label at upload — YouTube 'Altered or synthetic content',")
        print("Instagram 'AI info'.")
    return 1 if (rc or problems) else 0


def cmd_visuals(slug, args):
    """The supporting-visuals plan, approval and generation. Generation goes
    through the video toolkit on Modal and never blocks the reel: a visual
    that fails is left out and the build ships footage for that beat."""
    import visuals as visuals_engine
    p = PROJECTS / slug

    def ids(flag):
        val = args[args.index(flag) + 1] if args.index(flag) + 1 < len(args) else "all"
        return "all" if val == "all" else [x.strip() for x in val.split(",") if x.strip()]

    if "--approve" in args:
        visuals_engine.approve(p, ids("--approve"))
    if "--reject" in args:
        visuals_engine.reject(p, ids("--reject"))
    if "--generate" in args:
        only = ids("--only") if "--only" in args else None
        visuals_engine.generate(p, only=None if only == "all" else only,
                                retry="--retry" in args)
        print()
        print(visuals_engine.summary_text(p))
        return 0
    if "--preview" in args:
        out = visuals_engine.preview_sheet(p)
        print(out or "nothing generated yet")
        return 0
    print(visuals_engine.plan_text(p))
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    cmd, slug = sys.argv[1], sys.argv[2]
    fns = {"new": cmd_new, "prep": cmd_prep, "build": cmd_build,
           "stage": cmd_stage, "verify": cmd_verify, "library": cmd_library,
           "check": cmd_check}
    if cmd == "render":
        only = next((a for a in sys.argv[3:] if a in ("kyros", "partner")), None)
        return cmd_render(slug, "--overlays" in sys.argv, only)
    if cmd == "visuals":
        return cmd_visuals(slug, sys.argv[3:])
    if cmd not in fns:
        print(__doc__); return 2
    return fns[cmd](slug) or 0


if __name__ == "__main__":
    raise SystemExit(main())
