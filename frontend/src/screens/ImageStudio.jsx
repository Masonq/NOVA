import { useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { useStudio } from "../studio.js";
import { priceOf, PRICE } from "../jobs.js";
import Carousel from "../ui/Carousel.jsx";

const STYLES = ["Фото", "Арт", "Логотип", "3D", "Аниме"];
const ASPECTS = [{ v: "1:1", t: "1:1" }, { v: "3:4", t: "3:4" }, { v: "9:16", t: "9:16" }, { v: "16:9", t: "16:9" }];
const ratio = (a) => { const [w, h] = a.split(":").map(Number); return `${w} / ${h}`; };

export default function ImageStudio({ go, me, reloadMe, params }) {
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [style, setStyle] = useState(params?.style || "Фото");
  const [aspect, setAspect] = useState("1:1");
  const [hq, setHq] = useState(() => localStorage.getItem("nova_img_hq") === "1");
  const pickHq = (v) => { setHq(v); localStorage.setItem("nova_img_hq", v ? "1" : "0"); };

  const [ref, setRef] = useState(null);
  const [sheet, setSheet] = useState(null);
  const s = useStudio("image", reloadMe);
  const cur = s.current;
  const first = (j) => (j?.files || []).find((f) => f.type === "image");
  const gallery = [cur, ...s.recent.filter((j) => j.id !== cur?.id)].filter((j) => first(j)).slice(0, 12).map((j) => ({ j, f: first(j) }));
  return (
    <main className="screen studio">
      <StudioTop title="Фото" me={me} go={go} />
      <PromptBox value={prompt} onChange={setPrompt} max={1200} placeholder="Опишите картинку: что, где, какое настроение"
        attach={ref} onAttach={setRef} attachLabel="Своё фото" />
      {ref && <p className="muted small pad">Нейросеть изменит ваше фото по описанию</p>}
      <Opts label="Стиль" value={style} options={STYLES} onChange={setStyle}
        hint={hq ? "GPT Image 2.6 · high" : ref ? "Nano Banana 2.1 · 2K" : style === "Логотип" ? "GPT Image 2.6" : "Seedream 5.5 · 2K"} />
      <Opts label="Формат" value={aspect} options={ASPECTS} onChange={setAspect} />
      <Toggle label="Высокое качество" sub={`как в ChatGPT: точнее текст и детали · +${PRICE.image_hq} кр.`} on={hq} onChange={pickHq} />

      {s.active ? (
        <section className="reveal" style={{ aspectRatio: ratio(s.active.params?.aspect || aspect) }} aria-label="Идёт генерация">
          <div className="reveal-fill" style={{ height: `${s.active.progress}%` }} />
          <div className="reveal-cap"><Progress job={s.active} /></div>
        </section>
      ) : gallery.length > 0 && (
        <section aria-label="Ваши картинки">
          <Carousel key={cur?.id} label="Ваши картинки" height={400} items={gallery.map(({ j, f }) => ({
            key: f.url, img: f.thumb_url || f.url, title: j.prompt,
            sub: `${j.params?.style || "Фото"} · ${new Date(j.at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}`,
            onOpen: () => setSheet({ j, f }), onMore: () => setSheet({ j, f }),
          }))} />
        </section>)}

      <Dock label="Создать" price={priceOf("image", { refs: ref ? [ref] : [], hq })} balance={me?.balance} busy={s.busy}
        disabled={prompt.trim().length < 2 || !!s.active}
        onClick={() => s.run(prompt.trim(), { style, aspect, hq, refs: ref ? [ref] : [] })} />
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go}
        onChange={(j) => { setSheet(null); s.reload(); if (!j) s.setCurrent(null); }} />
    </main>);
}
