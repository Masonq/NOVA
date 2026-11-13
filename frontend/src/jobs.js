import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { haptic } from "./tg.js";
import { toast } from "./ui/Toast.jsx";

export const PRICE = { image: 40, video_std_s: 24, video_pro_s: 36, video_sound_k: 1.5, music: 30, tts_1k: 5, tts_min: 2 };
/** Prices can change from the admin panel: refresh them when the app starts. */
export const loadPrices = () => api("/api/me/config").then((c) => Object.assign(PRICE, c.price)).catch(() => {});
export function priceOf(kind, p = {}, text = "") {
  if (kind === "image") return PRICE.image;
  if (kind === "music") return PRICE.music;
  if (kind === "tts") return Math.max(PRICE.tts_min, Math.ceil((text.length / 1000) * PRICE.tts_1k));
  const per = p.quality === "1080p" ? PRICE.video_pro_s : PRICE.video_std_s;
  return Math.ceil(((p.duration || 5) * per * (p.sound ? PRICE.video_sound_k : 1)) / 5) * 5;
}
export const KIND = { image: "Фото", video: "Видео", music: "Трек", tts: "Озвучка" };

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
