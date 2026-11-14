import { useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";
import Orb from "./Orb.jsx";

/** Glass capsule: icons, the active tab opens with its label, a lens slides between tabs. */
export default function TabBar({ tabs, active, onSelect, side }) {
  const wrap = useRef(null);
  const btns = useRef({});
  const [lens, setLens] = useState(null);
  const [moving, setMoving] = useState(false);
  const prev = useRef(active);
  // press and slide along the bar (like Telegram): a glass lens follows the finger, the tab under it lights up,
  // releasing opens that tab
  const [drag, setDrag] = useState(null);           // { x, over } while the finger is down
  const g = useRef(null), skipClick = useRef(false);
  const tabAt = (cx) => {
    for (const t of tabs) { const r = btns.current[t.k]?.getBoundingClientRect(); if (r && cx >= r.left - 1 && cx <= r.right + 1) return t.k; }
    return null;
  };
  const down = (e) => {
    if (!lens || (e.pointerType === "mouse" && e.button !== 0)) return;
    const pr = wrap.current.getBoundingClientRect();
    g.current = { id: e.pointerId, x0: e.clientX, left: pr.left, width: pr.width, moved: false, over: active };
  };
  const move = (e) => {
    const s = g.current; if (!s || s.id !== e.pointerId) return;
    if (!s.moved && Math.abs(e.clientX - s.x0) < 6) return;
    if (!s.moved) { s.moved = true; try { wrap.current.setPointerCapture(e.pointerId); } catch {} haptic("light"); }
    const W = 68;                                   // the lens shrinks to one tab's size while it follows the finger
    const x = Math.max(3, Math.min(s.width - W - 3, e.clientX - s.left - W / 2));
    const over = tabAt(e.clientX) || s.over;
    if (over !== s.over) { s.over = over; haptic("select"); }
    setDrag({ x, over });
  };
  const up = (e) => {
    const s = g.current; g.current = null;
    if (!s || s.id !== e.pointerId) return;
    if (s.moved) {
      skipClick.current = true; setTimeout(() => { skipClick.current = false; }, 0);
      setDrag(null);
      if (s.over && s.over !== active) onSelect(s.over);
    }
  };

  // Final geometry is computed ahead of time: labels are still opening while the lens flies.
  const target = () => {
    const pad = 5, gap = 2, open = 7;
    let x = pad;
    for (const t of tabs) {
      const b = btns.current[t.k]; if (!b) return null;
      const l = b.querySelector(".gnav-l");
      const curL = l.getBoundingClientRect().width + parseFloat(getComputedStyle(l).marginLeft || 0);
      const base = b.getBoundingClientRect().width - curL;
      const w = base + (t.k === active ? l.scrollWidth + open : 0);
      if (t.k === active) return { x, w };
      x += w + gap;
    }
    return null;
  };
  useLayoutEffect(() => {
    const t = target(); if (t) setLens(t);
    if (prev.current !== active) {
      prev.current = active;
      setMoving(true);
      const id = setTimeout(() => setMoving(false), 420);
      return () => clearTimeout(id);
    }
  }, [active]);
  useLayoutEffect(() => {
    const r = () => { const t = target(); if (t) setLens(t); };
    window.addEventListener("resize", r);
    document.fonts?.ready.then(r);
    return () => window.removeEventListener("resize", r);
  }, [active]);

  return (
    <nav className="gnav" aria-label="Разделы">
      <div className={"gnav-pill" + (drag ? " dragging" : "")} ref={wrap}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={() => { g.current = null; setDrag(null); }}
        onClickCapture={(e) => { if (skipClick.current) { e.stopPropagation(); e.preventDefault(); } }}>
        {lens && <span className={"gnav-lens" + (moving ? " moving" : "") + (drag ? " grab" : "")}
          style={{ transform: `translateX(${drag ? drag.x : lens.x}px)`, width: drag ? 68 : lens.w }} aria-hidden="true" />}
        {tabs.map((t) => {
          const on = t.k === active;
          return (
            <button key={t.k} ref={(el) => (btns.current[t.k] = el)} className={"gnav-tab" + (on ? " on" : "") + (drag?.over === t.k ? " over" : "")}
              aria-current={on ? "page" : undefined} aria-label={t.t} onClick={() => { if (!on) { haptic("select"); onSelect(t.k); } }}>
              <Icon n={t.i} s={20} w={on ? 2.1 : 1.8} />
              <span className="gnav-l">{t.t}</span>
            </button>);
        })}
      </div>
      {side && (
        <button className={"gnav-side" + (side.accent ? " accent" : "")} aria-label={side.label} onClick={() => { haptic("light"); side.onClick(); }}>
          {side.orb ? <Orb size={48} /> : <Icon n={side.i} s={21} />}
          {side.badge ? <b className="gnav-badge">{side.badge}</b> : null}
        </button>)}
    </nav>);
}

/** Segmented tabs with a sliding dark pill (filters). */
export function SlideTabs({ items, value, onChange, label }) {
  const wrap = useRef(null);
  const btns = useRef({});
  const [pill, setPill] = useState(null);
  const [more, setMore] = useState(false);
  useLayoutEffect(() => {
    const w = wrap.current; if (!w) return;
    const f = () => setMore(w.scrollLeft + w.clientWidth < w.scrollWidth - 4);
    f(); w.addEventListener("scroll", f, { passive: true }); window.addEventListener("resize", f);
    return () => { w.removeEventListener("scroll", f); window.removeEventListener("resize", f); };
  }, [items.length]);
  useLayoutEffect(() => {
    const b = btns.current[value], w = wrap.current;
    if (!b || !w) return;
    setPill({ x: b.offsetLeft, w: b.offsetWidth });
    const sl = b.offsetLeft - (w.clientWidth - b.offsetWidth) / 2;
    w.scrollTo({ left: Math.max(0, sl), behavior: "smooth" });
  }, [value, items.length]);
  return (
    <div className={"stabs" + (more ? " more" : "")} ref={wrap} role="tablist" aria-label={label}>
      {pill && <span className="stabs-pill" style={{ transform: `translateX(${pill.x}px)`, width: pill.w }} aria-hidden="true" />}
      {items.map((x) => (
        <button key={x.k} ref={(el) => (btns.current[x.k] = el)} role="tab" aria-selected={value === x.k}
          className={"stab" + (value === x.k ? " on" : "")} onClick={() => { haptic("select"); onChange(x.k); }}>
          {x.i && <Icon n={x.i} s={15} />}{x.t}
        </button>))}
    </div>);
}
