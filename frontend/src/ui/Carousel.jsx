import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";

/** A picture for works without one (a voice-over, a track without a cover): a soft gradient and a waveform,
 *  stable per work, warm for female voices, cool for male ones — so no card is an empty box. */
const FEMALE = new Set(["Sulafat", "Aoede", "Leda", "Kore"]);
function Art({ seed = 1, voice, kind }) {
  const female = FEMALE.has(voice);
  const [a, b] = kind === "music" ? ["#7A3CFF", "#FF4FA3"] : female ? ["#B04CFF", "#FF7AB6"] : ["#2D6BFF", "#33D1FF"];
  let x = (Number(seed) || 7) % 97 + 13;
  const bars = Array.from({ length: 24 }, () => { x = (x * 73 + 19) % 101; return 22 + (x % 70); });
  return (
    <span className="gart" style={{ "--a": a, "--b": b }} aria-hidden="true">
      <span className="gart-w">{bars.map((h, k) => <i key={k} style={{ height: `${h}%` }} />)}</span>
    </span>);
}

/** 3D glass carousel (ref: Glassy Carousel V2): the picture fades into a frosted glass panel with the title,
 *  the counter and a short description; neighbours stack behind it in perspective.
 *  items: [{ key, img, kind, voice, seed, title, desc, sub, onOpen, onMore }] */
export default function Carousel({ items, index: start = 0, onChange, label = "Карусель", height = 380 }) {
  const [i, setI] = useState(start);
  const [drag, setDrag] = useState(0);
  const st = useRef(null);
  const n = items.length;
  useEffect(() => { setI((x) => Math.min(x, Math.max(0, n - 1))); }, [n]);
  useEffect(() => { setI(start); }, [start]);
  const go = (k) => { const v = Math.max(0, Math.min(n - 1, k)); if (v !== i) { haptic("select"); setI(v); onChange?.(v); } };
  const down = (e) => { st.current = { x: e.clientX, y: e.clientY, t: Date.now(), lock: null }; };
  const move = (e) => {
    const s = st.current; if (!s) return;
    const dx = e.clientX - s.x, dy = e.clientY - s.y;
    if (s.lock === null && (Math.abs(dx) > 6 || Math.abs(dy) > 6)) s.lock = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    if (s.lock === "x") setDrag(dx);
  };
  const up = () => {
    const s = st.current; st.current = null;
    if (!s || s.lock !== "x") { setDrag(0); return; }
    const fast = Math.abs(drag) / Math.max(1, Date.now() - s.t) > 0.4;
    const step = Math.abs(drag) > 70 || fast ? (drag < 0 ? 1 : -1) * Math.max(1, Math.round(Math.abs(drag) / 220)) : 0;
    setDrag(0); go(i + step);
  };
  const key = (e) => { if (e.key === "ArrowRight") go(i + 1); if (e.key === "ArrowLeft") go(i - 1); };
  if (!n) return null;
  const pos = i - drag / 220;
  return (
    <div className="gcar" style={{ height }} role="region" aria-roledescription="карусель" aria-label={label} tabIndex={0} onKeyDown={key}
      onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onPointerLeave={() => st.current && up()}>
      {items.map((it, k) => {
        const d = k - pos, a = Math.abs(d);
        if (a > 3.2) return null;
        const style = {
          // neighbours step out less with distance, so three of them stack on each side like in the reference
          transform: `translateX(calc(-50% + ${Math.sign(d) * (Math.min(a, 1) * 50 + Math.max(0, a - 1) * 24)}%)) translateZ(${-Math.min(a, 3) * 110}px) rotateY(${Math.max(-34, Math.min(34, -d * 28))}deg) scale(${1 - Math.min(a, 3) * 0.09})`,
          zIndex: 100 - Math.round(a * 10),
          opacity: a > 2.6 ? Math.max(0, 3.2 - a) / 0.6 : 1,
          transition: drag ? "none" : undefined,
        };
        const center = Math.round(pos) === k;
        return (
          <article key={it.key} className={"gcard k-" + (it.kind || "image") + (center ? " on" : "")} style={style}
            aria-hidden={!center} aria-label={`${k + 1} из ${n}: ${it.title}`}
            onClick={() => { if (Math.abs(drag) < 4 && !center) go(k); }}>
            <span className="gmedia">{it.img ? <img src={it.img} alt="" draggable="false" loading="lazy" /> : <Art seed={it.seed} voice={it.voice} kind={it.kind} />}</span>
            <span className="gcard-dim" style={{ opacity: Math.min(0.55, a * 0.24) }} />
            {center && it.onOpen && <button className="gchip l" onClick={(e) => { e.stopPropagation(); it.onOpen(); }}><Icon n="expand" s={13} />Открыть</button>}
            {center && it.onMore && <button className="gchip r" aria-label="Действия" onClick={(e) => { e.stopPropagation(); it.onMore(); }}><Icon n="more" s={15} /></button>}
            <div className="gcap">
              <div className="gcap-h"><b>{it.title}</b><span>{k + 1} / {n}</span></div>
              {it.sub && <small className="gcap-s">{it.sub}</small>}
              {it.desc && <p>{it.desc}</p>}
            </div>
          </article>);
      })}
    </div>);
}
