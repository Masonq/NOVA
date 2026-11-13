import { useEffect, useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Icon from "../ui/Icon.jsx";
import { useStudio } from "../studio.js";
import { api } from "../api.js";
import { priceOf } from "../jobs.js";
import { toast } from "../ui/Toast.jsx";
import { haptic } from "../tg.js";

/** A vertical reel from a topic: script (editable) → voice-over → a picture per scene → music → subtitles. */
export default function ReelStudio({ go, me, reloadMe, params }) {
  const s = useStudio("reel", reloadMe);
  const [topic, setTopic] = useState(params?.prompt || "");
  const [secs, setSecs] = useState(30);
  const [script, setScript] = useState(null);
  const [writing, setWriting] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState("Puck");
  const [mode, setMode] = useState("camera");
  const [music, setMusic] = useState(true);
  const [subs, setSubs] = useState(true);
  const [sheet, setSheet] = useState(null);
  useEffect(() => { api("/api/voices").then((r) => setVoices(r.voices)).catch(() => {}); }, []);
  const write = async () => {
    setWriting(true); haptic("light");
    try { setScript(await api("/api/jobs/reel/script", { method: "POST", body: { topic: topic.trim(), seconds: secs } })); }
    catch (e) { toast(e.message, "error"); }
    finally { setWriting(false); }
  };
  const edit = (i, k, v) => setScript((sc) => ({ ...sc, scenes: sc.scenes.map((x, j) => (j === i ? { ...x, [k]: v } : x)) }));
  const drop = (i) => setScript((sc) => ({ ...sc, scenes: sc.scenes.filter((_, j) => j !== i) }));
  const add = () => setScript((sc) => ({ ...sc, scenes: [...sc.scenes, { text: "", visual: "" }] }));
  const live = mode === "live";
  const p = script ? { scenes: script.scenes, voice, live, music, subs, title: script.title, music_style: script.music } : {};
  const valid = script && script.scenes.length >= 2 && script.scenes.length <= 10 && script.scenes.every((x) => x.text.trim().length >= 2 && x.visual.trim().length >= 5);
  const v = s.current?.files?.find((x) => x.type === "video");
  return (
    <main className="screen studio">
      <StudioTop title="Ролик" me={me} go={go} />
      {!script ? (<>
        <PromptBox value={topic} onChange={setTopic} max={500} placeholder="О чём ролик: «5 фактов о Белграде», «как выбрать кофе», «история нашей кофейни»" />
        <Opts label="Длина" value={secs} onChange={setSecs} options={[{ v: 30, t: "30 секунд" }, { v: 60, t: "60 секунд" }]} />
        <button className="cta wide" disabled={topic.trim().length < 3 || writing} onClick={write}>{writing ? "Пишу сценарий…" : "Написать сценарий"}</button>
        <p className="muted small mus-tip">Сценарий бесплатный — сначала посмотрите и поправьте его, платите только за готовый ролик.</p>
      </>) : (<>
        <div className="reel-head">
          <input className="reel-title" value={script.title} maxLength={80} onChange={(e) => setScript({ ...script, title: e.target.value })} aria-label="Название" />
          <button className="link" onClick={() => setScript(null)}>Другая тема</button>
        </div>
        <ol className="scenes">
          {script.scenes.map((x, i) => (
            <li key={i} className="card scene">
              <div className="sc-h"><b>Сцена {i + 1}</b>{script.scenes.length > 2 && <button className="ic-btn" aria-label="Убрать сцену" onClick={() => drop(i)}><Icon n="x" s={13} /></button>}</div>
              <textarea value={x.text} maxLength={300} rows={2} onChange={(e) => edit(i, "text", e.target.value)} placeholder="Что говорит голос" />
              <details><summary>Картинка сцены</summary>
                <textarea value={x.visual} maxLength={900} rows={3} onChange={(e) => edit(i, "visual", e.target.value)} placeholder="Что показать в кадре" /></details>
            </li>))}
        </ol>
        {script.scenes.length < 10 && <button className="row-btn add-scene" onClick={add}><Icon n="plus" s={16} />Добавить сцену</button>}
        <div className="opts" role="group" aria-label="Голос">
          <div className="opts-h"><span>Голос</span></div>
          <div className="opts-row">{voices.map((vv) => <button key={vv.id} className={"opt" + (voice === vv.id ? " on" : "")} aria-pressed={voice === vv.id}
            onClick={() => setVoice(vv.id)}>{vv.name[0].toUpperCase() + vv.name.slice(1)}</button>)}</div>
        </div>
        <Opts label="Сцены" value={mode} onChange={setMode} hint={live ? "живое видео в каждой сцене · дороже" : "картинки с движением камеры"}
          options={[{ v: "camera", t: "Движение камеры" }, { v: "live", t: "Живые сцены" }]} />
        <Toggle label="Фоновая музыка" sub="инструментал под настроение ролика" on={music} onChange={setMusic} />
        <Toggle label="Субтитры" sub="крупный текст под голос" on={subs} onChange={setSubs} />
      </>)}
      {s.active && <Progress job={s.active} />}
      {!s.active && v && (
        <section className="clip-out" aria-label="Готовый ролик">
          <video src={v.url} poster={s.current.files.find((x) => x.type === "thumb")?.url} controls playsInline preload="metadata" />
          <button className="row-btn" onClick={() => setSheet(s.current)}>Скачать, поделиться и другое</button>
        </section>)}
      {script && <Dock label="Сделать ролик" price={priceOf("reel", p)} balance={me?.balance} busy={s.busy}
        disabled={!valid || !!s.active} onClick={() => s.run(topic.trim() || script.title, p)} />}
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => { setSheet(null); s.reload(); }} />
    </main>);
}
