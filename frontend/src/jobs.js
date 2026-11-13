import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { haptic } from "./tg.js";
import { toast } from "./ui/Toast.jsx";

export const PRICE = { image: 12, image_edit: 18, image_hq: 18, agent_min: 5, agent_search: 3, chat_msg: 1, video_std_s: 24, video_pro_s: 36, video_sound_k: 1.5, music: 30, tts_1k: 5, tts_min: 2 };
/** Prices can change from the admin panel: refresh them when the app starts. */
export const loadPrices = () => api("/api/me/config").then((c) => Object.assign(PRICE, c.price)).catch(() => {});
export function priceOf(kind, p = {}, text = "") {
  if (kind === "image") return (p.refs?.length ? PRICE.image_edit : PRICE.image) + (p.hq ? PRICE.image_hq : 0);
  if (kind === "music") return PRICE.music + (p.voice_chars ? Math.max(PRICE.tts_min, Math.ceil((p.voice_chars / 1000) * PRICE.tts_1k)) : 0);
  if (kind === "tts") { const spoken = text.replace(/^\s*\[[^\]]{1,82}\]\s*$/gm, "").trim(); return Math.max(PRICE.tts_min, Math.ceil((spoken.length / 1000) * PRICE.tts_1k)); }
  const per = p.quality === "1080p" ? PRICE.video_pro_s : PRICE.video_std_s;
  return Math.ceil(((p.duration || 5) * per * (p.sound ? PRICE.video_sound_k : 1)) / 5) * 5;
}
export const KIND = { image: "Фото", video: "Видео", music: "Трек", tts: "Озвучка", clip: "Клип", reel: "Ролик", greeting: "Поздравление" };

/** Global poller for running generations. */
const listeners = new Set();
let active = [];
let timer = null;
async function tick() {
  try {
    const prev = active;
    active = await api("/api/jobs/active");
    const gone = prev.filter((p) => !active.find((a) => a.id === p.id));
    for (const g of gone) {
      const j = await api(`/api/jobs/${g.id}`).catch(() => null);
      if (j?.status === "done") { haptic("success"); toast(`Готово: ${KIND[j.kind].toLowerCase()}`); }
      else if (j?.status === "failed") { haptic("error"); toast("Не получилось — кредиты вернулись на баланс", "error"); }
      listeners.forEach((l) => l({ finished: j }));
    }
    listeners.forEach((l) => l({ active }));
  } catch {}
  timer = setTimeout(tick, active.length ? 2500 : 8000);
}
export function kickJobs() { clearTimeout(timer); tick(); }
export function useActiveJobs(onFinished) {
  const [list, setList] = useState(active);
  const cb = useRef(onFinished); cb.current = onFinished;
  useEffect(() => {
    const l = (e) => { if (e.active) setList(e.active); if (e.finished && cb.current) cb.current(e.finished); };
    listeners.add(l);
    if (!timer) tick();
    return () => listeners.delete(l);
  }, []);
  return list;
}

export async function startJob(kind, prompt, params) {
  const j = await api("/api/jobs", { method: "POST", body: { kind, prompt, params } });
  haptic("medium");
  kickJobs();
  return j;
}

export function thumbOf(j) {
  const f = j.files || [];
  const im = f.find((x) => x.type === "thumb") || f.find((x) => x.type === "image");
  if (im) return im.thumb_url || im.url;
  return f.find((x) => x.cover_url)?.cover_url || null;
}


/** «[Куплет 1: мужской]» marks in lyrics, the same rules as the server. */
export function parseSections(text) {
  const re = /^\s*\[([^\]:]{1,40})(?::\s*([^\]]{1,40}))?\]\s*$/;
  const out = [];
  for (const line of (text || "").split("\n")) {
    const m = line.match(re);
    if (m) out.push({ label: m[1].trim(), who: whoOf(m[2] || m[1]) });
  }
  return out;
}
function whoOf(spec) {
  const t = (spec || "").toLowerCase();
  if (/дуэт|вместе|оба|duet|both/.test(t)) return "duet";
  if (/жен|female/.test(t)) return "female";
  if (/муж|male/.test(t)) return "male";
  return "";
}
export const WHO_RU = { male: "мужской", female: "женский", duet: "дуэт", "": "без пометки" };


/** Title, meta line and description for a work's card. Section marks like «[Куплет 1: мужской]» are not shown. */
export function cardText(j) {
  const clean = (j.prompt || "").replace(/^\s*\[[^\]]{1,82}\]\s*$/gm, "").replace(/\s+/g, " ").trim();
  const p = j.params || {};
  const track = (j.files || []).find((f) => f.title)?.title;
  const date = j.at ? new Date(j.at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "";
  const meta = {
    image: [p.style || "Картинка"], video: ["Видео", `${p.duration || 5} с`],
    music: ["Трек", p.genre], tts: ["Озвучка", p.male && p.female ? `${p.male} и ${p.female}` : p.voice],
  }[j.kind] || [KIND[j.kind]];
  const lines = (j.prompt || "").split("\n").filter((l) => l.trim() && !/^\s*\[[^\]]{1,82}\]\s*$/.test(l));
  const first = (lines[0] || "").trim().split(/(?<=[.!?…])\s/)[0];      // a lyric's first line, or the first sentence
  const cut = first.length > 60 ? first.slice(0, 60).replace(/\s+\S*$/, "") + "…" : first;   // on a word boundary
  const title = track || cut || KIND[j.kind] || "Работа";
  // the rest when the title is a whole sentence, the full text when it was shortened: never the title twice, never half a word
  const desc = (track ? clean : cut === first ? clean.slice(first.length) : clean).trim();
  return { title, sub: [...meta, date].filter(Boolean).join(" · "), desc };
}
