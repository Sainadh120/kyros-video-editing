import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadLead } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadKey } from "@remotion/google-fonts/Anton";
import { loadFont as loadUi } from "@remotion/google-fonts/DMSans";
// The other four researched lead/payload pairings (scripts/typography.py).
// Importing a module costs nothing — @remotion/google-fonts only fetches a
// face over the network when its `loadFont()` is actually CALLED. So all
// eight are imported unconditionally here, but only the pair a clip's own
// captions_data.json asks for is ever invoked (see ALT_LEAD/ALT_KEY below) —
// a clip that never asks for them costs nothing extra.
import { loadFont as loadFraunces } from "@remotion/google-fonts/Fraunces";
import { loadFont as loadBarlowCondensed } from "@remotion/google-fonts/BarlowCondensed";
import { loadFont as loadCormorantGaramond } from "@remotion/google-fonts/CormorantGaramond";
import { loadFont as loadOswald } from "@remotion/google-fonts/Oswald";
import { loadFont as loadNewsreader } from "@remotion/google-fonts/Newsreader";
import { loadFont as loadSairaCondensed } from "@remotion/google-fonts/SairaCondensed";
import { loadFont as loadInstrumentSerif } from "@remotion/google-fonts/InstrumentSerif";
import { loadFont as loadAntonio } from "@remotion/google-fonts/Antonio";
import captions from "./captions_data.json";
import { KYROS_STING_SVG } from "./kyrosSting";

/**
 * Reference-led register: type sits transparently ON the footage.
 *
 * Two render modes, driven by props:
 *   showVideo=false, transparent=true  -> TextOverlay, alpha, for compositing
 *   showVideo=true,  transparent=false -> Composed preview
 *
 * Colour is measured, not chosen. The wall behind the text samples #E9C39F,
 * so type there is dark (espresso 9.8:1 / forest 7.4:1 / rust 4.0:1). The
 * question and close cards lay a scrim and invert to cream-on-dark.
 *
 * Everything positional lives in layout.* in captions_data.json, and the
 * phrasing lives in ANSWER_CHUNKS in scripts/build_captions.py.
 */

// The original two calls, byte-for-byte unchanged, so the default pairing
// (theme.type.lead/key.fontFamily absent or "PlayfairDisplay"/"Anton" — true
// of all four shipped clips) resolves through EXACTLY this code path, with
// no new branch evaluated for it.
const lead = loadLead("italic", { weights: ["500", "600"], subsets: ["latin"] });
const leadUpright = loadLead("normal", { weights: ["500"], subsets: ["latin"] });
const key = loadKey("normal", { weights: ["400"], subsets: ["latin"] });
const ui = loadUi("normal", { weights: ["400", "500", "600"], subsets: ["latin"] });

const LEAD_FAMILY_DEFAULT = lead.fontFamily;
const LEAD_UPRIGHT = leadUpright.fontFamily;
const KEY_FAMILY_DEFAULT = key.fontFamily;
const UI_FAMILY = ui.fontFamily;

// A researched pairing beyond the default (scripts/typography.py:PAIRINGS).
// Keyed by the exact string build_captions.py writes to
// theme.type.lead.fontFamily / theme.type.key.fontFamily.
//
// Each generated google-fonts module types `style`/`weights` as a literal
// union specific to that face (e.g. Anton only ever accepts "400"), so a
// single shared call signature across five unrelated modules has to be
// loosened to `any` here — the real validation that every weight used below
// actually exists for that face happened against the installed package's
// own font-info tables (see scripts/typography.py's module docstring), not
// against this type.
type FontLoader = (style: any, options: any) => { fontFamily: string };

const ALT_LEAD: Record<string, FontLoader> = {
  Fraunces: loadFraunces,
  CormorantGaramond: loadCormorantGaramond,
  Newsreader: loadNewsreader,
  InstrumentSerif: loadInstrumentSerif,
};
const ALT_KEY: Record<string, FontLoader> = {
  BarlowCondensed: loadBarlowCondensed,
  Oswald: loadOswald,
  SairaCondensed: loadSairaCondensed,
  Antonio: loadAntonio,
};

const rawTheme = (captions as any).theme.type as {
  lead: Record<string, unknown>; key: Record<string, unknown>;
};
const leadFamilyWanted = (rawTheme.lead.fontFamily as string) ?? "PlayfairDisplay";
const leadStyleWanted = (rawTheme.lead.style as "italic" | "normal") ?? "italic";
const leadWeightWanted = String(rawTheme.lead.weight ?? 500);
const keyFamilyWanted = (rawTheme.key.fontFamily as string) ?? "Anton";
const keyWeightWanted = String(rawTheme.key.weight ?? 400);

// Only calls an alternate loader (network fetch) when the pairing actually
// differs from the default — the branch that keeps the four shipped clips
// from paying for, or touching, any of the new font modules.
const LEAD_FAMILY =
  leadFamilyWanted === "PlayfairDisplay" || !ALT_LEAD[leadFamilyWanted]
    ? LEAD_FAMILY_DEFAULT
    : ALT_LEAD[leadFamilyWanted](leadStyleWanted, {
        weights: [leadWeightWanted], subsets: ["latin"],
      }).fontFamily;
const KEY_FAMILY =
  keyFamilyWanted === "Anton" || !ALT_KEY[keyFamilyWanted]
    ? KEY_FAMILY_DEFAULT
    : ALT_KEY[keyFamilyWanted]("normal", {
        weights: [keyWeightWanted], subsets: ["latin"],
      }).fontFamily;
const LEAD_STYLE: "italic" | "normal" = leadStyleWanted;

/* ------------------------------------------------------------------ types */

export type BrandId = "kyros" | "partner";

type Brand = {
  label: string;
  logo: { enabled: boolean };
  outro: {
    kind: "clip" | "logo-card";
    src: string;
    enterFrame: number;
    durationInFrames: number;
    background?: string;
    logoWidth?: number;
  };
  durationInFrames: number;
};

type Tone = "key" | "keyAlt";
type Word = { index: number; text: string; startFrame: number; activeToFrame: number };
type QuestionRow = {
  style: "lead" | "key";
  words: number[];
  text: string;
  lines?: string[];
  size?: number;
  appearFrame: number;
  // Per-row fill, so the question card can pick out its own hero word rather
  // than setting every row in one colour. Falls back to the onDark palette.
  color?: string;
};
type Zone = "top" | "bottom";
type Chunk = {
  id: string;
  zone: Zone;
  leadWords: number[];
  leadText: string;
  leadSize: number;
  leadColor?: string;
  leadDark?: boolean;
  keyWords: number[];
  keyLines: string[];
  keySize: number;
  keyColor?: string;
  keyDark?: boolean;
  tone: Tone;
  fromFrame: number;
  toFrame: number;
  keyFromFrame: number;
  // Which reveal style the payload uses (scripts/motion.py:REVEAL_STYLES).
  // Absent on every shipped chunk today, which resolves to "legacyMaskWipe"
  // — the original, unmodified reveal — so existing clips render unchanged.
  reveal?: string;
  // Position in a spoken list, when the beat is a rung of one. Null on beats
  // that stand alone — the ladder rule then renders nothing.
  listIndex?: number | null;
  listTotal?: number | null;
};

const data = captions as unknown as {
  meta: { videoSrc: string; audioSrc: string; videoFrames: number };
  theme: {
    palette: {
      scene: { wall: string; wallShadow: string };
      onLight: Record<"lead" | "key" | "keyAlt" | "muted", string>;
      onDark: Record<"scrim" | "lead" | "key" | "keyAlt" | "muted", string>;
      // Dark type for low captions sitting straight on the footage (no scrim),
      // chosen to read against the subject's colour — e.g. a parrot-green
      // saree. Optional; falls back to onLight when absent.
      bottomText?: Record<"lead" | "key" | "keyAlt", string>;
    };
    type: {
      lead: Record<string, number | string | boolean>;
      key: Record<string, number | string>;
      ui: Record<string, number | string>;
      // Outline carried by every caption. Widths are a fraction of the type
      // size. Absent, or with a null colour, means no stroke.
      stroke?: {
        color: string | null; keyEm: number; leadEm: number; shadow: string;
      };
    };
    motion: {
      soft: { mass: number; damping: number; stiffness: number };
      punch: { mass: number; damping: number; stiffness: number };
      wordFrames: number; chunkInFrames: number; chunkOutFrames: number;
      wipeFrames: number; scrimFrames: number; closeFrames: number;
    };
  };
  layout: {
    topZone: { top: number; height: number; paddingX: number };
    bottomZone: { top: number; height: number; paddingX: number };
    captionScrim: {
      enabled: boolean; color: string; opacity: number; top: number;
      // Fade distance at the panel's top edge, in px. Small = a clean cut.
      feather?: number;
    };
    logo: { width: number; right: number; y: number; stingSeconds: number; opacity: number; loop?: boolean };
    doctorPlate: {
      src: string; fileWidth: number; fileHeight: number;
      pillX: number; pillY: number; pillWidth: number; pillHeight: number;
      targetPillWidth: number; left: number; top: number; holdFrames: number;
    };
    video: { renderWidth: number; renderHeight: number; offsetY: number };
    outro: { src: string; crossfadeFrames: number };
  };
  compliance: { doctor: { name: string; title: string } };
  fixtures: {
    plateFromFrame: number; logoFromFrame: number;
    // Windows where a burned-in graphic fills the top of the frame; the mark
    // steps aside rather than landing on top of it.
    logoHideWindows?: [number, number][];
  };
  brands: Record<BrandId, Brand>;
  phases: unknown[];
  words: { question: Word[]; answer: Word[] };
  // Blank-top filler: stretch the footage so her head fills the bare wall
  // wherever no burned-in graphic covers the top band. Absent = no zoom.
  zoom?: { windows: [number, number][]; scale: number; easeFrames: number };
};

const P = data.theme.palette;
const TL = data.theme.type.lead as Record<string, number>;
const TK = data.theme.type.key as Record<string, number>;
const TU = data.theme.type.ui as Record<string, number>;
const STROKE = data.theme.type.stroke?.color ? data.theme.type.stroke : null;

/** Outline + depth shadow for a caption glyph, at a given type size. */
const outline = (size: number, em: number): React.CSSProperties =>
  STROKE
    ? {
        WebkitTextStrokeWidth: `${size * em}px`,
        WebkitTextStrokeColor: STROKE.color as string,
        // Without this the stroke is painted centred on the glyph edge and
        // eats into the letterform; `stroke fill` puts the fill back on top.
        paintOrder: "stroke fill",
        textShadow: STROKE.shadow,
      }
    : {};
const M = data.theme.motion;
const L = data.layout;

const questionPhase = data.phases[0] as {
  scrimOpacity: number;
  card?: {
    bg: string; opacity: number; lead: string; key: string;
    texture?: string; dark: boolean;
  }; exitFrame: number; exitDurationInFrames: number;
  rows: QuestionRow[];
};
const answerPhase = data.phases[1] as { fromFrame: number; chunks: Chunk[] };
const FIX = data.fixtures;
export const BRANDS = data.brands;
const QW = data.words.question;
const AW = data.words.answer;

/* ------------------------------------------------- supporting visuals */
/*
 * Pictures and number/list graphics that show what the doctor is saying.
 * Every file here was generated and checked before build; this component
 * only plays finished files from public/ai and never generates anything.
 * `visuals` is absent from every clip built without brief.visuals, and then
 * each component below returns null — the composition is unchanged.
 */

type Rect = [number, number, number, number];
type GraphicSpec = {
  type: "counter" | "frequency" | "ring" | "checklist";
  value?: number; from?: number; prefix?: string; suffix?: string;
  label?: string; unit?: string; count?: number | number[];
  items?: string[]; itemFrames?: number[];
  listStyle?: "ticks" | "numbered" | "bars" | "pills";
  ground: string; groundOpacity: number; ink: string; accent: string; text: string;
  texture?: string | null;
};
type VisualItem = {
  id: string;
  kind: "image" | "video" | "graphic";
  treatment: "doctorBubble" | "inset" | "cutaway" | "hookBackdrop" | "listBuild";
  fromFrame: number; toFrame: number; fadeFrames: number;
  src?: string; rect?: Rect;
  kenBurns?: { from: number; to: number; x0: number; x1: number };
  bubble?: {
    shape: "circle" | "roundedSquare"; rect: Rect;
    face: { cx: number; cy: number; r: number };
    ring: string; ringWidth: number; radius: number; shrinkFrames: number;
  };
  captionWashes?: {
    color: string; opacity: number; fromFrame: number; toFrame: number; rect: Rect;
  }[];
  graphic?: GraphicSpec;
  cardOpacity?: number;
  glow?: { color: string; opacity: number; rect: Rect };
  // listBuild: one item of a spoken list
  group?: string; label?: string; showLabels?: boolean; listLayout?: "grid" | "cuts"; stage?: number[];
  tile?: Rect; index?: number; count?: number;
  settleFrame?: number; tileFrames?: number;
  ground?: string; labelColor?: string; accent?: string; texture?: string | null;
};

const VIS = (captions as any).visuals as { items: VisualItem[] } | undefined;
const VITEMS: VisualItem[] = VIS ? VIS.items : [];
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const EASE_IN_OUT = Easing.inOut(Easing.cubic);
const EASE_OUT = Easing.out(Easing.cubic);

const activeAt = (frame: number, pred: (i: VisualItem) => boolean) =>
  VITEMS.find((i) => pred(i) && frame >= i.fromFrame && frame < i.toFrame);

/** Fade in, hold, fade out — no bounce, no velocity. */
const visualOpacity = (it: VisualItem, frame: number) =>
  interpolate(
    frame,
    [it.fromFrame, it.fromFrame + it.fadeFrames, it.toFrame - it.fadeFrames, it.toFrame],
    [0, 1, 1, 0],
    { ...CLAMP, easing: EASE_IN_OUT },
  );

const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

/**
 * A still or a clip, filling w x h. Stills drift with a slow camera move so a
 * photograph never sits dead; clips play from their own first frame, which is
 * why callers wrap this in a <Sequence> (see the Outro gotcha below).
 */
const Picture: React.FC<{ it: VisualItem; w: number; h: number }> = ({ it, w, h }) => {
  const frame = useCurrentFrame();
  const base: React.CSSProperties = { width: w, height: h, objectFit: "cover", display: "block" };
  if (it.kind === "video") {
    return <OffthreadVideo src={staticFile(it.src as string)} muted style={base} />;
  }
  const kb = it.kenBurns ?? { from: 1, to: 1, x0: 0, x1: 0 };
  const p = interpolate(frame, [0, Math.max(1, it.toFrame - it.fromFrame)], [0, 1], CLAMP);
  const s = kb.from + (kb.to - kb.from) * p;
  const x = (kb.x0 + (kb.x1 - kb.x0) * p) * w;
  return (
    <Img
      src={staticFile(it.src as string)}
      style={{ ...base, transform: `translateX(${x}px) scale(${s})` }}
    />
  );
};

const fmtNum = (n: number) => Math.round(n).toLocaleString("en-IN");

const numeralStyle = (size: number, color: string): React.CSSProperties => ({
  fontFamily: KEY_FAMILY, fontWeight: TK.weight, fontSize: size, lineHeight: 0.95,
  letterSpacing: TK.letterSpacing, color, whiteSpace: "nowrap",
});

const labelStyle = (size: number, color: string): React.CSSProperties => ({
  fontFamily: UI_FAMILY, fontWeight: 600, fontSize: size, letterSpacing: size * 0.14,
  textTransform: "uppercase", color, textAlign: "center", lineHeight: 1.15,
});

/** Largest numeral size that fits `text` across w, capped. */
const fitSize = (text: string, w: number, cap: number) =>
  Math.min(cap, (w * 0.86) / (Math.max(1, text.length) * (TK.advanceEm || 0.47)));

/** Her number, her frequency, her list — drawn exactly, never generated. */
const GraphicBody: React.FC<{
  g: GraphicSpec; w: number; h: number; local: number; from: number; full: boolean;
}> = ({ g, w, h, local, from, full }) => {
  if (g.type === "counter") {
    const t = interpolate(local, [6, 30], [0, 1], { ...CLAMP, easing: EASE_OUT });
    const start = g.from ?? 0;
    const cur = start + ((g.value ?? 0) - start) * t;
    const pre = g.prefix ?? "";
    const suf = g.suffix ?? "";
    const final = g.from !== undefined
      ? `${fmtNum(g.from)}–${fmtNum(g.value ?? 0)}` : `${pre}${fmtNum(g.value ?? 0)}${suf}`;
    const shown = g.from !== undefined
      ? `${fmtNum(g.from)}–${fmtNum(cur)}` : `${pre}${fmtNum(cur)}${suf}`;
    const size = fitSize(final, w, h * 0.5);
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: size * 0.14 }}>
        <div style={numeralStyle(size, g.ink)}>{shown}</div>
        {g.label ? <div style={labelStyle(Math.max(24, size * 0.2), g.text)}>{g.label}</div> : null}
        <div style={{ width: size * 1.5 * t, height: 6, borderRadius: 3, background: g.accent }} />
      </div>
    );
  }
  if (g.type === "frequency") {
    const c = Array.isArray(g.count) ? g.count : [g.count ?? 0, g.count ?? 0];
    const lo = Math.min(...c);
    const hi = Math.max(...c);
    const head = lo === hi ? `${lo}×` : `${lo}–${hi}×`;
    const dot = Math.min(w / 11, h / 5.2);
    const days = ["M", "T", "W", "T", "F", "S", "S"];
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: dot * 0.42 }}>
        <div style={numeralStyle(fitSize(head, w * 0.6, h * 0.34), g.ink)}>{head}</div>
        <div style={{ display: "flex", gap: dot * 0.42 }}>
          {days.map((d, i) => {
            const on = interpolate(local, [8 + i * 3, 15 + i * 3], [0, 1], { ...CLAMP, easing: EASE_OUT });
            const solid = i < lo;
            const maybe = i >= lo && i < hi;
            return (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: dot * 0.16 }}>
                <div
                  style={{
                    width: dot, height: dot, borderRadius: "50%", boxSizing: "border-box",
                    background: solid ? g.accent : "transparent",
                    border: `${Math.max(3, dot * 0.1)}px solid ${solid || maybe ? g.accent : rgba(g.text, 0.25)}`,
                    opacity: 0.25 + 0.75 * on, transform: `scale(${0.82 + 0.18 * on})`,
                  }}
                />
                <div style={labelStyle(Math.max(18, dot * 0.32), rgba(g.text, 0.7))}>{d}</div>
              </div>
            );
          })}
        </div>
        {g.label ? <div style={labelStyle(Math.max(22, dot * 0.4), g.text)}>{g.label}</div> : null}
      </div>
    );
  }
  if (g.type === "ring") {
    const t = interpolate(local, [6, 33], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
    const D = Math.min(h * 0.86, w * (full ? 0.62 : 0.46));
    const sw = D * 0.1;
    const R = (D - sw) / 2;
    const C = 2 * Math.PI * R;
    const ring = (
      <div style={{ position: "relative", width: D, height: D, flex: "none" }}>
        <svg width={D} height={D} style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}>
          <circle cx={D / 2} cy={D / 2} r={R} fill="none" stroke={rgba(g.text, 0.16)} strokeWidth={sw} />
          <circle cx={D / 2} cy={D / 2} r={R} fill="none" stroke={g.accent} strokeWidth={sw}
            strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - t)} />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column",
                      alignItems: "center", justifyContent: "center" }}>
          <div style={numeralStyle(D * 0.34, g.ink)}>{fmtNum((g.value ?? 0) * t)}</div>
          {g.unit ? <div style={labelStyle(Math.max(20, D * 0.09), g.text)}>{g.unit}</div> : null}
        </div>
      </div>
    );
    const label = g.label ? (
      <div style={{ ...labelStyle(Math.max(24, D * 0.1), g.text), maxWidth: full ? w * 0.8 : w - D - 90,
                    textAlign: full ? "center" : "left" }}>{g.label}</div>
    ) : null;
    return (
      <div style={{ display: "flex", flexDirection: full ? "column" : "row", alignItems: "center",
                    gap: D * 0.16 }}>
        {ring}{label}
      </div>
    );
  }
  return <Checklist g={g} w={w} h={h} local={local} from={from} />;
};

/**
 * A spoken list as a motion graphic. Four styles (graphic.listStyle) so the
 * reels don't share one template; all of them share the same grammar: the
 * item arrives on her word with a mask wipe, earlier items step back a
 * little so the eye sits on the one she is saying, and the ornament (ring,
 * numeral, bar, pill) draws itself rather than popping in.
 */
const Checklist: React.FC<{ g: GraphicSpec; w: number; h: number; local: number; from: number }> = ({
  g, w, h, local, from,
}) => {
  const items = g.items ?? [];
  const n = Math.max(1, items.length);
  const style = g.listStyle ?? "ticks";
  const padX = 58;
  const innerW = w - padX * 2;
  const rowH = Math.min((h - 70) / n, 170);
  const ornament = style === "pills" ? 0 : rowH * 0.62;
  const longest = items.reduce((a, b) => (b.length > a.length ? b : a), "");
  const textW = innerW - ornament - (style === "pills" ? 90 : rowH * 0.34);
  const size = Math.min(rowH * (style === "pills" ? 0.46 : 0.56), fitSize(longest, textW, 96));
  const ats = items.map((_, i) => (g.itemFrames?.[i] ?? from + 8 + i * 14) - from);

  return (
    <div style={{ width: innerW, display: "flex", flexDirection: "column",
                  alignItems: style === "pills" ? "center" : "stretch",
                  gap: style === "pills" ? rowH * 0.16 : 0 }}>
      {items.map((txt, i) => {
        const at = ats[i];
        const next = i + 1 < n ? ats[i + 1] : 1e6;   // last item never steps back; interpolate rejects Infinity
        const on = interpolate(local, [at, at + 10], [0, 1], { ...CLAMP, easing: EASE_OUT });
        const wipe = interpolate(local, [at + 2, at + 14], [0, 100], { ...CLAMP, easing: EASE_IN_OUT });
        const draw = interpolate(local, [at, at + 16], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
        const settle = interpolate(local, [next, next + 10], [1, 0.62], { ...CLAMP, easing: EASE_OUT });
        const text = (
          <div style={{ ...numeralStyle(size, g.ink), clipPath: `inset(-10% ${100 - wipe}% -10% 0)`,
                        transform: `translateX(${(1 - on) * 18}px)` }}>{txt}</div>
        );

        if (style === "pills") {
          const pop = interpolate(local, [at, at + 7, at + 13], [0.86, 1.035, 1], { ...CLAMP, easing: EASE_OUT });
          return (
            <div key={i} style={{ opacity: on * settle, transform: `scale(${pop})`,
                                  display: "flex", alignItems: "center", gap: size * 0.42,
                                  padding: `${size * 0.26}px ${size * 0.62}px`, borderRadius: 999,
                                  background: rgba(g.accent, 0.1),
                                  border: `2px solid ${rgba(g.accent, 0.35 + 0.4 * draw)}` }}>
              <div style={{ width: size * 0.3, height: size * 0.3, borderRadius: "50%",
                            background: g.accent, transform: `scale(${draw})` }} />
              {text}
            </div>
          );
        }

        const rule = i < n - 1 ? (
          <div style={{ position: "absolute", left: ornament + rowH * 0.34, right: 0, bottom: 0, height: 1.5,
                        background: rgba(g.ink, 0.16), transformOrigin: "left",
                        transform: `scaleX(${draw})` }} />
        ) : null;

        let mark: React.ReactNode;
        if (style === "numbered") {
          mark = (
            <div style={{ width: ornament, fontFamily: LEAD_FAMILY, fontStyle: LEAD_STYLE,
                          fontSize: ornament * 0.78, lineHeight: 1, color: g.accent,
                          opacity: on, fontVariantNumeric: "lining-nums tabular-nums",
                          transform: `translateY(${(1 - on) * 10}px)` }}>
              {String(i + 1).padStart(2, "0")}
            </div>
          );
        } else if (style === "bars") {
          mark = (
            <div style={{ width: ornament, display: "flex", justifyContent: "center" }}>
              <div style={{ width: 7, height: rowH * 0.58, borderRadius: 4, background: g.accent,
                            transformOrigin: "top", transform: `scaleY(${draw})` }} />
            </div>
          );
        } else {
          const R = 17;
          const C = 2 * Math.PI * R;
          const tick = interpolate(local, [at + 8, at + 18], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
          mark = (
            <svg width={ornament} height={ornament} viewBox="0 0 40 40" style={{ flex: "none" }}>
              <circle cx="20" cy="20" r={R} fill={rgba(g.accent, 0.12 * draw)} stroke={g.accent}
                strokeWidth="2.4" strokeDasharray={C} strokeDashoffset={C * (1 - draw)}
                transform="rotate(-90 20 20)" />
              <path d="M13 20.5 L18.2 25.6 L27.5 15" fill="none" stroke={g.accent} strokeWidth="3.4"
                strokeLinecap="round" strokeLinejoin="round" pathLength={1}
                strokeDasharray={1} strokeDashoffset={1 - tick} />
            </svg>
          );
        }

        const active = style === "bars"
          ? interpolate(local, [at, at + 8], [0, 1], CLAMP) * interpolate(local, [next, next + 10], [1, 0], CLAMP)
          : 0;
        return (
          <div key={i} style={{ position: "relative", height: rowH, display: "flex", alignItems: "center",
                                gap: rowH * 0.34, opacity: Math.max(on, 0.0001) * settle,
                                borderRadius: 18, background: rgba(g.accent, 0.07 * active),
                                paddingLeft: style === "bars" ? 0 : 0 }}>
            {mark}
            {text}
            {rule}
          </div>
        );
      })}
    </div>
  );
};

const GRAIN = "repeating-linear-gradient(37deg, rgba(0,0,0,0.028) 0px, rgba(0,0,0,0.028) 1px, rgba(0,0,0,0) 1px, rgba(0,0,0,0) 3px)";
const VIGNETTE = "radial-gradient(120% 85% at 50% 42%, rgba(255,255,255,0.055) 0%, rgba(255,255,255,0) 55%, rgba(0,0,0,0.42) 100%)";

const GraphicCard: React.FC<{ it: VisualItem; opacity: number }> = ({ it, opacity }) => {
  const frame = useCurrentFrame();
  const g = it.graphic as GraphicSpec;
  const full = it.treatment !== "inset";
  const [x0, y0, x1, y1] = it.rect ?? [90, 560, 990, 1180];
  const lift = interpolate(frame, [it.fromFrame, it.fromFrame + it.fadeFrames], [18, 0],
    { ...CLAMP, easing: EASE_OUT });
  return (
    <AbsoluteFill style={{ opacity }}>
      {full ? <AbsoluteFill style={{ backgroundColor: g.ground }} /> : null}
      {full && g.texture ? (
        <AbsoluteFill style={{ background: g.texture === "vignette" ? VIGNETTE : GRAIN }} />
      ) : null}
      <div
        style={{
          position: "absolute", left: x0, top: y0, width: x1 - x0, height: y1 - y0,
          transform: `translateY(${lift}px)`, borderRadius: full ? 0 : 34,
          background: full ? undefined
            : `linear-gradient(160deg, ${rgba(g.ground, Math.min(1, g.groundOpacity))} 0%, ${rgba(g.ground, g.groundOpacity * 0.84)} 100%)`,
          backdropFilter: full ? undefined : "blur(18px) saturate(1.15)",
          border: full ? undefined : "1.5px solid rgba(255,255,255,0.55)",
          boxShadow: full ? undefined
            : "0 30px 70px rgba(30,18,8,0.22), 0 4px 14px rgba(30,18,8,0.10), inset 0 1px 0 rgba(255,255,255,0.7)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        {!full ? <div style={{ position: "absolute", inset: 0, borderRadius: 34, background: GRAIN }} /> : null}
        <div style={{ position: "relative" }}>
          <GraphicBody g={g} w={x1 - x0} h={y1 - y0} local={frame - it.fromFrame}
            from={it.fromFrame} full={full} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/**
 * A spoken list, built up: each item arrives centre stage on its own word
 * with a slow settle, glides into its tile as the next one arrives, and by
 * the end every item is on screen together, labelled. Her bubble stays on
 * throughout (DoctorBubble).
 */
/**
 * listLayout "cuts": one item at a time. A large sharp square card over a
 * blurred, darkened copy of the same picture filling the frame, the label set
 * big beneath it, and a row of progress dots so the viewer feels the list
 * building. The next item cross-fades in on its own word. Square tiles are
 * never stretched to 9:16 — the blur carries the full frame, the card stays
 * crisp.
 */
const ListCuts: React.FC<{ lead: VisualItem; mem: VisualItem[]; opacity: number }> = ({
  lead, mem, opacity,
}) => {
  const frame = useCurrentFrame();
  const [sx0, sy0, sx1, sy1] = (lead.stage ?? [48, 300, 1032, 1180]) as Rect;
  const labelH = 150;
  const card = Math.min(sx1 - sx0 - 40, sy1 - sy0 - labelH - 30, 900);
  const cx = (sx0 + sx1) / 2;
  const cardTop = sy0 + (sy1 - sy0 - card - labelH) / 2;
  const XF = 7;
  const shown = mem.filter((m, i) => {
    const next = mem[i + 1];
    return frame >= m.fromFrame && (!next || frame < next.fromFrame + XF);
  });
  const current = mem.filter((m) => frame >= m.fromFrame).length - 1;
  return (
    <AbsoluteFill style={{ opacity, backgroundColor: lead.ground }}>
      {shown.map((m) => {
        const i = mem.indexOf(m);
        const next = mem[i + 1];
        const inT = interpolate(frame, [m.fromFrame, m.fromFrame + XF], [0, 1], { ...CLAMP, easing: EASE_OUT });
        const outT = next ? interpolate(frame, [next.fromFrame, next.fromFrame + XF], [1, 0], CLAMP) : 1;
        const o = inT * outT;
        const pop = interpolate(frame, [m.fromFrame, m.fromFrame + 12], [0.94, 1], { ...CLAMP, easing: EASE_OUT });
        const drift = interpolate(frame, [m.fromFrame, m.fromFrame + 60], [1.0, 1.04], CLAMP);
        const labelIn = interpolate(frame, [m.fromFrame + 3, m.fromFrame + 12], [0, 1], { ...CLAMP, easing: EASE_OUT });
        return (
          <AbsoluteFill key={m.id} style={{ opacity: o }}>
            <Sequence from={m.fromFrame} durationInFrames={Math.max(1, m.toFrame - m.fromFrame)} layout="none">
              <AbsoluteFill style={{ overflow: "hidden" }}>
                <div style={{ width: 1080, height: 1920, transform: "scale(1.18)",
                              filter: "blur(38px) brightness(0.5) saturate(1.1)" }}>
                  <Picture it={{ ...m, kenBurns: undefined }} w={1080} h={1920} />
                </div>
              </AbsoluteFill>
              <AbsoluteFill style={{ background: "radial-gradient(90% 60% at 50% 40%, rgba(0,0,0,0) 0%, rgba(0,0,0,0.35) 100%)" }} />
              <div style={{ position: "absolute", left: cx - card / 2, top: cardTop, width: card, height: card,
                            borderRadius: 36, overflow: "hidden", transform: `scale(${pop})`,
                            boxShadow: "0 40px 90px rgba(0,0,0,0.45), 0 0 0 2px rgba(255,255,255,0.18)" }}>
                <div style={{ width: card, height: card, transform: `scale(${drift})` }}>
                  <Picture it={{ ...m, kenBurns: undefined }} w={card} h={card} />
                </div>
              </div>
            </Sequence>
            {m.label ? (
              <div style={{ position: "absolute", left: sx0, width: sx1 - sx0, top: cardTop + card + 34,
                            display: "flex", justifyContent: "center", opacity: labelIn,
                            transform: `translateY(${(1 - labelIn) * 16}px)` }}>
                <div style={{ ...numeralStyle(Math.min(96, fitSize(m.label, sx1 - sx0, 96)), "#FFF6E8"),
                              textShadow: "0 4px 24px rgba(0,0,0,0.45)" }}>{m.label}</div>
              </div>
            ) : null}
          </AbsoluteFill>
        );
      })}
      <div style={{ position: "absolute", left: sx0, width: sx1 - sx0, top: cardTop - 46,
                    display: "flex", justifyContent: "center", gap: 14 }}>
        {mem.map((m, i) => (
          <div key={m.id} style={{ height: 8, borderRadius: 4,
                                   width: i === current ? 44 : 8,
                                   background: i <= current ? (lead.accent ?? "#FFB01F") : "rgba(255,255,255,0.35)" }} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

const ListBuild: React.FC<{ lead: VisualItem; opacity: number }> = ({ lead, opacity }) => {
  const frame = useCurrentFrame();
  const mem = VITEMS.filter((i) => i.group === lead.group)
    .sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  if (lead.listLayout === "cuts") {
    return <ListCuts lead={lead} mem={mem} opacity={opacity} />;
  }
  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill style={{ backgroundColor: lead.ground }} />
      {lead.texture ? (
        <AbsoluteFill style={{ background: lead.texture === "vignette" ? VIGNETTE : GRAIN }} />
      ) : null}
      {mem.map((m) => {
        if (frame < m.fromFrame) {
          return null;
        }
        const tf = m.tileFrames ?? 10;
        const s = m.settleFrame ?? m.fromFrame + 20;
        const p = interpolate(frame, [s, s + tf], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
        const arrive = interpolate(frame, [m.fromFrame, m.fromFrame + 8], [0, 1],
          { ...CLAMP, easing: EASE_OUT });
        // Each item pops out over its own tile (its `rect`), then settles in.
        const [rx0, ry0, rx1, ry1] = m.rect as Rect;
        const [tx0, ty0, tx1, ty1] = m.tile as Rect;
        const x = rx0 + (tx0 - rx0) * p;
        const y = ry0 + (ty0 - ry0) * p;
        const w = rx1 - rx0 + (tx1 - tx0 - (rx1 - rx0)) * p;
        const h = ry1 - ry0 + (ty1 - ty0 - (ry1 - ry0)) * p;
        const settle = interpolate(frame, [m.fromFrame, s], [1.1, 1.0],
          { ...CLAMP, easing: EASE_OUT });
        const labelOn = interpolate(frame, [s + tf - 2, s + tf + 6], [0, 1], CLAMP);
        return (
          <div
            key={m.id}
            style={{
              position: "absolute", left: x, top: y, width: w, height: h,
              borderRadius: 26, overflow: "hidden", opacity: arrive, zIndex: p < 1 ? 2 : 1,
              boxShadow: "0 0 0 4px rgba(250,241,228,0.9), 0 18px 44px rgba(0,0,0,0.35)",
            }}
          >
            <Sequence from={m.fromFrame} durationInFrames={Math.max(1, m.toFrame - m.fromFrame)}
              layout="none">
              <div style={{ width: w, height: h, transform: `scale(${settle})` }}>
                <Picture it={{ ...m, kenBurns: undefined }} w={w} h={h} />
              </div>
            </Sequence>
            {m.label && m.showLabels ? (
              <div
                style={{
                  position: "absolute", left: 0, right: 0, bottom: 0,
                  padding: "40px 16px 16px", opacity: labelOn,
                  background: "linear-gradient(to top, rgba(0,0,0,0.66), rgba(0,0,0,0))",
                }}
              >
                <div style={labelStyle(Math.max(22, Math.min(40, w * 0.07)), "#FFF6E8")}>
                  {m.label}
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/** Full-frame pictures, wall cards and graphics, under every caption. */
const SupportingVisuals: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <>
      {VITEMS.filter((it) => it.treatment !== "hookBackdrop").map((it) => {
        if (frame < it.fromFrame || frame >= it.toFrame) {
          return null;
        }
        const o = visualOpacity(it, frame);
        if (it.treatment === "listBuild") {
          // The first item's window is the whole list's; it draws the group.
          return it.index === 0 ? <ListBuild key={it.id} lead={it} opacity={o} /> : null;
        }
        if (it.kind === "graphic") {
          return <GraphicCard key={it.id} it={it} opacity={o} />;
        }
        const dur = it.toFrame - it.fromFrame;
        if (it.treatment === "inset" && it.rect) {
          const [x0, y0, x1, y1] = it.rect;
          const lift = interpolate(frame, [it.fromFrame, it.fromFrame + it.fadeFrames], [18, 0],
            { ...CLAMP, easing: EASE_OUT });
          return (
            <div
              key={it.id}
              style={{
                position: "absolute", left: x0, top: y0, width: x1 - x0, height: y1 - y0,
                opacity: o, transform: `translateY(${lift}px)`, borderRadius: 34, overflow: "hidden",
                boxShadow: "0 0 0 5px rgba(250,241,228,0.95), 0 22px 54px rgba(30,18,8,0.28)",
              }}
            >
              <Sequence from={it.fromFrame} durationInFrames={dur} layout="none">
                <Picture it={it} w={x1 - x0} h={y1 - y0} />
              </Sequence>
            </div>
          );
        }
        return (
          <AbsoluteFill key={it.id} style={{ opacity: o, overflow: "hidden" }}>
            <AbsoluteFill style={{ transform: `scale(${interpolate(frame, [it.fromFrame, it.fromFrame + it.fadeFrames * 2], [1.06, 1], { ...CLAMP, easing: EASE_OUT })})` }}>
              <Sequence from={it.fromFrame} durationInFrames={dur} layout="none">
                <Picture it={it} w={1080} h={1920} />
              </Sequence>
            </AbsoluteFill>
          </AbsoluteFill>
        );
      })}
    </>
  );
};

/**
 * The doctor, shrunk into a circle or rounded square in the solved corner
 * while a picture fills the frame, then popped back full-frame. Her real
 * footage, never a likeness. Not wrapped in a Sequence on purpose: this is
 * the take itself and must stay on the composition's clock, like Footage.
 */
const DoctorBubble: React.FC = () => {
  const frame = useCurrentFrame();
  const it = activeAt(frame, (i) => !!i.bubble);
  if (!it || !it.bubble) {
    return null;
  }
  const B = it.bubble;
  // She stays full-frame underneath while the picture fades in (Footage keeps
  // drawing), so the only motion is a cross-fade — then her circle pops into
  // the corner once the picture has landed, and leaves before it fades out.
  // The old version morphed a clip-mask from the whole frame down to the
  // corner, which read as sliding arches and ghosted edges.
  const fade = it.fadeFrames ?? 12;
  const pop = 11;
  const pIn = interpolate(frame, [it.fromFrame + Math.round(fade * 0.6), it.fromFrame + Math.round(fade * 0.6) + pop],
    [0, 1], { ...CLAMP, easing: Easing.out(Easing.back(1.4)) });
  const pOut = interpolate(frame, [it.toFrame - fade - pop + 2, it.toFrame - fade + 2], [1, 0],
    { ...CLAMP, easing: Easing.in(Easing.cubic) });
  const p = Math.min(pIn, pOut);
  if (p <= 0) {
    return null;
  }
  const [bx0, by0, bx1, by1] = B.rect;
  const bw = bx1 - bx0;
  const bh = by1 - by0;
  const { cx, cy, r } = B.face;
  const sEnd = bw / 2 / r;
  const tx = bw / 2 - cx * sEnd;
  const ty = bh / 2 - cy * sEnd;
  const radius = B.shape === "circle" ? "50%" : B.radius;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute", left: bx0, top: by0, width: bw, height: bh,
          borderRadius: radius, overflow: "hidden",
          opacity: Math.min(1, p * 1.4), transform: `scale(${0.72 + 0.28 * p})`,
          boxShadow: `0 0 0 ${B.ringWidth}px ${B.ring}, 0 22px 50px rgba(0,0,0,0.38)`,
        }}
      >
        <div
          style={{
            position: "absolute", left: 0, top: 0, width: 1080, height: 1920,
            transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${sEnd})`,
          }}
        >
          <OffthreadVideo
            src={staticFile(data.meta.videoSrc)}
            muted
            style={{
              position: "absolute", top: L.video.offsetY, left: 0,
              width: L.video.renderWidth, height: L.video.renderHeight, objectFit: "cover",
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/**
 * A soft oval glow behind one caption's words, only where the picture under
 * them would out-shout them — measured per caption, so it never spans both
 * zones and never reads as a bar laid across the frame.
 */
const CaptionWash: React.FC = () => {
  const frame = useCurrentFrame();
  const glows: React.ReactNode[] = [];
  VITEMS.forEach((it) => {
    (it.captionWashes ?? []).forEach((w, i) => {
      if (frame < w.fromFrame || frame >= w.toFrame) {
        return;
      }
      const fade = Math.max(1, Math.min(it.fadeFrames, Math.floor((w.toFrame - w.fromFrame - 1) / 2)));
      const own = interpolate(
        frame, [w.fromFrame, w.fromFrame + fade, w.toFrame - fade, w.toFrame], [0, 1, 1, 0],
        { ...CLAMP, easing: EASE_IN_OUT },
      );
      const [x0, y0, x1, y1] = w.rect;
      glows.push(
        <div
          key={`${it.id}-${i}`}
          style={{
            position: "absolute",
            opacity: own * visualOpacity(it, frame) * w.opacity,
            // Wide and heavily feathered so it reads as light falling behind
            // the words, not a blob: full width, fading out top and bottom.
            left: 0, width: 1080, top: y0 - (y1 - y0) * 0.45, height: (y1 - y0) * 1.9,
            background: `linear-gradient(to bottom, ${rgba(w.color, 0)} 0%, ${rgba(w.color, 0.72)} 26%, ${w.color} 42%, ${w.color} 58%, ${rgba(w.color, 0.72)} 74%, ${rgba(w.color, 0)} 100%)`,
          }}
        />,
      );
    });
  });
  return glows.length ? <>{glows}</> : null;
};

/* ------------------------------------------------------------- primitives */

const useSoft = (from: number, dur?: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - from, fps, config: M.soft,
    ...(dur ? { durationInFrames: dur } : {}) });
};

/** Slight overshoot — the payload lands, it doesn't drift in. */
const usePunch = (from: number, dur?: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - from, fps, config: M.punch,
    ...(dur ? { durationInFrames: dur } : {}) });
};

/** Word of the delicate italic lead line, fading in as it is spoken. */
const LeadWord: React.FC<{
  word: Word; color: string; shadow: string; size: number;
}> = ({ word, color, shadow, size }) => {
  const reveal = useSoft(word.startFrame, M.wordFrames);
  return (
    <span
      style={{
        display: "inline-block",
        color,
        opacity: reveal,
        transform: `translateY(${interpolate(reveal, [0, 1], [10, 0])}px)`,
        textShadow: shadow,
        ...outline(size, STROKE ? STROKE.leadEm : 0),
      }}
    >
      {word.text}
    </span>
  );
};

const LeadLine: React.FC<{
  words: Word[]; size: number; color: string; shadow: string;
}> = ({ words, size, color, shadow }) => (
  <div
    style={{
      display: "flex", flexWrap: "wrap", justifyContent: "center",
      columnGap: 16, rowGap: 2,
      fontFamily: LEAD_FAMILY, fontStyle: LEAD_STYLE,
      fontSize: size, fontWeight: TL.weight,
      lineHeight: TL.lineHeight, letterSpacing: TL.letterSpacing,
      textAlign: "center",
    }}
  >
    {words.map((w) => (
      <LeadWord key={w.index} word={w} color={color} shadow={shadow} size={size} />
    ))}
  </div>
);

/**
 * Payload block. Each line rises into place behind a mask and settles with a
 * small punch, staggered so a stacked payload reads top-then-bottom. Where the
 * beat is a rung of a spoken list, a thin rule underneath advances one step per
 * rung, so the viewer can see how far down the list they are.
 */
const KeyLines: React.FC<{
  lines: string[]; size: number; fromFrame: number;
  color: string; shadow: string;
  listIndex?: number | null; listTotal?: number | null;
  reveal?: string;
}> = ({ lines, size, fromFrame, color, shadow, listIndex, listTotal, reveal }) => (
  <div style={{ marginTop: 18 }}>
    {lines.map((text, i) => (
      <KeyLine
        key={i}
        text={text}
        size={size}
        // stagger, so a stacked payload reads top-then-bottom
        fromFrame={fromFrame + i * 5}
        color={color}
        shadow={shadow}
        reveal={reveal}
      />
    ))}
    <LadderRule
      index={listIndex}
      total={listTotal}
      color={color}
      size={size}
      fromFrame={fromFrame + lines.length * 5}
    />
  </div>
);

/**
 * The ladder rule. Five benefits are spoken as a list; this shows which rung
 * the current beat is, as a filled segment against a faint track. It draws in
 * the payload's own colour, which the palette engine has already checked
 * against this zone's background, so it never needs its own contrast decision.
 */
const LadderRule: React.FC<{
  index?: number | null; total?: number | null;
  color: string; size: number; fromFrame: number;
}> = ({ index, total, color, size, fromFrame }) => {
  const grow = useSoft(fromFrame, M.wipeFrames);
  if (!index || !total) {
    return null;
  }
  const width = Math.round(size * 4.4);
  const filled = (index / total) * grow;
  // Track and fill are siblings, not parent and child: nested opacity
  // multiplies, so a fill inside a faded track can never be more solid
  // than the track it sits on.
  return (
    <div
      style={{
        margin: "22px auto 0",
        width,
        height: 5,
        position: "relative",
        opacity: Math.min(1, grow * 2),
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: 3,
          background: color,
          opacity: 0.22,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0, left: 0, bottom: 0,
          width: `${filled * 100}%`,
          borderRadius: 3,
          background: color,
        }}
      />
    </div>
  );
};

/**
 * The base type style shared by every payload reveal, so a new one only has
 * to describe its MOTION, not re-derive the outline/shadow/weight rules.
 */
const keyBaseStyle = (size: number, color: string): React.CSSProperties => ({
  fontFamily: KEY_FAMILY,
  fontSize: size,
  fontWeight: TK.weight,
  lineHeight: TK.lineHeight,
  letterSpacing: TK.letterSpacing,
  color,
  textAlign: "center",
  whiteSpace: "nowrap",
  ...outline(size, STROKE ? STROKE.keyEm : 0),
});

type RevealProps = {
  text: string; size: number; fromFrame: number; color: string; shadow: string;
};

/**
 * The ORIGINAL reveal, unchanged. A vertical mask: the line rises up through
 * an `overflow:hidden` window the height of one text line, so at any
 * mid-transition frame only the TOP portion of every glyph in the line is
 * visible — a horizontal band across the whole line, not a per-letter cut.
 * That is what a still pulled at 10.5s of the shipped pcos-sleep-cycle cut
 * caught: "UNDER CONTROL" mid-rise, reading as a flat grey half-drawn line.
 *
 * The fix (KeyLineMaskWipeFast, below) is NOT applied here. Doing so would
 * change already-rendered frames of the four shipped clips, which the brief
 * for this work requires stay byte-identical. This function is kept as the
 * implicit default — reached only when a chunk carries no `reveal` field,
 * true of every chunk in every shipped captions_data.json — specifically so
 * that guarantee holds. New clips should not opt into it.
 *
 * Measured illegibility window: ~9-13 frames (0.3-0.43s) at `M.wipeFrames`
 * (~13f). See docs/TYPE-AND-MOTION.md.
 */
const KeyLineLegacy: React.FC<RevealProps> = ({ text, size, fromFrame, color, shadow }) => {
  const rise = useSoft(fromFrame, M.wipeFrames);
  const land = usePunch(fromFrame, M.wipeFrames);
  const base = keyBaseStyle(size, color);

  // A spacer holds the payload's space from the moment its chunk opens, so the
  // lead line does not jump when the phrase lands. It is `visibility: hidden`,
  // not a faded ghost: a dim preview of the words sitting on screen before they
  // are spoken reads as a rendering fault, not as design. The solid line RISES
  // into that reserved space behind a mask as the words are spoken, and settles
  // with a small punch.
  //
  // The mask is padded and pulled back by the same 0.16em so descenders and the
  // per-letter shadow are not sheared off at the bottom edge once the line has
  // landed — the old clip-path carried a -0.14em bleed for the same reason.
  return (
    <div style={{ position: "relative" }}>
      <div style={{ ...base, visibility: "hidden" }}>{text}</div>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          overflow: "hidden",
          paddingBottom: "0.16em",
          marginBottom: "-0.16em",
        }}
      >
        <div
          style={{
            ...base,
            textShadow: STROKE ? STROKE.shadow : shadow,
            opacity: rise,
            transform:
              `translateY(${interpolate(rise, [0, 1], [100, 0])}%) ` +
              `scale(${interpolate(land, [0, 1], [0.97, 1])})`,
            transformOrigin: "center bottom",
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};

// How long the wipe edge takes to cross the whole line. Fixed rather than
// scaled to line length: every shipped payload line is 6-19 characters, so a
// 6-frame sweep never lingers inside one glyph's width for more than ~1
// frame (6 frames / 6 chars, the shortest line measured, still resolves in a
// single frame per glyph). A future one- or two-character line would not
// have this guarantee, but the sizing rule's own ceiling means a payload
// that short is set far above the width-fitting size anyway (see
// scripts/typography.py's MEASURED_FIT for the worked numbers), so it is
// visually a poster word landing, not a "read while it wipes" moment.
const WIPE_SWEEP_FRAMES = 6;

/**
 * The successor default. Same idea — the line arrives rather than simply
 * appearing — but the wipe axis is rotated 90 degrees: a `clip-path: inset()`
 * reveals left to right, so at every instant every VISIBLE character is its
 * COMPLETE glyph. Only the character count in view changes, never a
 * fragment of one. That is what removes the failure mode above rather than
 * just shortening it — the shape on screen is legible at every frame, not
 * only for slightly fewer of them.
 *
 * Measured illegibility window: 0 whole-line failures; worst case one glyph
 * is bisected by the wipe edge for a single frame (see WIPE_SWEEP_FRAMES).
 */
const KeyLineMaskWipeFast: React.FC<RevealProps> = ({ text, size, fromFrame, color, shadow }) => {
  const frame = useCurrentFrame();
  const land = usePunch(fromFrame, WIPE_SWEEP_FRAMES + 4);
  const sweep = interpolate(frame, [fromFrame, fromFrame + WIPE_SWEEP_FRAMES], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const base = keyBaseStyle(size, color);
  return (
    <div style={{ position: "relative" }}>
      <div style={{ ...base, visibility: "hidden" }}>{text}</div>
      <div
        style={{
          position: "absolute", top: 0, left: 0, right: 0,
          clipPath: `inset(0 ${((1 - sweep) * 100).toFixed(2)}% 0 0)`,
        }}
      >
        <div
          style={{
            ...base,
            textShadow: STROKE ? STROKE.shadow : shadow,
            transform: `scale(${interpolate(land, [0, 1], [0.985, 1])})`,
            transformOrigin: "center bottom",
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};

/**
 * No mask at all: the payload's units (words, or characters) fade and rise
 * as whole, complete shapes, staggered. A faint word is never a BROKEN one —
 * there is no spatial cut to freeze mid-motion — so this style's
 * illegibility window is 0 by construction, not by tuning. Small
 * displacement (<=10px for words, <=8px for characters) so it never
 * competes with her own movement (README's Rule 2 for this system).
 */
const KeyLineUnitStagger: React.FC<RevealProps & {
  unit: "word" | "char"; staggerFrames: number; durFrames: number; displacementPx: number;
}> = ({ text, size, fromFrame, color, shadow, unit, staggerFrames, durFrames, displacementPx }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const base = keyBaseStyle(size, color);
  if (unit === "char") {
    // Chars wrapped individually let a line break fall mid-word ("TWO TYPE / S"
    // on pcos-belly-fat). Each word is an unbreakable group of chars.
    let k = 0;
    return (
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: size * 0.22 }}>
        {text.split(" ").map((word, wi) => (
          <span key={wi} style={{ display: "inline-flex", whiteSpace: "nowrap" }}>
            {Array.from(word).map((ch) => {
              const i = k++;
              const reveal = spring({ frame: frame - (fromFrame + i * staggerFrames), fps,
                config: M.soft, durationInFrames: durFrames });
              return (
                <span key={i} style={{ ...base, display: "inline-block", whiteSpace: "pre",
                  textShadow: STROKE ? STROKE.shadow : shadow, opacity: reveal,
                  transform: `translateY(${interpolate(reveal, [0, 1], [displacementPx, 0])}px)` }}>
                  {ch}
                </span>
              );
            })}
          </span>
        ))}
      </div>
    );
  }
  const parts = text.split(" ");
  return (
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center",
                  columnGap: size * 0.22 }}>
      {parts.map((p, i) => {
        // spring() is a pure function (not a hook), so calling it per item in
        // a loop of fixed length (the string does not change frame to frame)
        // does not violate the rules of hooks — only useCurrentFrame/
        // useVideoConfig above are hooks, and both are called unconditionally.
        const reveal = spring({ frame: frame - (fromFrame + i * staggerFrames), fps,
          config: M.soft, durationInFrames: durFrames });
        return (
          <span
            key={i}
            style={{
              ...base,
              display: "inline-block",
              whiteSpace: "pre",
              textShadow: STROKE ? STROKE.shadow : shadow,
              opacity: reveal,
              transform: `translateY(${interpolate(reveal, [0, 1], [displacementPx, 0])}px)`,
            }}
          >
            {p}
          </span>
        );
      })}
    </div>
  );
};

/**
 * A fast, slightly overshooting scale+opacity snap on the whole payload
 * line — reserved for a beat whose key phrase carries a top-quartile
 * acoustic emphasis score (scripts/measure_audio.py). No mask, so the
 * illegibility window is 0 for the same reason as the stagger styles: every
 * frame shows a complete, if not-yet-full-size, glyph.
 *
 * Scope note: this snaps the whole LINE, not one word picked out of a
 * longer one — build_captions should route `punchPop` only to beats whose
 * payload line already IS the emphasised word (a single short line), which
 * is how most payloads already resolve by the time they reach this
 * component. Highlighting one word inside a longer surviving line is not
 * implemented.
 */
const KeyLinePunchPop: React.FC<RevealProps> = ({ text, size, fromFrame, color, shadow }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const PUNCH_FRAMES = 8;
  const p = spring({ frame: frame - fromFrame, fps, config: M.punch, durationInFrames: PUNCH_FRAMES });
  const base = keyBaseStyle(size, color);
  return (
    <div
      style={{
        ...base,
        textShadow: STROKE ? STROKE.shadow : shadow,
        opacity: Math.min(1, p * 1.4),
        transform: `scale(${interpolate(p, [0, 1], [0.85, 1])})`,
        transformOrigin: "center",
      }}
    >
      {text}
    </div>
  );
};

// Blur reveal: how much blur at frame 0, and how long the spring takes.
// Slow relative to every other style on purpose — this is the ONE style the
// research calls for something slower and bigger (README-style rule: a hero
// beat on a bare wall can afford it). No displacement at all.
const BLUR_START_PX = 10;
const BLUR_FRAMES = 20;

/**
 * Blur + opacity, no mask, no displacement. A blurred-but-whole word is a
 * different failure mode than a masked one: every frame still shows the
 * complete glyph outline, just softened, which reads as "coming into
 * focus" rather than "a broken render" — the specific complaint the
 * shipped bug produced. Reserved for a genuine hero beat: long duration, a
 * bare wall (no scrim), a take's own top-decile emphasis. See
 * scripts/motion.py:REVEAL_STYLES and docs/TYPE-AND-MOTION.md for why this
 * style is held to a different proof than the mask-based ones instead of
 * the same numeric cap.
 */
const KeyLineBlurIn: React.FC<RevealProps> = ({ text, size, fromFrame, color, shadow }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = spring({ frame: frame - fromFrame, fps, config: M.soft, durationInFrames: BLUR_FRAMES });
  const base = keyBaseStyle(size, color);
  const blurPx = interpolate(reveal, [0, 1], [BLUR_START_PX, 0], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        ...base,
        textShadow: STROKE ? STROKE.shadow : shadow,
        opacity: interpolate(reveal, [0, 1], [0.15, 1], { extrapolateRight: "clamp" }),
        filter: `blur(${blurPx}px)`,
      }}
    >
      {text}
    </div>
  );
};

/**
 * Dispatch by `chunk.reveal` (scripts/motion.py:REVEAL_STYLES). Absent or
 * unrecognised -> the legacy, unmodified reveal, which is what every shipped
 * chunk resolves to today.
 */
const KeyLine: React.FC<RevealProps & { reveal?: string }> = ({ reveal, ...props }) => {
  switch (reveal) {
    case "maskWipeFast":
      return <KeyLineMaskWipeFast {...props} />;
    case "wordStagger":
      return <KeyLineUnitStagger {...props} unit="word" staggerFrames={5} durFrames={14} displacementPx={10} />;
    case "charCascade":
      return <KeyLineUnitStagger {...props} unit="char" staggerFrames={2} durFrames={10} displacementPx={8} />;
    case "punchPop":
      return <KeyLinePunchPop {...props} />;
    case "blurIn":
      return <KeyLineBlurIn {...props} />;
    case "legacyMaskWipe":
    default:
      return <KeyLineLegacy {...props} />;
  }
};

/* --------------------------------------------------------------- fixtures */

/**
 * The supplied animated lockup, inlined so its CSS keyframes can be scrubbed.
 * Remotion renders every frame in a fresh page, so a CSS animation would sit
 * frozen at t=0. Pausing it and driving animation-delay from the frame makes
 * it deterministic. The sting plays once and holds, rather than looping for
 * the whole take.
 */
const AnimatedLogo: React.FC<{ brand: Brand }> = ({ brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = useSoft(FIX.logoFromFrame, M.chunkInFrames);

  // The partner cut carries no Kyros mark anywhere in the take.
  const hidden = (FIX.logoHideWindows ?? []).some(([a, b]) => frame >= a && frame < b);
  if (!brand.logo.enabled || frame < FIX.logoFromFrame || hidden) {
    return null;
  }

  // The supplied mark is authored `infinite alternate`, so it pulses forever
  // when opened in a browser. Looping keeps that; clamping plays it once and
  // holds, which stops the bar competing with the captions for 19 seconds.
  // Whichever the brand wants — layout.logo.loop decides.
  const elapsed = (frame - FIX.logoFromFrame) / fps;
  const scrub = L.logo.loop
    ? elapsed % (L.logo.stingSeconds * 2)   // *2: one out-and-back of `alternate`
    : Math.min(elapsed, L.logo.stingSeconds);
  const scale = L.logo.width / 479.3203125;

  return (
    <div
      style={{
        position: "absolute",
        right: L.logo.right,
        top: L.logo.y,
        width: L.logo.width,
        opacity: L.logo.opacity * reveal,
        filter: "drop-shadow(0 2px 10px rgba(233,195,159,0.75))",
      }}
    >
      <style>{`
        .kyros-sting .animated-bar {
          animation-play-state: paused !important;
          animation-delay: -${scrub}s, -${scrub}s !important;
        }
        .kyros-sting svg { width: 100%; height: auto; display: block; }
      `}</style>
      <div
        className="kyros-sting"
        style={{ transform: `scale(${scale <= 1 ? 1 : 1})` }}
        dangerouslySetInnerHTML={{ __html: KYROS_STING_SVG }}
      />
    </div>
  );
};

/**
 * The supplied lower-third. Name and title are artwork, so nothing is
 * retyped here. It appears as she begins the answer, holds ~1.9s and leaves —
 * it is deliberately not on screen for the rest of the take.
 *
 * Offsets position by the visible pill inside the PNG, not by the file's
 * transparent padding, so `left` and `top` mean what they say.
 */
const DoctorPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const D = L.doctorPlate;
  const a = FIX.plateFromFrame;
  const IN = 16;
  const OUT = 12;
  const z = a + D.holdFrames;
  if (frame < a || frame > z + OUT) {
    return null;
  }
  const inP = interpolate(frame, [a, a + IN], [0, 1], { ...CLAMP, easing: Easing.out(Easing.cubic) });
  const outP = interpolate(frame, [z, z + OUT], [0, 1], { ...CLAMP, easing: Easing.in(Easing.cubic) });
  const k = D.targetPillWidth / D.pillWidth;
  const w = D.fileWidth * k;
  // Reveal left to right as it slides in; hide right to left as it leaves.
  const rightClip = (1 - inP) * 100;
  const leftShift = outP * 100;
  const clip = `inset(-20% ${Math.max(rightClip, leftShift)}% -20% 0% round 999px)`;
  return (
    <div
      style={{
        position: "absolute",
        left: D.left - D.pillX * k,
        top: D.top - D.pillY * k,
        width: w,
        height: D.fileHeight * k,
        opacity: Math.min(1, inP * 1.6) * (1 - outP * 0.6),
        transform: `translateX(${(1 - inP) * -34 - outP * 22}px)`,
        clipPath: clip, WebkitClipPath: clip,
        filter: "drop-shadow(0 10px 22px rgba(0,0,0,0.28))",
      }}
    >
      <Img src={staticFile(D.src)} style={{ width: "100%", height: "100%", display: "block" }} />
    </div>
  );
};

/* ------------------------------------------------------ phase 1: the hook */

const QuestionHook: React.FC = () => {
  const frame = useCurrentFrame();
  const exit = interpolate(
    frame,
    [questionPhase.exitFrame, questionPhase.exitFrame + questionPhase.exitDurationInFrames],
    [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (exit >= 1) {
    return null;
  }

  // First screen: the shadow deepens as the payload lands, so the big word
  // reads as it punches in rather than floating. Stronger than the in-scene
  // captions, since this is the hook.
  const keyRow = questionPhase.rows.find((r) => r.style === "key");
  const landFrom = keyRow ? keyRow.appearFrame : 0;
  const land = interpolate(frame, [landFrom, landFrom + M.wipeFrames], [0.55, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  // The card decides the whole register of the opening. A dark ground takes a
  // dark drop shadow; a light one would be smudged by it, so it gets a faint
  // light-side lift instead.
  const card = questionPhase.card;
  const onDarkCard = card ? card.dark : true;
  const shadow = onDarkCard
    ? `0 6px 26px rgba(0,0,0,${(0.78 * land).toFixed(3)}), `
      + `0 2px 8px rgba(0,0,0,${(0.62 * land).toFixed(3)})`
    : `0 2px 10px rgba(0,0,0,${(0.14 * land).toFixed(3)})`;

  // Texture keeps the panel from reading as a flat fill. A vignette pulls the
  // corners down on a dark card; grain is a fine noise wash for a light one.
  const texture =
    card?.texture === "vignette"
      ? "radial-gradient(120% 85% at 50% 42%, rgba(255,255,255,0.055) 0%, rgba(255,255,255,0) 55%, rgba(0,0,0,0.42) 100%)"
      : card?.texture === "grain"
        ? "radial-gradient(110% 80% at 50% 38%, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 60%), "
          + "repeating-linear-gradient(37deg, rgba(0,0,0,0.028) 0px, rgba(0,0,0,0.028) 1px, rgba(0,0,0,0) 1px, rgba(0,0,0,0) 3px)"
        : undefined;

  // The opening can be pictures of what the question asks about, from frame
  // 1 — cut on the words, in sequence. When they cover the whole question the
  // card goes (cardOpacity 0) and a measured glow sits behind the words only.
  const HOOKS = VITEMS.filter((i) => i.treatment === "hookBackdrop");
  const HB = HOOKS[0];
  const cardOpacity =
    HB && HB.cardOpacity !== undefined ? HB.cardOpacity : questionPhase.scrimOpacity;
  const glow = HB?.glow;

  return (
    <AbsoluteFill style={{ opacity: 1 - exit }}>
      {HOOKS.map((h, i) => {
        const end = i === HOOKS.length - 1
          ? h.toFrame + questionPhase.exitDurationInFrames : h.toFrame;
        if (frame < h.fromFrame || frame >= end) {
          return null;
        }
        return (
          <AbsoluteFill key={h.id} style={{ overflow: "hidden" }}>
            <Sequence from={h.fromFrame} durationInFrames={Math.max(1, end - h.fromFrame)}
              layout="none">
              <Picture it={h} w={1080} h={1920} />
            </Sequence>
          </AbsoluteFill>
        );
      })}
      {glow ? (
        <div
          style={{
            position: "absolute", left: glow.rect[0], top: glow.rect[1],
            width: glow.rect[2] - glow.rect[0], height: glow.rect[3] - glow.rect[1],
            opacity: glow.opacity,
            background: `radial-gradient(ellipse 72% 50% at 50% 50%, ${glow.color} 0%, ${glow.color} 58%, ${rgba(glow.color, 0)} 100%)`,
          }}
        />
      ) : null}
      {/* The card is what makes the doctor disappear, in both render modes. */}
      <AbsoluteFill
        style={{
          backgroundColor: card ? card.bg : P.onDark.scrim,
          opacity: cardOpacity,
        }}
      />
      {texture ? (
        <AbsoluteFill
          style={{ background: texture, opacity: cardOpacity }}
        />
      ) : null}
      <AbsoluteFill
        style={{
          justifyContent: "center", alignItems: "center",
          padding: `0 ${L.topZone.paddingX}px`,
          transform: `translateY(${-30 * exit}px)`,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          {questionPhase.rows.map((row, i) =>
            row.style === "lead" ? (
              <div key={i} style={{ marginTop: i === 0 ? 0 : 14 }}>
                <LeadLine
                  words={row.words.map((w) => QW[w])}
                  size={TL.questionSize}
                  color={row.color ?? card?.lead ?? P.onDark.lead}
                  shadow={shadow}
                />
              </div>
            ) : (
              <KeyLines
                key={i}
                lines={row.lines as string[]}
                size={row.size as number}
                fromFrame={row.appearFrame}
                color={row.color ?? card?.key ?? P.onDark.key}
                shadow={shadow}
              />
            )
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------- phase 2: the answer */

/** Linear enter/exit visibility of a chunk, without hooks — safe in a loop. */
const chunkVis = (chunk: Chunk, frame: number): number => {
  const enter = interpolate(frame, [chunk.fromFrame, chunk.fromFrame + M.chunkInFrames],
    [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const exit = interpolate(frame, [chunk.toFrame, chunk.toFrame + M.chunkOutFrames],
    [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return enter * (1 - exit);
};

/**
 * A soft scrim under the bottom-zone captions. It only exists while a bottom
 * chunk is on screen (max over their visibilities, so back-to-back bottom
 * chunks hand off without the band flickering). A top-to-bottom gradient keeps
 * the subject's face clear and darkens only where the low caption sits.
 */
const CaptionScrim: React.FC = () => {
  const frame = useCurrentFrame();
  if (!L.captionScrim.enabled) {
    return null;
  }
  let vis = 0;
  for (const c of answerPhase.chunks) {
    if (c.zone === "bottom") {
      vis = Math.max(vis, chunkVis(c, frame));
    }
  }
  if (vis <= 0) {
    return null;
  }
  const c = L.captionScrim;
  return (
    <div
      style={{
        position: "absolute",
        left: 0, right: 0, top: c.top, bottom: 0,
        opacity: vis * c.opacity,
        // `feather` is how far the panel takes to fade out at its top edge.
        // A large value is the soft wash; a small one is a clean cut, which is
        // what keeps the panel off the doctor's face instead of creeping up
        // her chin. Fades to its OWN colour at zero alpha, not to transparent
        // black, so a light panel does not grey off as it goes.
        background: `linear-gradient(to top, ${c.color} 0px, ${c.color} calc(100% - ${
          c.feather ?? Math.round((1920 - c.top) * 0.45)
        }px), ${c.color}00 100%)`,
      }}
    />
  );
};

const ChunkBlock: React.FC<{ chunk: Chunk }> = ({ chunk }) => {
  const frame = useCurrentFrame();
  const enter = useSoft(chunk.fromFrame, M.chunkInFrames);
  const exit = interpolate(
    frame, [chunk.toFrame, chunk.toFrame + M.chunkOutFrames], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (frame < chunk.fromFrame || exit >= 1) {
    return null;
  }

  const bottom = chunk.zone === "bottom";
  const Z = bottom ? L.bottomZone : L.topZone;
  const scrimOn = L.captionScrim.enabled;

  // Colour is per beat, chosen by the palette engine (an elegant, APCA-checked
  // rotation) and paired: the big payload is one colour, the small lead another.
  // Fall back to the zone palette if a beat carries no colour.
  const palFallback = !bottom ? P.onLight : scrimOn ? P.onDark : (P.bottomText ?? P.onDark);
  const keyColor = chunk.keyColor ?? (chunk.tone === "keyAlt" ? palFallback.keyAlt : palFallback.key);
  const leadColor = chunk.leadColor ?? palFallback.lead;

  // Shadow follows the *text* colour, not the zone: a light glyph gets a faint
  // dark edge, a dark glyph a faint light edge — just enough to hold against a
  // busy patch, never a box. On the scrim the old cream-on-dark shadow stays.
  // Dark glyphs get a whisper-light halo; light (cream/yellow) glyphs get a
  // slightly firmer dark edge — enough to hold on the bright saree, still a
  // per-letter shade, never a box behind the line.
  const faint = (dark?: boolean) =>
    dark
      ? "0 1px 3px rgba(255,255,255,0.32), 0 0 2px rgba(255,255,255,0.22)"
      : "0 2px 6px rgba(0,0,0,0.5), 0 1px 2px rgba(0,0,0,0.45)";
  const topShadow = `0 3px 16px ${P.scene.wallShadow}, 0 1px 3px rgba(0,0,0,0.18)`;
  // On a scrim the shadow must follow the GLYPH's polarity, not just the fact
  // that a scrim is present. A light glyph on a dark panel wants a dark lift;
  // a dark glyph on a light panel given the same treatment gets a black smear
  // around every letter — which is exactly what it looked like. The ground is
  // uniform and the contrast is 80+ Lc, so dark-on-light needs nothing at all.
  const onScrim = (dark?: boolean) =>
    dark ? "none" : "0 4px 22px rgba(0,0,0,0.55), 0 1px 4px rgba(0,0,0,0.35)";
  const keyShadow = scrimOn ? onScrim(chunk.keyDark) : bottom ? faint(chunk.keyDark) : topShadow;
  const leadShadow = scrimOn ? onScrim(chunk.leadDark) : bottom ? faint(chunk.leadDark) : topShadow;

  return (
    <div
      style={{
        position: "absolute",
        top: Z.top, left: 0, right: 0, height: Z.height,
        padding: `0 ${Z.paddingX}px`,
        display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        opacity: enter * (1 - exit),
        transform: `translateY(${-22 * exit}px)`,
      }}
    >
      {chunk.leadWords.length > 0 ? (
        <LeadLine
          words={chunk.leadWords.map((w) => AW[w])}
          size={chunk.leadSize}
          color={leadColor}
          shadow={leadShadow}
        />
      ) : null}
      <KeyLines
        lines={chunk.keyLines}
        size={chunk.keySize}
        fromFrame={chunk.keyFromFrame}
        color={keyColor}
        shadow={keyShadow}
        listIndex={chunk.listIndex}
        listTotal={chunk.listTotal}
        reveal={chunk.reveal}
      />
    </div>
  );
};

/* ----------------------------------------------------- phase 3: the outro */

/**
 * The end card, in whichever form the brand takes.
 *
 * "clip"      — the supplied Kyros MP4, played exactly as delivered: hard cut,
 *               no crossfade, no added motion, nothing laid over it.
 * "logo-card" — the partner mark held on a flat field.
 *
 * The Sequence wrapper matters for the clip. Without it OffthreadVideo reads
 * its time from the composition timeline, so at frame 491 it would ask a
 * 3-second clip for its frame at 16.4s and hold the last frame instead of
 * playing. Sequence restarts local time at 0 so the clip runs 0 -> 3.0s.
 */
const Outro: React.FC<{ brand: Brand }> = ({ brand }) => {
  const { outro } = brand;

  return (
    <Sequence
      from={outro.enterFrame}
      durationInFrames={outro.durationInFrames}
      layout="none"
    >
      {outro.kind === "clip" ? (
        <AbsoluteFill>
          <OffthreadVideo
            src={staticFile(outro.src)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      ) : (
        <AbsoluteFill
          style={{
            backgroundColor: outro.background,
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Img
            src={staticFile(outro.src)}
            style={{ width: outro.logoWidth, height: "auto", display: "block" }}
          />
        </AbsoluteFill>
      )}
    </Sequence>
  );
};

/* ------------------------------------------------------------ composition */

const Footage: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame >= data.meta.videoFrames) {
    return null;
  }
  // While she is in the bubble, DoctorBubble draws her and the frame is the
  // picture's. Never true on a clip without supporting visuals.
  // Keep drawing her under a full-frame picture: the picture's own fade is
  // the transition, so she must still be there while it is part-transparent.
  // Scale about the frame centre, then shift up by exactly the height the
  // scale created at the bottom edge — the frame stays covered top and bottom
  // while her head rises into the wall that used to sit above it.
  const Z = data.zoom;
  let zoomStyle: React.CSSProperties | undefined;
  if (Z) {
    const win = Z.windows.find(([a, b]) => frame >= a && frame < b);
    if (win) {
      const s = interpolate(
        frame,
        [win[0], win[0] + Z.easeFrames, win[1] - Z.easeFrames, win[1]],
        [1, Z.scale, Z.scale, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
      zoomStyle = {
        transform: `translateY(${(1 - s) * 960}px) scale(${s})`,
      };
    }
  }
  return (
    <AbsoluteFill style={zoomStyle}>
      <OffthreadVideo
        src={staticFile(data.meta.videoSrc)}
        muted
        style={{
          position: "absolute", top: L.video.offsetY, left: 0,
          width: L.video.renderWidth, height: L.video.renderHeight,
          objectFit: "cover",
        }}
      />
    </AbsoluteFill>
  );
};

export type DoctorVideoProps = {
  showVideo: boolean;
  transparent: boolean;
  /** Which cut: the Kyros original, or the Aster Ramesh partner version. */
  brandId: BrandId;
};

export const DoctorVideo: React.FC<DoctorVideoProps> = ({
  showVideo,
  transparent,
  brandId,
}) => {
  const brand = BRANDS[brandId];
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // No global fade — the supplied outro ends the piece on its own frames.
  const fadeOut = 1;

  return (
    <AbsoluteFill
      style={{ backgroundColor: transparent ? undefined : P.scene.wall }}
    >
      {showVideo ? <Audio src={staticFile(data.meta.audioSrc)} /> : null}
      <AbsoluteFill style={{ opacity: fadeOut }}>
        {/* Everything from the take is gated off once the outro takes over. */}
        {frame < brand.outro.enterFrame ? (
          <>
            {showVideo ? <Footage /> : null}
            {showVideo ? <SupportingVisuals /> : null}
            {showVideo ? <DoctorBubble /> : null}
            {showVideo ? <CaptionWash /> : null}
            <CaptionScrim />
            {answerPhase.chunks.map((c) => (
              <ChunkBlock key={c.id} chunk={c} />
            ))}
            <DoctorPlate />
            <AnimatedLogo brand={brand} />
            <QuestionHook />
          </>
        ) : null}
        <Outro brand={brand} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default DoctorVideo;
