import { useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Player from "../ui/Player.jsx";
import { useStudio } from "../studio.js";
import { priceOf } from "../jobs.js";

const GENRES = ["Поп", "Lo-fi", "Хип-хоп", "Электроника", "Рок", "Эмбиент", "Джаз", "Кино"];
const MOODS = ["Спокойно", "Энергично", "Грустно", "Романтично", "Эпично"];
const coverUrl = (f) => (f.cover ? f.url.replace(/[^/]+$/, f.cover.split("/").pop()) : null);

export default function MusicStudio({ go, me, reloadMe, params }) {
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [genre, setGenre] = useState("Lo-fi");
  const [mood, setMood] = useState("Спокойно");
  const [vocal, setVocal] = useState(false);
  const [sheet, setSheet] = useState(null);
  const s = useStudio("music", reloadMe);
  const list = s.current ? [s.current, ...s.recent.filter((j) => j.id !== s.current.id)] : s.recent;
  return (
    <main className="screen studio">
      <StudioTop title="Музыка" me={me} go={go} />
      <PromptBox value={prompt} onChange={setPrompt} max={2900} placeholder={vocal ? "О чём песня: тема, история, пара строк" : "Для чего трек: фон для видео, учёба, тренировка"} />
      <Opts label="Жанр" value={genre} options={GENRES} onChange={setGenre} />
      <Opts label="Настроение" value={mood} options={MOODS} onChange={setMood} />
      <Toggle label="С вокалом" sub={vocal ? "текст напишется сам, поёт по-русски" : "только музыка, без голоса"} on={vocal} onChange={setVocal} />
      {s.active && (
        <section className="card render" aria-label="Идёт генерация">
          <p className="render-p">{s.active.prompt}</p>
          <Progress job={s.active} />
          <p className="muted small">Трек пишется около 2 минут. Получится два варианта с обложками.</p>
        </section>)}
      {list.length > 0 && (
        <section className="tracks" aria-label="Треки">
          {list.slice(0, 8).flatMap((j) => (j.files || []).filter((f) => f.type === "audio").map((f, i) => (
            <Player key={f.url} src={f.url} cover={coverUrl(f)} title={f.title || j.prompt.slice(0, 40)}
              sub={`${j.params?.genre || "Трек"}${(j.files.length > 1) ? ` · вариант ${i + 1}` : ""}`} onMore={() => setSheet({ j, f })} />)))}
        </section>)}
      <Dock label={vocal ? "Создать песню" : "Создать трек"} price={priceOf("music")} balance={me?.balance} busy={s.busy}
        disabled={prompt.trim().length < 2 || !!s.active}
        onClick={() => s.run(prompt.trim(), { genre, mood, instrumental: !vocal })} />
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go} onChange={() => s.reload()} />
    </main>);
}
