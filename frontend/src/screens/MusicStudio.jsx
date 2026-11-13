import { useState } from "react";
import { StudioTop, Opts, OptsMulti, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import Sheet, { JobSheet } from "../ui/Sheet.jsx";
import Icon from "../ui/Icon.jsx";
import { api } from "../api.js";
import Player from "../ui/Player.jsx";
import { useStudio } from "../studio.js";
import { priceOf } from "../jobs.js";

const GENRES = ["Авто", "Рэп", "Поп", "Lo-fi", "Хип-хоп", "Электроника", "Рок", "Эмбиент", "Джаз", "Кино"];
const MOODS = ["Авто", "Спокойно", "Энергично", "Грустно", "Романтично", "Эпично"];
const coverUrl = (f) => f.cover_url || null;

export default function MusicStudio({ go, me, reloadMe, params }) {
  const [vj, setVj] = useState(params?.voice_job ? { id: params.voice_job, text: params.voice_text || "", voice: params.voice || "" } : null);
  const [pick, setPick] = useState(false);
  const [tts, setTts] = useState(null);
  const openPick = () => { setPick(true); api("/api/jobs?limit=40").then((r) => setTts(r.filter((j) => j.kind === "tts" && j.status === "done"))).catch(() => setTts([])); };
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [genre, setGenre] = useState([]);
  const [mood, setMood] = useState([]);
  const [voices, setVoices] = useState("auto");
  const [vjVoices, setVjVoices] = useState("same");
  const [vocal, setVocal] = useState(false);
  const [sheet, setSheet] = useState(null);
  const s = useStudio("music", reloadMe);
  const list = s.current ? [s.current, ...s.recent.filter((j) => j.id !== s.current.id)] : s.recent;
  return (
    <main className="screen studio">
      <StudioTop title="Музыка" me={me} go={go} />
      {vj ? (
        <div className="card voicejob">
          <span className="vj-ic"><Icon n="wave" s={18} /></span>
          <span className="sr-t"><b>Голос из озвучки{vj.voice ? ` · ${vj.voice}` : ""}</b><small>{vj.text}</small></span>
          <button className="ic-btn" aria-label="Убрать голос" onClick={() => setVj(null)}><Icon n="x" s={14} /></button>
        </div>
      ) : (
        <button className="row-btn vj-add" onClick={openPick}><Icon n="wave" /><span className="sr-t"><span>Голос из озвучки</span><small>ваш голос и текст станут треком</small></span><Icon n="chevron" s={15} /></button>
      )}
      <PromptBox value={prompt} onChange={setPrompt} max={2900}
        placeholder={vj ? "Пожелания к музыке — необязательно: темп, инструменты, атмосфера" : vocal ? "О чём песня и как звучит: тема, история, на кого похоже" : "Для чего трек и как звучит: фон для видео, учёба, тренировка"} />
      <OptsMulti label="Жанр" value={genre} options={GENRES} onChange={setGenre} />
      <OptsMulti label="Настроение" value={mood} options={MOODS} onChange={setMood} />
      {!vj && <Toggle label="С вокалом" sub={vocal ? "ИИ напишет текст, поёт по‑русски" : "только музыка, без голоса"} on={vocal} onChange={setVocal} />}
      {vj && <Opts label="Кто поёт" value={vjVoices} onChange={setVjVoices}
        hint={{ same: `голос озвучки${vj.voice ? ` · ${vj.voice}` : ""}`, male: "мужской голос", female: "женский голос", duet: "ИИ поделит текст на партии" }[vjVoices]}
        options={[{ v: "same", t: "Как в озвучке" }, { v: "male", t: "Мужской" }, { v: "female", t: "Женский" }, { v: "duet", t: "Дуэт" }]} />}
      {!vj && vocal && <Opts label="Голос" value={voices} onChange={setVoices}
        hint={{ auto: "ИИ решит по смыслу песни", male: "", female: "", duet: "ИИ распределит части" }[voices]}
        options={[{ v: "auto", t: "Авто" }, { v: "male", t: "Мужской" }, { v: "female", t: "Женский" }, { v: "duet", t: "Дуэт" }]} />}
      {s.active && (
        <section className="card render" aria-label="Идёт генерация">
          <p className="render-p">{s.active.prompt}</p>
          <Progress job={s.active} />
          <p className="muted small">Пишу текст и записываю трек — около 2 минут.</p>
        </section>)}
      {list.length > 0 && (
        <section className="tracks" aria-label="Треки">
          {list.slice(0, 8).flatMap((j) => (j.files || []).filter((f) => f.type === "audio").slice(0, 1).map((f, i) => (
            <Player key={f.url} src={f.url} cover={coverUrl(f)} title={f.title || j.prompt.slice(0, 40)}
              sub={[j.params?.genre, j.params?.instrumental === false
                ? ({ male: "мужской вокал", female: "женский вокал", duet: "дуэт" }[j.params?.brief?.vocals] || "с вокалом") : "инструментал"].filter(Boolean).join(" · ")} onMore={() => setSheet({ j, f })} />)))}
        </section>)}
      <Dock label={vj ? "Создать трек из озвучки" : vocal ? "Создать песню" : "Создать трек"} price={priceOf("music", vj ? { voice_chars: vj.text.length } : {})}
        balance={me?.balance} busy={s.busy} disabled={(!vj && prompt.trim().length < 2) || !!s.active}
        onClick={() => s.run(prompt.trim() || "Трек из озвучки", { genre: genre.join(", "), mood: mood.join(", "),
          instrumental: vj ? false : !vocal, ...(vj ? { voice_job: vj.id, voices: vjVoices } : vocal ? { voices } : {}) })} />
      <Sheet open={pick} onClose={() => setPick(false)} title="Голос из озвучки">
        <h3 className="sheet-title">Выберите озвучку</h3>
        {tts === null ? <div className="skeleton" /> : tts.length === 0 ? (
          <div className="empty-state slim"><p>Озвучек пока нет</p><button className="cta small" onClick={() => go("tts")}>Сделать озвучку</button></div>
        ) : tts.map((j) => (
          <button key={j.id} className="sheet-row" onClick={() => { setVj({ id: j.id, text: j.prompt, voice: j.params?.voice || "" }); setPick(false); }}>
            <span className="sr-ic"><Icon n="wave" /></span>
            <span className="sr-t"><span>{j.prompt}</span><small>{[j.params?.voice, j.params?.tone].filter(Boolean).join(" · ")}</small></span>
          </button>))}
      </Sheet>
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go} onChange={() => s.reload()} />
    </main>);
}
