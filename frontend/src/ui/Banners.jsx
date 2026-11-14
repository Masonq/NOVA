import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import Art3D from "./Art3D.jsx";
import { haptic } from "../tg.js";

const KEY = "nova_banners_hidden";
const hiddenSet = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || "[]")); } catch { return new Set(); } };

/** Swipeable promo cards (like Walt): a 3D picture on the right, dots, ✕ hides a card for good; they turn by themselves
 *  every few seconds and pause while the finger is on them. items: [{ id, title, sub, art, bg, onClick }] */
export default function Banners({ items }) {
  const [hidden, setHidden] = useState(hiddenSet);
  const list = items.filter((b) => !hidden.has(b.id));
  const row = useRef(null), touching = useRef(false);
  const [idx, setIdx] = useState(0);
  const onScroll = () => {
    const el = row.current; if (!el) return;
    const i = Math.round(el.scrollLeft / el.clientWidth);
    if (i !== idx) setIdx(i);
  };
  useEffect(() => {
    if (list.length < 2 || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => {
      const el = row.current; if (!el || touching.current || document.hidden) return;
      const next = (Math.round(el.scrollLeft / el.clientWidth) + 1) % list.length;
      el.scrollTo({ left: next * el.clientWidth, behavior: "smooth" });
    }, 5000);
    return () => clearInterval(t);
  }, [list.length]);
  if (!list.length) return null;
  const hide = (id) => {
    haptic("light");
    const s = new Set(hidden); s.add(id); setHidden(s);
    try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch {}
  };
  return (
    <section className="banners" aria-label="Новое в NOVA">
      <div className="bn-row" ref={row} onScroll={onScroll}
        onTouchStart={() => { touching.current = true; }} onTouchEnd={() => { setTimeout(() => { touching.current = false; }, 1500); }}>
        {list.map((b) => (
          <div key={b.id} className="bn" style={{ background: b.bg }} role="button" tabIndex={0}
            onClick={() => { haptic("light"); b.onClick?.(); }} onKeyDown={(e) => e.key === "Enter" && b.onClick?.()}>
            <span className="bn-t"><b>{b.title}</b><small>{b.sub} ›</small></span>
            <Art3D name={b.art} size={92} className="bn-art" />
            <button className="bn-x" aria-label="Скрыть" onClick={(e) => { e.stopPropagation(); hide(b.id); }}><Icon n="x" s={11} w={2.6} /></button>
          </div>))}
      </div>
      {list.length > 1 && <div className="bn-dots" aria-hidden="true">{list.map((b, i) => <i key={b.id} className={i === idx ? "on" : ""} />)}</div>}
    </section>);
}
