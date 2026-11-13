import { useEffect, useRef, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { api } from "../api.js";
import { thumbOf } from "../jobs.js";

/** Full-screen vertical feed of your own pictures and videos. */
export default function Feed({ go }) {
  const [items, setItems] = useState(null);
  const [sheet, setSheet] = useState(null);
  const box = useRef(null);
  useEffect(() => {
    api("/api/jobs?limit=60").then((r) => setItems(r.filter((j) => j.status === "done" && (j.kind === "image" || j.files?.some((f) => f.type === "video"))).flatMap((j) =>
      j.kind === "image" ? j.files.filter((f) => f.type === "image").slice(0, 1).map((f) => ({ j, f })) : [{ j, f: j.files.find((f) => f.type === "video") }]))).catch(() => setItems([]));
  }, []);
  useEffect(() => {
    const el = box.current; if (!el) return;
    const io = new IntersectionObserver((es) => es.forEach((e) => { const v = e.target.querySelector("video"); if (v) e.isIntersecting ? v.play().catch(() => {}) : v.pause(); }), { root: el, threshold: 0.6 });
    el.querySelectorAll(".slide").forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [items]);
  return (
    <main className="feed" ref={box}>
      <button className="ic-btn back-btn feed-back" aria-label="Назад" onClick={() => go("archive")}><Icon n="back" /></button>
      {items?.length === 0 && <div className="empty-state"><p>Лента пустая</p><span className="muted small">Здесь будут ваши картинки и видео</span></div>}
      {items?.map(({ j, f }) => f && (
        <section key={f.url} className="slide">
          {f.type === "video"
            ? <video src={f.url} poster={thumbOf(j) || undefined} loop playsInline muted preload="metadata" />
            : <img src={f.url} alt={j.prompt} loading="lazy" />}
          <div className="slide-cap"><p>{j.prompt}</p></div>
          <button className="ic-btn slide-more" aria-label="Действия" onClick={() => setSheet({ j, f })}><Icon n="more" /></button>
        </section>))}
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go} onChange={() => {}} />
    </main>);
}
