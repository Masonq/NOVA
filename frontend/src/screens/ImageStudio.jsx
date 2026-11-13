import { useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { useStudio } from "../studio.js";
import { priceOf } from "../jobs.js";
import Carousel from "../ui/Carousel.jsx";

const STYLES = ["Фото", "Арт", "Логотип", "3D", "Аниме"];
const ASPECTS = [{ v: "1:1", t: "1:1" }, { v: "3:4", t: "3:4" }, { v: "9:16", t: "9:16" }, { v: "16:9", t: "16:9" }];
const ratio = (a) => { const [w, h] = a.split(":").map(Number); return `${w} / ${h}`; };

export default function ImageStudio({ go, me, reloadMe, params }) {
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [style, setStyle] = useState(params?.style || "Фото");
  const [aspect, setAspect] = useState("1:1");
  const [ref, setRef] = useState(null);
  const [sel, setSel] = useState(0);
  const [sheet, setSheet] = useState(null);
  const s = useStudio("image", reloadMe);
  const cur = s.current;
  const imgs = (cur?.files || []).filter((f) => f.type === "image");
  const pa = cur?.params?.aspect || "1:1";
  return (
    <main className="screen studio">
      <StudioTop title="Фото" me={me} go={go} />
      <PromptBox value={prompt} onChange={setPrompt} max={1200} placeholder="Опишите картинку: что, где, какое настроение"
        attach={ref} onAttach={setRef} attachLabel="Своё фото" />
      {ref && <p className="muted small pad">Нейросеть изменит ваше фото по описанию</p>}
      <Opts label="Стиль" value={style} options={STYLES} onChange={setStyle} />
      <Opts label="Формат" value={aspect} options={ASPECTS} onChange={setAspect} />

      {s.active ? (
        <section className="reveal" style={{ aspectRatio: ratio(s.active.params?.aspect || aspect) }} aria-label="Идёт генерация">
          <div className="reveal-fill" style={{ height: `${s.active.progress}%` }} />
          <div className="reveal-cap"><Progress job={s.active} /></div>
        </section>
      ) : cur && imgs.length > 0 && (
        <section aria-label="Результат">
          <Carousel key={cur.id} label="Варианты" height={imgs.length > 1 ? 400 : 380}
            onChange={setSel} items={imgs.map((f, i) => ({
              key: f.url, img: f.url, title: `Вариант ${i + 1}`, sub: `${cur.params?.style || "Фото"} · ${pa} · ${cur.prompt}`,
              onOpen: () => setSheet(f), onMore: () => setSheet(f),
            }))} />
        </section>)}

      {s.recent.length > 1 && (
        <section aria-labelledby="ri-h">
          <div className="row-h"><h2 id="ri-h">Недавние</h2><button className="link" onClick={() => go("archive", { kind: "image" })}>Все</button></div>
          <div className="recent">{s.recent.slice(0, 10).map((j) => {
            const f = j.files?.find((x) => x.type === "image");
            return <button key={j.id} className="thumb img" style={{ backgroundImage: f ? `url(${f.url})` : undefined }} aria-label={j.prompt}
              onClick={() => { s.setCurrent(j); setSel(0); window.scrollTo({ top: 0, behavior: "smooth" }); }} />;
          })}</div>
        </section>)}
      <Dock label="Создать 4 варианта" price={priceOf("image")} balance={me?.balance} busy={s.busy}
        disabled={prompt.trim().length < 2 || !!s.active}
        onClick={() => s.run(prompt.trim(), { style, aspect, refs: ref ? [ref] : [] })} />
      <JobSheet job={sheet && cur} file={sheet} onClose={() => setSheet(null)} go={go}
        onChange={(j) => { if (!j) { s.setCurrent(null); s.reload(); } else s.setCurrent(j); }} />
    </main>);
}
