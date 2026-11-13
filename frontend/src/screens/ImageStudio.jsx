import { useState } from "react";
import { StudioTop, PromptBox, Dock, Progress } from "../ui/Studio.jsx";
import { Tiles, AspectPicker, FeatureToggle, Glow, Ideas } from "../ui/Creative.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { useStudio } from "../studio.js";
import { priceOf, PRICE, cardText } from "../jobs.js";
import Carousel from "../ui/Carousel.jsx";

const STYLES = [
  { v: "Фото", t: "Фото", a: "#4FA3FF", b: "#0B2342", m: "aperture" },
  { v: "Арт", t: "Арт", a: "#FF7A59", b: "#3B1020", m: "brush" },
  { v: "Логотип", t: "Логотип", a: "#F5C343", b: "#2B2206", m: "hex" },
  { v: "3D", t: "3D", a: "#7C6CFF", b: "#18113F", m: "cube" },
  { v: "Аниме", t: "Аниме", a: "#FF6FB5", b: "#3A0F2E", m: "sparkle" },
];
const ASPECTS = [{ v: "1:1", t: "Квадрат", use: "аватар, пост" }, { v: "3:4", t: "Портрет", use: "пост в ленту" },
  { v: "9:16", t: "Сторис", use: "сторис, обои на телефон" }, { v: "16:9", t: "Экран", use: "обложка, обои на компьютер" }];
const IDEAS = {
  "Фото": ["Кофейня на рассвете, мягкий свет", "Портрет в неоновом дожде", "Белград с высоты на закате"],
  "Арт": ["Кит летит над ночным городом, акварель", "Лиса в осеннем лесу, масло", "Галактика в стеклянной банке"],
  "Логотип": ["Логотип кофейни «Зерно», минимализм", "Значок фитнес-приложения", "Монограмма N, золото на чёрном"],
  "3D": ["Милый робот-курьер с посылкой", "Парящий остров с водопадом", "Домик из конфет, мягкий свет"],
  "Аниме": ["Девушка на крыше под звёздами", "Самурай под сакурой", "Уютная комната в дождь"],
};
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
    <main className="screen studio mus">
      <Glow color={STYLES.find((x) => x.v === style)?.a} />
      <StudioTop title="Фото" me={me} go={go} />
      <PromptBox value={prompt} onChange={setPrompt} max={1200} placeholder="Опишите картинку: что, где, какое настроение"
        attach={ref} onAttach={setRef} attachLabel="Своё фото" />
      {ref ? <p className="muted small pad">Нейросеть изменит ваше фото по описанию</p>
        : !prompt.trim() && <Ideas items={IDEAS[style]} onPick={setPrompt} />}
      <Tiles label="Стиль" items={STYLES} value={style} onChange={setStyle} grid
        hint={hq ? "GPT Image 2.6 · high" : ref ? "Nano Banana 2.1 · 2K" : style === "Логотип" ? "GPT Image 2.6" : "Seedream 5.5 · 2K"} />
      <AspectPicker value={aspect} onChange={setAspect} items={ASPECTS} />
      <FeatureToggle on={hq} onChange={pickHq} tone="gold" icon="spark" title="Высокое качество"
        sub={`точнее текст и детали · +${PRICE.image_hq} кр.`} subOn={`GPT Image 2.6 high · +${PRICE.image_hq} кр.`} />

      {s.active ? (
        <section className="reveal" style={{ aspectRatio: ratio(s.active.params?.aspect || aspect) }} aria-label="Идёт генерация">
          <div className="reveal-fill" style={{ height: `${s.active.progress}%` }} />
          <div className="reveal-cap"><Progress job={s.active} /></div>
        </section>
      ) : gallery.length > 0 && (
        <section aria-label="Ваши картинки">
          <Carousel key={cur?.id} label="Ваши картинки" height={400} items={gallery.map(({ j, f }) => ({
            key: f.url, img: f.thumb_url || f.url, ...cardText(j),
            onOpen: () => setSheet({ j, f }), onMore: () => setSheet({ j, f }),
          }))} />
        </section>)}

      <Dock job={s.active} label="Создать" price={priceOf("image", { refs: ref ? [ref] : [], hq })} balance={me?.balance} busy={s.busy}
        disabled={prompt.trim().length < 2 || !!s.active}
        onClick={() => s.run(prompt.trim(), { style, aspect, hq, refs: ref ? [ref] : [] })} />
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go}
        onChange={(j) => { setSheet(null); s.reload(); if (!j) s.setCurrent(null); }} />
    </main>);
}
