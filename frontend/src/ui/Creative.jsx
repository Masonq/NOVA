import { useRef } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";
import { MicrophoneStage, DiscoBall, Headphones, SpeakerHifi, Equalizer, Guitar, CloudMoon, PianoKeys, FilmSlate, Plant,
  Camera, Palette, PenNib, Cube, Sparkle, Waves, Lightning, Microphone, Feather, MagicWand, Diamond, SpeakerHigh, MusicNotes } from "@phosphor-icons/react";

/** Shared creative controls of the studios: cover tiles, aspect shapes, option cards, feature switches, mood glow. */
/** Tile pictures: Phosphor duotone icons (white on the tile gradient). */
const GLYPH = {
  wave: MicrophoneStage, rings: DiscoBall, vinyl: Headphones, bars: SpeakerHifi, grid: Equalizer, bolt: Guitar, mist: CloudMoon,
  notes: PianoKeys, film: FilmSlate, leaf: Plant,
  aperture: Camera, brush: Palette, hex: PenNib, cube: Cube, sparkle: Sparkle,
  calm: Waves, energy: Lightning, mic: Microphone, whisper: Feather,
};
/** How each picture comes alive while its tile is selected (like the equalizer of «Звук»). */
export const ANIM = {
  wave: "bob", rings: "spin", vinyl: "pulse", bars: "thump", grid: "thump", bolt: "wiggle", mist: "float", notes: "bob", film: "clap", leaf: "sway",
  aperture: "flash", brush: "wiggle", hex: "write", cube: "turn", sparkle: "twinkle",
  calm: "drift", energy: "flash", mic: "bob", whisper: "sway",
};
export function Motif({ m, size = 34 }) {
  const G = GLYPH[m];
  return G ? <G size={size} weight="duotone" color="#fff" /> : null;
}

/** Single-choice cover tiles (style, intonation). items: [{ v, t, a, b, m, sub? }] */
export function Tiles({ label, hint, items, value, onChange, grid }) {
  return (
    <div className="mc-block" role="radiogroup" aria-label={label}>
      <div className="opts-h"><span>{label}</span>{hint && <small>{hint}</small>}</div>
      <div className={grid ? "g-grid" + (items.length > 4 ? " g5" : "") : "g-tiles"} style={grid ? { gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` } : undefined}>
        {items.map((it) => {
          const on = value === it.v;
          return (
            <button key={it.v} role="radio" aria-checked={on} className={"g-tile" + (on ? " on" : "")} style={{ "--ga": it.a, "--gb": it.b }}
              onClick={() => { haptic("select"); onChange(it.v); }}>
              <span className={"g-ic a-" + ANIM[it.m]} aria-hidden="true"><Motif m={it.m} size={grid ? 28 : 34} /></span>
              <span>{it.t}{it.sub && <small>{it.sub}</small>}</span>
              {on && <i className="g-check"><Icon n="check" s={11} w={3} /></i>}
            </button>);
        })}
      </div>
    </div>);
}

/** Frame shapes drawn to scale: the user sees the format, not just «9:16». */
export function AspectPicker({ label = "Формат", value, onChange, items }) {
  return (
    <div className="mc-block" role="radiogroup" aria-label={label}>
      <div className="opts-h"><span>{label}</span><small>{items.find((x) => x.v === value)?.use}</small></div>
      <div className="asp-row" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((it) => {
          const [w, h] = it.v.split(":").map(Number), k = 34 / Math.max(w, h);
          const on = value === it.v;
          return (
            <button key={it.v} role="radio" aria-checked={on} className={"asp" + (on ? " on" : "")} onClick={() => { haptic("select"); onChange(it.v); }}>
              <span className="asp-box"><i style={{ width: Math.round(w * k), height: Math.round(h * k) }} /></span>
              <b>{it.t}</b><small>{it.v}</small>
            </button>);
        })}
      </div>
    </div>);
}

/** Option cards with a small picture and an optional price: duration, quality. items: [{ v, t, sub, vis }] */
export function CardChoice({ label, hint, items, value, onChange }) {
  return (
    <div className="mc-block" role="radiogroup" aria-label={label}>
      <div className="opts-h"><span>{label}</span>{hint && <small>{hint}</small>}</div>
      <div className="cc-row" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((it) => {
          const on = value === it.v;
          return (
            <button key={String(it.v)} role="radio" aria-checked={on} className={"cc" + (on ? " on" : "")} onClick={() => { haptic("select"); onChange(it.v); }}>
              {it.vis && <span className="cc-vis" aria-hidden="true">{it.vis}</span>}
              <b>{it.t}</b>{it.sub && <small>{it.sub}</small>}
            </button>);
        })}
      </div>
    </div>);
}

function FIcon({ tone }) {
  const G = { wild: MagicWand, gold: Diamond, sound: SpeakerHigh }[tone] || Sparkle;
  return <span className={"f-ic a-" + ({ wild: "wiggle", gold: "twinkle" }[tone] || "pulse")}><G size={20} weight="duotone" /></span>;
}
export { MusicNotes, MicrophoneStage };

/** A switch card that comes alive when on. tone: wild | gold | sound */
export function FeatureToggle({ on, onChange, title, sub, subOn, icon, tone = "wild" }) {
  return (
    <button className={"wild t-" + tone + (on ? " on" : "")} role="switch" aria-checked={on} onClick={() => { haptic(on ? "select" : "medium"); onChange(!on); }}>
      <span className="wild-ic" aria-hidden="true">
        {tone === "sound" && on ? <span className="eq"><i /><i /><i /><i /></span> : <FIcon tone={tone} />}
        {on && tone !== "sound" && <><i className="sp s1" /><i className="sp s2" /><i className="sp s3" /></>}
      </span>
      <span className="sr-t"><span>{title}</span><small>{on && subOn ? subOn : sub}</small></span>
      <span className={"switch" + (on ? " on" : "")} aria-hidden="true"><i /></span>
    </button>);
}

/** Soft colour light at the top of a studio, follows the chosen style. */
export function Glow({ color }) {
  return <i className="mus-glow" aria-hidden="true" style={{ color }} />;
}

/** Quick prompt ideas: tap to put one in the field. */
export function Ideas({ items, onPick }) {
  const row = useRef(null);
  return (
    <div className="ideas" ref={row} aria-label="Идеи">
      <span className="ideas-l"><Icon n="spark" s={12} w={2.2} />Идеи</span>
      {items.map((t) => <button key={t} className="idea" onClick={() => { haptic("select"); onPick(t); }}>{t}</button>)}
    </div>);
}
