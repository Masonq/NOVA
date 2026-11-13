import { useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";

/** Glass capsule: icons, the active tab opens with its label, a lens slides between tabs. */
export default function TabBar({ tabs, active, onSelect, side }) {
  const wrap = useRef(null);
  const btns = useRef({});
  const [lens, setLens] = useState(null);
  const [moving, setMoving] = useState(false);
  const prev = useRef(active);

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
      <div className="gnav-pill" ref={wrap}>
        {lens && <span className={"gnav-lens" + (moving ? " moving" : "")} style={{ transform: `translateX(${lens.x}px)`, width: lens.w }} aria-hidden="true" />}
        {tabs.map((t) => {
          const on = t.k === active;
          return (
            <button key={t.k} ref={(el) => (btns.current[t.k] = el)} className={"gnav-tab" + (on ? " on" : "")}
              aria-current={on ? "page" : undefined} aria-label={t.t} onClick={() => { if (!on) { haptic("select"); onSelect(t.k); } }}>
              <Icon n={t.i} s={20} w={on ? 2.1 : 1.8} />
              <span className="gnav-l">{t.t}</span>
            </button>);
        })}
      </div>
      {side && (
        <button className={"gnav-side" + (side.accent ? " accent" : "")} aria-label={side.label} onClick={() => { haptic("light"); side.onClick(); }}>
          <Icon n={side.i} s={21} />
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
