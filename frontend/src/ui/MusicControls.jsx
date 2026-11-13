import { useMemo, useRef } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";
import { Motif, FeatureToggle, MusicNotes, MicrophoneStage } from "./Creative.jsx";

/* ---------- genres: cover tiles ---------- */
export const GENRE_ART = {
  "Рэп":         { a: "#5B2BD6", b: "#170A3A", m: "wave" },
  "Поп":         { a: "#FF5FA2", b: "#5A1240", m: "rings" },
  "Lo-fi":       { a: "#F2A65A", b: "#4A2A12", m: "vinyl" },
  "Хип-хоп":     { a: "#F5C343", b: "#3D2B05", m: "bars" },
  "Электроника": { a: "#22D3EE", b: "#062A44", m: "grid" },
  "Рок":         { a: "#FF4D3D", b: "#3A0A08", m: "bolt" },
  "Эмбиент":     { a: "#7EE0C3", b: "#0B3A33", m: "mist" },
  "Джаз":        { a: "#E8B26A", b: "#2E1B3D", m: "notes" },
  "Кино":        { a: "#9AA8FF", b: "#141B45", m: "film" },
  "Фолк":        { a: "#A8D672", b: "#1E3511", m: "leaf" },
};

export function GenreTiles({ value, onChange, max = 3 }) {
  const toggle = (g) => {
    if (value.includes(g)) { haptic("select"); return onChange(value.filter((x) => x !== g)); }
    if (value.length >= max) { haptic("warning"); return; }
    haptic("select"); onChange([...value, g]);
  };
  return (
    <div className="mc-block" role="group" aria-label="Жанр">
      <div className="opts-h"><span>Жанр</span>
        {value.length ? <button className="mc-reset" onClick={() => { haptic("select"); onChange([]); }}>{value.join(" + ")} · сбросить</button> : <small>по описанию · до {max}</small>}</div>
      <div className="g-tiles">
        {Object.entries(GENRE_ART).map(([g, art]) => {
          const on = value.includes(g), dim = !on && value.length >= max;
          return (
            <button key={g} className={"g-tile" + (on ? " on" : "") + (dim ? " dim" : "")} aria-pressed={on} onClick={() => toggle(g)}
              style={{ "--ga": art.a, "--gb": art.b }}>
              <span className="g-ic" aria-hidden="true"><Motif m={art.m} /></span>
              <span>{g}</span>
              {on && <i className="g-check"><Icon n="check" s={11} w={3} /></i>}
            </button>);
        })}
      </div>
    </div>);
}

/* ---------- mood: a pad with a glowing point ---------- */
export function moodText(p) {
  if (!p) return "";
  const e = p.x < 0.34 ? "спокойно" : p.x > 0.66 ? "энергично" : "";
  const v = p.y > 0.66 ? "радостно" : p.y < 0.34 ? "грустно" : "";
  const ex = (p.x > 0.88 || p.x < 0.12) && e ? "очень " : "";
  const parts = [e && ex + e, v].filter(Boolean);
  return parts.length ? parts.join(" и ") : "ровно, без крайностей";
}
export function moodColor(p) {
  if (!p) return "hsl(250 60% 55%)";
  const hue = Math.round(205 - p.x * 190), sat = Math.round(45 + p.y * 40), lit = Math.round(42 + p.y * 14);
  return `hsl(${hue < 0 ? hue + 360 : hue} ${sat}% ${lit}%)`;
}

export function MoodPad({ value, onChange }) {
  const box = useRef(null), last = useRef("");
  const set = (e) => {
    const r = box.current.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y = Math.min(1, Math.max(0, 1 - (e.clientY - r.top) / r.height));
    const p = { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
    const t = moodText(p); if (t !== last.current) { last.current = t; haptic("select"); }
    onChange(p);
  };
  const key = (e) => {
    const d = { ArrowLeft: [-0.1, 0], ArrowRight: [0.1, 0], ArrowUp: [0, 0.1], ArrowDown: [0, -0.1] }[e.key];
    if (!d) return; e.preventDefault();
    const p = value || { x: 0.5, y: 0.5 };
    onChange({ x: Math.min(1, Math.max(0, p.x + d[0])), y: Math.min(1, Math.max(0, p.y + d[1])) });
  };
  return (
    <div className="mc-block">
      <div className="opts-h"><span>Настроение</span>
        {value ? <button className="mc-reset" onClick={() => { haptic("select"); onChange(null); }}>сбросить</button> : <small>по описанию</small>}</div>
      <div ref={box} className={"m-pad" + (value ? " set" : "")} role="slider" tabIndex={0} aria-label="Настроение"
        aria-valuetext={value ? moodText(value) : "по описанию"} onKeyDown={key}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); set(e); }}
        onPointerMove={(e) => { if (e.currentTarget.hasPointerCapture(e.pointerId)) set(e); }}>
        <span className="mp-l t">Радостно</span><span className="mp-l b">Грустно</span>
        <span className="mp-l l">Спокойно</span><span className="mp-l r">Энергично</span>
        <i className="mp-axis h" /><i className="mp-axis v" />
        {value
          ? <i className="mp-dot" style={{ left: `${value.x * 100}%`, top: `${(1 - value.y) * 100}%`, color: moodColor(value) }} />
          : <span className="mp-hint">Коснитесь, чтобы задать настроение</span>}
      </div>
      <p className="mp-say" aria-live="polite">{value ? moodText(value)[0].toUpperCase() + moodText(value).slice(1) : "ИИ подберёт по описанию"}</p>
    </div>);
}

/* ---------- length: a sound wave you stretch ---------- */
const STEPS = [0, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 210, 240];
const fmt = (s) => (s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "Авто");

export function LengthWave({ value, onChange }) {
  const box = useRef(null);
  const bars = useMemo(() => Array.from({ length: 56 }, (_, i) => 0.28 + 0.72 * Math.abs(Math.sin(i * 0.55) * 0.6 + Math.sin(i * 1.7 + 1) * 0.3 + Math.sin(i * 0.13) * 0.25)), []);
  const idx = Math.max(0, STEPS.indexOf(value));
  const frac = idx / (STEPS.length - 1);
  const set = (e) => {
    const r = box.current.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    const v = STEPS[Math.round(f * (STEPS.length - 1))];
    if (v !== value) { haptic("select"); onChange(v); }
  };
  const key = (e) => {
    const d = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[e.key];
    if (!d) return; e.preventDefault();
    onChange(STEPS[Math.min(STEPS.length - 1, Math.max(0, idx + d))]);
  };
  return (
    <div className="mc-block">
      <div className="opts-h"><span>Длина</span><small>{value ? "примерно" : "ИИ решит сам"}</small></div>
      <div className="l-wave-w">
        <b className={"l-val" + (value ? "" : " auto")}>{fmt(value)}</b>
        <div ref={box} className="l-wave" role="slider" tabIndex={0} aria-label="Длина трека" aria-valuemin={0} aria-valuemax={240}
          aria-valuenow={value} aria-valuetext={value ? `${fmt(value)} минуты` : "Авто"} onKeyDown={key}
          onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); set(e); }}
          onPointerMove={(e) => { if (e.currentTarget.hasPointerCapture(e.pointerId)) set(e); }}>
          {bars.map((h, i) => <i key={i} className={i / (bars.length - 1) <= frac && value ? "on" : ""} style={{ height: `${Math.round(h * 100)}%` }} />)}
          <span className="l-thumb" style={{ left: `${frac * 100}%` }} />
        </div>
        <div className="l-scale" aria-hidden="true">{[0, 60, 120, 180, 240].map((v) => (
          <span key={v} style={{ left: `${(STEPS.indexOf(v) / (STEPS.length - 1)) * 100}%` }}>{fmt(v)}</span>))}</div>
      </div>
    </div>);
}

/* ---------- vocals: two cards ---------- */
export function VocalCards({ vocal, onChange }) {
  return (
    <div className="v-cards" role="radiogroup" aria-label="Вокал">
      <button role="radio" aria-checked={!vocal} className={"v-card" + (!vocal ? " on" : "")} onClick={() => { haptic("select"); onChange(false); }}>
        <span className="v-ic"><span className="f-ic"><MusicNotes size={21} weight="duotone" /></span></span><b>Только музыка</b><small>без голоса</small></button>
      <button role="radio" aria-checked={vocal} className={"v-card" + (vocal ? " on" : "")} onClick={() => { haptic("select"); onChange(true); }}>
        <span className="v-ic"><span className="f-ic"><MicrophoneStage size={21} weight="duotone" /></span></span><b>С голосом</b><small>ИИ напишет текст</small></button>
    </div>);
}

/* ---------- «Без чего»: field with quick picks ---------- */
const AVOID = ["без гитары", "без автотюна", "без барабанов", "без скрипок", "без мата"];
export function AvoidField({ value, onChange, vocal }) {
  const items = value.split(",").map((x) => x.trim()).filter(Boolean);
  const has = (t) => items.some((x) => x.toLowerCase() === t);
  const toggle = (t) => {
    haptic("select");
    onChange(has(t) ? items.filter((x) => x.toLowerCase() !== t).join(", ") : [...items, t].join(", "));
  };
  return (
    <div className="mc-block">
      <label className="opts-h" htmlFor="avoid"><span>Без чего</span><small>необязательно</small></label>
      <input id="avoid" className="mc-input" value={value} maxLength={200} onChange={(e) => onChange(e.target.value)} placeholder="Чего не должно быть в треке" />
      <div className="av-chips">
        {AVOID.filter((t) => vocal || !["без автотюна", "без мата"].includes(t)).map((t) => (
          <button key={t} className={"av-chip" + (has(t) ? " on" : "")} aria-pressed={has(t)} onClick={() => toggle(t)}>{has(t) ? <Icon n="check" s={11} w={3} /> : <Icon n="plus" s={11} w={2.6} />}{t}</button>))}
      </div>
    </div>);
}

/* ---------- Эксперимент ---------- */
export function WildToggle({ on, onChange }) {
  return <FeatureToggle on={on} onChange={onChange} title="Эксперимент" icon="spark" tone="wild"
    sub="необычное звучание, модель V6 Wild" subOn="V6 Wild: смелее и неожиданнее" />;
}
