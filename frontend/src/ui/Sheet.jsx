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

export default function Sheet({ open, onClose, children, title }) {
  useEffect(() => {
    if (!open) return;
    const close = () => onClose();
    pushBack(close);
    const prev = document.body.style.overflow; document.body.style.overflow = "hidden";
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => { popBack(close); document.body.style.overflow = prev; window.removeEventListener("keydown", esc); };
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
  const f = file || job.files?.[0];
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
        <span className="sr-t"><b>{job.prompt.slice(0, 48)}</b><small>{{ image: "Картинка", video: "Видео", music: "Трек", tts: "Озвучка" }[job.kind]}</small></span>
        <button className={"ic-btn fav" + (job.favorite ? " on" : "")} aria-label={job.favorite ? "Убрать из избранного" : "В избранное"} onClick={fav}><Icon n="heart" /></button>
      </div>
      {f && job.kind === "image" && <img className="sheet-media" src={f.url} alt={job.prompt} />}
      {f && job.kind === "video" && <video className="sheet-media" src={f.url} poster={thumbOf(job) || undefined} controls playsInline preload="metadata" />}
      {f && (job.kind === "music" || job.kind === "tts") && <Player src={f.url} title={f.title || job.prompt.slice(0, 40)} sub={job.kind === "tts" ? job.params?.voice : job.params?.genre} cover={f.cover_url || null} />}
      {job.kind === "music" && job.params?.brief?.lyrics && (
        <details className="lyrics"><summary>Текст песни</summary><pre>{job.params.brief.lyrics}</pre></details>)}
      {f && <Row ic="download" t="Скачать" on={() => saveFile(f.url, name)} />}
      {f && <Row ic="share" t="Поделиться" sub="страница с превью для Telegram и соцсетей" on={() => shareJob(job)} />}
      {job.kind === "image" && f && <Row ic="video" t="Оживить в видео" sub="картинка станет первым кадром" cls="accent" on={() => { onClose(); go("video", { image: f.url }); }} />}
      {job.kind === "tts" && f && <Row ic="music" t="Сделать трек из этой озвучки" sub="тем же голосом и с этим текстом" cls="accent"
        on={() => { onClose(); go("music", { voice_job: job.id, voice_text: job.prompt, voice: job.params?.voice }); }} />}
      {job.kind !== "tts" && <Row ic="spark" t="Сделать похожее" on={() => { onClose(); go(job.kind, { prompt: job.prompt }); }} />}
      <Row ic="trash" t="Удалить" cls="danger" on={del} />
    </Sheet>);
}
