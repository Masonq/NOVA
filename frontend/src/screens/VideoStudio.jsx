import { useState } from "react";
import { StudioTop, PromptBox, Dock, Progress } from "../ui/Studio.jsx";
import { AspectPicker, CardChoice, FeatureToggle, Glow, Ideas } from "../ui/Creative.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { useStudio } from "../studio.js";
import { priceOf, thumbOf, PRICE } from "../jobs.js";

const STEPS = [
  { t: "Сценарий", match: ["Сценарий"] }, { t: "Очередь", match: ["В очереди"] },
  { t: "Кадры", match: ["Рисую кадры"] }, { t: "Сборка", match: ["Сборка", "Сохраняю", "Готово"] },
];

const ASPECTS = [{ v: "9:16", t: "Вертикаль", use: "рилс, тикток, сторис" }, { v: "16:9", t: "Горизонт", use: "YouTube, экран" }, { v: "1:1", t: "Квадрат", use: "пост" }];
const IDEAS = ["Камера пролетает над ночным городом", "Кот в очках читает газету в кафе", "Волны разбиваются о скалы, слоу-мо"];
const Strip = ({ n }) => <span className="strip">{Array.from({ length: n }, (_, i) => <i key={i} />)}</span>;

export default function VideoStudio({ go, me, reloadMe, params }) {
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [image, setImage] = useState(params?.image || null);
  const [duration, setDuration] = useState(5);
  const [quality, setQuality] = useState("720p");
  const [aspect, setAspect] = useState("9:16");
  const [sound, setSound] = useState(false);
  const [sheet, setSheet] = useState(false);
  const s = useStudio("video", reloadMe);
  const p = { duration, quality, sound, aspect, ...(image ? { image_url: image } : {}) };
  const cur = s.current;
  const vid = cur?.files?.find((f) => f.type === "video");
  return (
    <main className="screen studio mus">
      <Glow color={sound ? "#EC4899" : quality === "1080p" ? "#F5C343" : "#6E7BFF"} />
      <StudioTop title="Видео" me={me} go={go} />
      <PromptBox value={prompt} onChange={setPrompt} max={1500} placeholder="Что происходит в кадре: сцена, движение камеры, свет"
        attach={image} onAttach={setImage} attachLabel="Оживить фото" />
      {image ? <p className="muted small pad">Фото станет первым кадром, формат возьмётся из него</p>
        : !prompt.trim() && <Ideas items={IDEAS} onPick={setPrompt} />}
      <CardChoice label="Длительность" hint="цена за ролик" value={duration} onChange={setDuration}
        items={[5, 10, 15].map((d) => ({ v: d, t: `${d} секунд`, sub: `✦ ${priceOf("video", { ...p, duration: d })}`, vis: <Strip n={(d / 5) * 2} /> }))} />
      <CardChoice label="Качество" value={quality} onChange={setQuality}
        items={[{ v: "720p", t: "HD", sub: "720p · быстрее", vis: <span className="q-badge">HD</span> },
                { v: "1080p", t: "Full HD", sub: "1080p · чётче", vis: <span className="q-badge gold">FHD</span> }]} />
      {!image && <AspectPicker value={aspect} onChange={setAspect} items={ASPECTS} />}
      <FeatureToggle on={sound} onChange={setSound} tone="sound" icon="wave" title="Звук"
        sub="речь, шумы и атмосфера" subOn={`речь, шумы и атмосфера · цена ×${PRICE.video_sound_k}`} />

      {s.active ? (
        <section className="card render" aria-label="Идёт генерация">
          <p className="render-p">{s.active.prompt}</p>
          <Progress job={s.active} steps={STEPS} />
          <p className="muted small">Видео делается 2–5 минут. Можно закрыть приложение — пришлём в бот, когда будет готово.</p>
        </section>
      ) : vid && (
        <section className="vid" aria-label="Результат">
          <video src={vid.url} poster={thumbOf(cur) || undefined} controls playsInline preload="metadata" />
          <button className="row-btn" onClick={() => setSheet(true)}>Действия с видео</button>
        </section>)}

      {s.recent.length > 1 && (
        <section aria-labelledby="rv-h">
          <div className="row-h"><h2 id="rv-h">Недавние</h2><button className="link" onClick={() => go("archive", { kind: "video" })}>Все</button></div>
          <div className="recent">{s.recent.slice(0, 10).map((j) => <button key={j.id} className="thumb img" aria-label={j.prompt}
            style={{ backgroundImage: thumbOf(j) ? `url(${thumbOf(j)})` : undefined }} onClick={() => { s.setCurrent(j); window.scrollTo({ top: 0, behavior: "smooth" }); }} />)}</div>
        </section>)}
      <Dock label="Создать видео" price={priceOf("video", p)} balance={me?.balance} busy={s.busy}
        disabled={prompt.trim().length < 2 || !!s.active} onClick={() => s.run(prompt.trim(), p)} />
      <JobSheet job={sheet && cur} file={vid} onClose={() => setSheet(false)} go={go}
        onChange={(j) => { if (!j) { s.setCurrent(null); s.reload(); } else s.setCurrent(j); }} />
    </main>);
}
