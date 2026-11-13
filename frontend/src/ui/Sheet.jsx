import { useEffect } from "react";
import Icon from "./Icon.jsx";
import { tg, pushBack, popBack } from "../tg.js";
import { toast } from "./Toast.jsx";
import { api } from "../api.js";
import Player from "./Player.jsx";
import { thumbOf } from "../jobs.js";

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

export default function Sheet({ open, onClose, children, title }) {
  useEffect(() => {
    if (!open) return;
    const close = () => onClose();
    pushBack(close);
    // no body.style changes here: they make the iOS web view repaint the whole document; a class + CSS is enough
    const root = document.documentElement;
    open_sheets.n += 1; root.classList.add("sheet-open");
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => {
      popBack(close); window.removeEventListener("keydown", esc);
      open_sheets.n = Math.max(0, open_sheets.n - 1);
      if (!open_sheets.n) root.classList.remove("sheet-open");
    };
  }, [open]);
  if (!open) return null;
  return (
    <div className="sheet-wrap" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <span className="grab" aria-hidden="true" />
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

export function JobSheet({ job, file, onClose, go, onChange }) {
  if (!job) return null;
  const combo = ["clip", "reel", "greeting"].includes(job.kind);
  const f = combo ? (job.files || []).find((x) => x.type === "video") || job.files?.[0] : file || job.files?.[0];
  const song = job.kind === "greeting" ? (job.files || []).find((x) => x.type === "audio") : null;
  const card = job.kind === "greeting" ? (job.files || []).find((x) => x.type === "image") : null;
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
        <span className="sr-t"><b>{job.prompt.slice(0, 48)}</b><small>{{ image: "Картинка", video: "Видео", music: "Трек", tts: "Озвучка", clip: "Клип", reel: "Ролик", greeting: "Поздравление" }[job.kind]}</small></span>
        <button className={"ic-btn fav" + (job.favorite ? " on" : "")} aria-label={job.favorite ? "Убрать из избранного" : "В избранное"} onClick={fav}><Icon n="heart" /></button>
      </div>
      {f && job.kind === "image" && <img className="sheet-media" src={f.url} alt={job.prompt} />}
      {f && (job.kind === "video" || (combo && f.type === "video")) && <video className="sheet-media" src={f.url} poster={thumbOf(job) || undefined} controls playsInline preload="metadata" />}
      {f && (job.kind === "music" || job.kind === "tts") && <Player src={f.url} title={f.title || job.prompt.slice(0, 40)} sub={job.kind === "tts" ? job.params?.voice : job.params?.genre} cover={f.cover_url || null} />}
      {card && f?.type === "video" && <img className="sheet-media card-media" src={card.url} alt="Открытка" />}
      {card && f?.type !== "video" && <img className="sheet-media" src={card.url} alt="Открытка" />}
      {song && <Player src={song.url} title={song.title || "Песня"} sub="Песня-поздравление" cover={song.cover_url || null} />}
      {job.kind === "greeting" && job.params?.st?.brief?.lyrics && (
        <details className="lyrics"><summary>Текст песни</summary><pre>{job.params.st.brief.lyrics}</pre></details>)}
      {job.kind === "music" && f && <Row ic="video" t="Сделать клип" sub="сцены по тексту песни, вертикальное видео" cls="accent" on={() => { onClose(); go("clip", { track: job }); }} />}
      {job.kind === "music" && job.params?.brief?.lyrics && (
        <details className="lyrics"><summary>Текст песни</summary><pre>{job.params.brief.lyrics}</pre></details>)}
      {f && <Row ic="download" t="Скачать" on={() => saveFile(f.url, name)} />}
      {f && <Row ic="share" t="Поделиться" sub="страница с превью для Telegram и соцсетей" on={() => shareJob(job)} />}
      {job.kind === "image" && f && <Row ic="video" t="Оживить в видео" sub="картинка станет первым кадром" cls="accent" on={() => { onClose(); go("video", { image: f.url }); }} />}
      {job.kind === "tts" && f && <Row ic="music" t="Сделать трек из этой озвучки" sub="тем же голосом и с этим текстом" cls="accent"
        on={() => { onClose(); go("music", { voice_job: job.id, voice_text: job.prompt, voice: job.params?.voice }); }} />}
      {!["tts", "clip", "greeting"].includes(job.kind) && <Row ic="spark" t="Сделать похожее" on={() => { onClose(); go(job.kind, { prompt: job.prompt }); }} />}
      <Row ic="trash" t="Удалить" cls="danger" on={del} />
    </Sheet>);
}
