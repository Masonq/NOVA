import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { tg, haptic, pushBack, popBack } from "../tg.js";
import { toast } from "./Toast.jsx";
import { api } from "../api.js";
import Player from "./Player.jsx";
import { thumbOf, cardText, PRICE } from "../jobs.js";

export function saveFile(url, name) {
  try { if (tg?.downloadFile) { tg.downloadFile({ url, file_name: name }); return; } } catch {}
  const a = document.createElement("a"); a.href = url; a.download = name; a.target = "_blank"; a.rel = "noopener"; a.click();
}
/** Shares a public page of the work (rich preview in Telegram) instead of a raw file link. */
export async function shareJob(job) {
  let r;
  try { r = await api(`/api/jobs/${job.id}/share`, { method: "POST" }); } catch (e) { toast(e.message, "error"); return; }
  if (tg?.openTelegramLink && tg.initData) {
    tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(r.url)}&text=${encodeURIComponent(r.text)}`); return;
  }
  try { if (navigator.share) { await navigator.share({ url: r.url, text: r.text }); return; } } catch (e) { if (e?.name === "AbortError") return; }
  try { await navigator.clipboard.writeText(r.url); toast("Ссылка скопирована"); } catch { toast(r.url); }
}

const open_sheets = { n: 0 };

/* Scroll lock while a sheet is open, without touching the page's styles (style changes made iOS repaint and flash):
   only the sheet scrolls; at its top/bottom the gesture is stopped instead of passing to the page behind;
   horizontal strips inside the sheet keep scrolling sideways. */
let touch = null;
function scroller(el, axis) {
  for (; el && el !== document.body; el = el.parentElement) {
    const st = getComputedStyle(el);
    if (axis === "x" && /(auto|scroll)/.test(st.overflowX) && el.scrollWidth > el.clientWidth + 1) return el;
    if (axis === "y" && /(auto|scroll)/.test(st.overflowY) && el.scrollHeight > el.clientHeight + 1) return el;
    if (el.classList?.contains("sheet")) return null;            // never look past the sheet
  }
  return null;
}
function blocked(target, dx, dy) {
  const sheet = target.closest?.(".sheet");
  if (!sheet) return true;                                   // the dim layer or anything behind it
  if (Math.abs(dx) > Math.abs(dy)) return !scroller(target, "x");
  const el = scroller(target, "y") || (sheet.scrollHeight > sheet.clientHeight + 1 ? sheet : null);
  if (!el) return true;                                      // a short sheet has nothing to scroll
  const top = el.scrollTop <= 0, bottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
  return (dy > 0 && top) || (dy < 0 && bottom);              // at the edge: don't chain the scroll to the page
}
const onStart = (e) => { const t = e.touches[0]; touch = { x: t.clientX, y: t.clientY }; };
const onMove = (e) => {
  if (!touch || e.touches.length > 1) return;
  const t = e.touches[0];
  if (blocked(e.target, t.clientX - touch.x, t.clientY - touch.y) && e.cancelable) e.preventDefault();
};
const onWheel = (e) => { if (blocked(e.target, -e.deltaX, -e.deltaY) && e.cancelable) e.preventDefault(); };
function lock(on) {
  const f = on ? "addEventListener" : "removeEventListener";
  document[f]("touchstart", onStart, { passive: true });
  document[f]("touchmove", onMove, { passive: false });
  document[f]("wheel", onWheel, { passive: false });
}

export default function Sheet({ open, onClose, children, title }) {
  useEffect(() => {
    if (!open) return;
    const close = () => onClose();
    pushBack(close);
    // no body.style changes here: they make the iOS web view repaint the whole document; a class + CSS is enough
    const root = document.documentElement;
    open_sheets.n += 1; root.classList.add("sheet-open");
    if (open_sheets.n === 1) lock(true);
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => {
      popBack(close); window.removeEventListener("keydown", esc);
      open_sheets.n = Math.max(0, open_sheets.n - 1);
      if (!open_sheets.n) { root.classList.remove("sheet-open"); lock(false); }
    };
  }, [open]);
  // mount in the start state, switch to «in» on the next frames: no late-starting animation can flash the final state first
  const [inn, setIn] = useState(false);
  useEffect(() => {
    if (!open) { setIn(false); return; }
    let a = requestAnimationFrame(() => { a = requestAnimationFrame(() => setIn(true)); });
    return () => cancelAnimationFrame(a);
  }, [open]);
  // swipe down to close: the sheet follows the finger, the dim fades with it; far or fast enough → it slides away
  const box = useRef(null), wrap = useRef(null), g = useRef(null);
  const start = (y, x, fromGrab) => {
    const el = box.current; if (!el) return;
    g.current = { y, x, t: Date.now(), dy: 0, on: false, ok: fromGrab || el.scrollTop <= 0, axis: null };
  };
  const drag = (y, x) => {
    const s = g.current, el = box.current; if (!s || !el || !s.ok) return;
    const dy = y - s.y, dx = x - s.x;
    if (!s.axis && (Math.abs(dy) > 6 || Math.abs(dx) > 6)) s.axis = Math.abs(dy) > Math.abs(dx) ? "y" : "x";
    if (s.axis !== "y") return;
    if (!s.on && dy > 0 && el.scrollTop <= 0) { s.on = true; s.y0 = y; el.style.transition = "none"; wrap.current.style.transition = "none"; }
    if (!s.on) return;
    s.dy = Math.max(0, y - s.y0);
    const now = Date.now(); s.trail = [...(s.trail || []).filter((p) => now - p[0] < 100), [now, s.dy]];   // last 100 ms
    el.style.transform = `translateY(${s.dy}px)`;
    wrap.current.style.backgroundColor = `rgba(0,0,0,${0.55 * Math.max(0, 1 - s.dy / el.offsetHeight)})`;
  };
  const end = () => {
    const s = g.current, el = box.current, w = wrap.current; g.current = null;
    if (!s || !s.on || !el) return;
    const tr = s.trail || [], a = tr[0], z = tr[tr.length - 1];
    const fast = a && z && z[0] > a[0] ? (z[1] - a[1]) / (z[0] - a[0]) > 0.5 : false;      // a flick: speed of the last moves
    el.style.transition = w.style.transition = "";
    if (s.dy > Math.min(140, el.offsetHeight * 0.28) || (fast && s.dy > 30)) {
      el.style.transform = "translateY(100%)"; w.style.backgroundColor = "rgba(0,0,0,0)";
      haptic("light"); setTimeout(onClose, 230);
    } else { el.style.transform = ""; w.style.backgroundColor = ""; }
  };
  const mouseGrab = (e) => {
    start(e.clientY, e.clientX, true);
    const mv = (ev) => drag(ev.clientY, ev.clientX);
    const up = () => { end(); window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
  };
  if (!open) return null;
  return (
    <div ref={wrap} className={"sheet-wrap" + (inn ? " in" : "")} onClick={onClose}>
      <div ref={box} className="sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}
        onTouchStart={(e) => start(e.touches[0].clientY, e.touches[0].clientX, !!e.target.closest?.(".grab-zone"))}
        onTouchMove={(e) => drag(e.touches[0].clientY, e.touches[0].clientX)} onTouchEnd={end} onTouchCancel={end}>
        <span className="grab-zone" onPointerDown={(e) => e.pointerType === "mouse" && mouseGrab(e)} aria-hidden="true"><span className="grab" /></span>
        {children}
      </div>
    </div>);
}

/* A row of the action sheet. Declared at module level: a component created inside another one is a new type on every
   render, so React would remount the rows (and replay their entrance animation) each time the parent refreshes. */
function Row({ ic, t, sub, on, cls }) {
  return (
    <button className={"sheet-row " + (cls || "")} onClick={on}>
      <span className="sr-ic"><Icon n={ic} /></span>
      <span className="sr-t"><span>{t}</span>{sub && <small>{sub}</small>}</span>
      <Icon n="chevron" s={15} />
    </button>);
}

export function JobSheet({ job, file, onClose, go, onChange, onArtist }) {
  if (!job) return null;
  return <JobSheetIn key={job.id} {...{ job, file, onClose, go, onChange, onArtist }} />;
}

function JobSheetIn({ job, file, onClose, go, onChange, onArtist }) {
  const [naming, setNaming] = useState(false);
  const [aname, setAname] = useState("");
  const [saving, setSaving] = useState(false);
  const canArtist = job.kind === "music" && job.status === "done" && job.params?.instrumental === false && !job.params?.voice_job;
  const saveArtist = async () => {
    const n = aname.trim(); if (!n || saving) return;
    setSaving(true);
    try {
      const a = await api("/api/artists", { method: "POST", body: { job_id: job.id, name: n } });
      haptic("success"); toast(`Исполнитель «${a.name}» сохранён`);
      onClose();
      if (onArtist) onArtist(a); else go("music", { artist: a.id });
    } catch (er) { toast(er.message, "error"); setSaving(false); }
  };
  const combo = ["clip", "reel", "greeting"].includes(job.kind);      // older works of removed kinds still open
  const f = combo ? (job.files || []).find((x) => x.type === "video") || job.files?.[0] : file || job.files?.[0];
  const ext = (f?.url || "").split(".").pop();
  const name = `nova-${job.kind}-${job.id}.${ext}`;
  const fav = async () => { const r = await api(`/api/jobs/${job.id}/favorite`, { method: "POST" }); onChange?.({ ...job, favorite: r.favorite }); };
  const del = async () => {
    if (!window.confirm("Удалить эту работу?")) return;
    await api(`/api/jobs/${job.id}`, { method: "DELETE" }); toast("Удалено"); onChange?.(null); onClose();
  };
  return (
    <Sheet open={!!job} onClose={onClose} title="Действия">
      <div className="sheet-head">
        <span className={"sh-thumb k-" + job.kind} style={thumbOf(job) ? { backgroundImage: `url(${thumbOf(job)})` } : undefined} />
        <span className="sr-t"><b>{cardText(job).title}</b><small>{{ image: "Картинка", video: "Видео", music: "Трек", tts: "Озвучка", clip: "Клип", reel: "Ролик", greeting: "Поздравление" }[job.kind]}</small></span>
        <button className={"ic-btn fav" + (job.favorite ? " on" : "")} aria-label={job.favorite ? "Убрать из избранного" : "В избранное"} onClick={fav}><Icon n="heart" /></button>
      </div>
      {f && job.kind === "image" && <img className="sheet-media" src={f.url} alt={job.prompt} />}
      {f && (job.kind === "video" || (combo && f.type === "video")) && <video className="sheet-media" src={f.url} poster={thumbOf(job) || undefined} controls playsInline preload="metadata" />}
      {f && (job.kind === "music" || job.kind === "tts") && <Player src={f.url} title={f.title || job.prompt.slice(0, 40)} sub={job.kind === "tts" ? job.params?.voice : job.params?.genre} cover={f.cover_url || null} />}
      {job.kind === "music" && job.params?.brief?.lyrics && (
        <details className="lyrics"><summary>Текст песни</summary><pre>{job.params.brief.lyrics}</pre></details>)}
      {f && <Row ic="download" t="Скачать" on={() => saveFile(f.url, name)} />}
      {f && <Row ic="share" t="Поделиться" sub="страница с превью для Telegram и соцсетей" on={() => shareJob(job)} />}
      {job.kind === "image" && f && <Row ic="video" t="Оживить в видео" sub="картинка станет первым кадром" cls="accent" on={() => { onClose(); go("video", { image: f.url }); }} />}
      {job.kind === "tts" && f && <Row ic="music" t="Сделать трек из этой озвучки" sub="тем же голосом и с этим текстом" cls="accent"
        on={() => { onClose(); go("music", { voice_job: job.id, voice_text: job.prompt, voice: job.params?.voice }); }} />}
      {canArtist && !naming && <Row ic="user" t="Сохранить исполнителя" sub={`этот голос будет петь ваши новые песни · ${PRICE.artist ?? 10} кр.`}
        on={() => { haptic("select"); setNaming(true); }} />}
      {canArtist && naming && (
        <div className="art-form">
          <label className="opts-h" htmlFor="art-name"><span>Имя исполнителя</span><small>{PRICE.artist ?? 10} кр.</small></label>
          <div className="art-row">
            <input id="art-name" autoFocus value={aname} maxLength={40} placeholder="Например: Ночной Макс" onChange={(e) => setAname(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveArtist()} />
            <button className="cta" disabled={!aname.trim() || saving} onClick={saveArtist}>{saving ? "…" : "Сохранить"}</button>
          </div>
        </div>)}
      {job.kind === "music" && job.params?.artist && <Row ic="music" t={`Ещё песня: ${job.params.artist_name || "этот исполнитель"}`} sub="тот же голос, новая песня"
        on={() => { onClose(); go("music", { artist: job.params.artist }); }} />}
      {!["tts", "clip", "reel", "greeting"].includes(job.kind) && <Row ic="spark" t="Сделать похожее" on={() => { onClose(); go(job.kind, { prompt: job.prompt }); }} />}
      <Row ic="trash" t="Удалить" cls="danger" on={del} />
    </Sheet>);
}
