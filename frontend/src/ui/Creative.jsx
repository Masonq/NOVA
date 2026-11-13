import { useRef } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";

/** Shared creative controls of the studios: cover tiles, aspect shapes, option cards, feature switches, mood glow. */
export function Motif({ m }) {
  const c = { fill: "none", stroke: "rgba(255,255,255,.85)", strokeWidth: 2.2, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (m) {
    case "wave": return <path {...c} d="M4 30c6-14 10 14 16 0s10-22 16 0 10 14 16 0 6-10 8-6" />;
    case "rings": return <g {...c}><circle cx="32" cy="30" r="8" /><circle cx="32" cy="30" r="16" opacity=".6" /><circle cx="32" cy="30" r="24" opacity=".3" /></g>;
    case "vinyl": return <g {...c}><circle cx="32" cy="30" r="20" /><circle cx="32" cy="30" r="13" opacity=".5" /><circle cx="32" cy="30" r="4" fill="rgba(255,255,255,.85)" /></g>;
    case "bars": return <g {...c} strokeWidth="5">{[14, 24, 34, 44, 54].map((x, i) => <path key={x} d={`M${x} 46V${[30, 16, 24, 10, 28][i]}`} />)}</g>;
    case "grid": return <g {...c} strokeWidth="1.6" opacity=".9">{[12, 24, 36, 48].map((v) => <path key={v} d={`M${v} 8v44M8 ${v - 2}h48`} />)}<circle cx="36" cy="22" r="4" fill="rgba(255,255,255,.9)" /></g>;
    case "bolt": return <path {...c} strokeWidth="2.6" d="M36 6L18 34h14l-4 20 20-30H34l2-18z" />;
    case "mist": return <g {...c} opacity=".9"><path d="M6 22c10-6 18 6 28 0s18-6 24 0" /><path d="M6 34c10-6 18 6 28 0s18-6 24 0" opacity=".6" /><path d="M6 46c10-6 18 6 28 0s18-6 24 0" opacity=".35" /></g>;
    case "notes": return <g {...c}><path d="M22 44V16l24-6v28" /><circle cx="17" cy="44" r="5" /><circle cx="41" cy="38" r="5" /></g>;
    case "film": return <g {...c}><rect x="10" y="12" width="44" height="36" rx="4" /><path d="M10 22h44M10 38h44M20 12v10M32 12v10M44 12v10M20 38v10M32 38v10M44 38v10" opacity=".6" /></g>;
    case "leaf": return <g {...c}><path d="M14 46C14 24 30 12 52 12c0 22-14 36-38 34z" /><path d="M14 46L40 22" opacity=".6" /></g>;
    case "aperture": return <g {...c}><circle cx="32" cy="30" r="20" /><path d="M32 10l8 16M52 30l-17 5M42 47l-10-13M22 47l6-16M12 30l18-3M22 13l9 14" opacity=".75" /></g>;
    case "brush": return <g {...c}><path d="M10 46c8 0 10-6 14-10s10-4 12 0-2 10-10 12-16-2-16-2z" /><path d="M36 34L54 12" strokeWidth="3" /></g>;
    case "hex": return <g {...c}><path d="M32 8l19 11v22L32 52 13 41V19z" /><path d="M26 22v16M26 30h12M38 22v16" strokeWidth="2.6" /></g>;
    case "cube": return <g {...c}><path d="M32 8l20 11v22L32 52 12 41V19z" /><path d="M12 19l20 11 20-11M32 30v22" opacity=".7" /></g>;
    case "sparkle": return <g {...c}><path d="M28 10c2 12 6 16 18 18-12 2-16 6-18 18-2-12-6-16-18-18 12-2 16-6 18-18z" /><path d="M48 40c1 5 3 7 8 8-5 1-7 3-8 8-1-5-3-7-8-8 5-1 7-3 8-8z" opacity=".7" /></g>;
    case "calm": return <g {...c}><path d="M6 36c8-8 14-8 22 0s14 8 22 0 8-6 10-6" /><circle cx="44" cy="16" r="6" opacity=".6" /></g>;
    case "mic": return <g {...c}><rect x="24" y="8" width="16" height="28" rx="8" /><path d="M16 30c0 9 7 16 16 16s16-7 16-16M32 46v8" /></g>;
    case "whisper": return <g {...c}><path d="M10 30h8M22 22v16M30 26v8M38 18v24M46 26v8M54 30h0" opacity=".85" /></g>;
    default: return null;
  }
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
              <svg viewBox="0 0 64 60" aria-hidden="true"><Motif m={it.m} /></svg>
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

/** A switch card that comes alive when on. tone: wild | gold | sound */
export function FeatureToggle({ on, onChange, title, sub, subOn, icon, tone = "wild" }) {
  return (
    <button className={"wild t-" + tone + (on ? " on" : "")} role="switch" aria-checked={on} onClick={() => { haptic(on ? "select" : "medium"); onChange(!on); }}>
      <span className="wild-ic" aria-hidden="true">
        {tone === "sound" && on ? <span className="eq"><i /><i /><i /><i /></span> : <Icon n={icon} s={18} w={2} />}
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
