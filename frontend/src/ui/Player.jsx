import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";

let current = null; // only one track plays at a time
const fmt = (s) => (isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00");

export default function Player({ src, title, sub, cover, onMore }) {
  const a = useRef(null);
  const [on, setOn] = useState(false);
  const [t, setT] = useState(0);
  const [d, setD] = useState(0);
  useEffect(() => () => { if (current === a.current) current = null; }, []);
  const toggle = () => {
    const el = a.current; if (!el) return;
    if (el.paused) { if (current && current !== el) current.pause(); current = el; el.play().catch(() => {}); } else el.pause();
  };
  const seek = (e) => {
    const el = a.current; if (!el || !d) return;
    const r = e.currentTarget.getBoundingClientRect();
    el.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * d;
  };
  return (
    <div className="player">
      <span className="pl-cover" style={cover ? { backgroundImage: `url(${cover})` } : undefined}>{!cover && <Icon n="music" s={18} />}</span>
      <div className="pl-main">
        <div className="pl-t"><b>{title}</b>{sub && <small>{sub}</small>}</div>
        <div className="pl-bar" onClick={seek} role="slider" aria-label="Позиция" aria-valuemin={0} aria-valuemax={Math.round(d)} aria-valuenow={Math.round(t)}>
          <i style={{ width: d ? `${(t / d) * 100}%` : 0 }} />
        </div>
        <div className="pl-time"><span>{fmt(t)}</span><span>{fmt(d)}</span></div>
      </div>
      <button className="pl-play" aria-label={on ? "Пауза" : "Слушать"} onClick={toggle}><Icon n={on ? "pause" : "play"} s={18} /></button>
      {onMore && <button className="ic-btn plain" aria-label="Действия" onClick={onMore}><Icon n="more" s={18} /></button>}
      <audio ref={a} src={src} preload="metadata" onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => setOn(false)}
        onTimeUpdate={(e) => setT(e.currentTarget.currentTime)} onLoadedMetadata={(e) => setD(e.currentTarget.duration)} />
    </div>);
}
