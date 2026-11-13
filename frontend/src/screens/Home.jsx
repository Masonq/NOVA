import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import Composer from "../ui/Composer.jsx";
import { toast } from "../ui/Toast.jsx";
import { api } from "../api.js";
import { haptic } from "../tg.js";
import { useActiveJobs, KIND, thumbOf } from "../jobs.js";
import { JobSheet } from "../ui/Sheet.jsx";

function greeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "Доброе утро";
  if (h >= 12 && h < 17) return "Добрый день";
  if (h >= 17 && h < 23) return "Добрый вечер";
  return "Доброй ночи";
}

let greeted = false; // assemble the greeting once per app launch

function Greeting({ text }) {
  const [animate] = useState(() => !greeted);
  useEffect(() => { greeted = true; }, []);
  return (
    <h1 className={"greet" + (animate ? " assemble" : "")} aria-label={text}>
      {[...text].map((ch, i) => (
        <span key={i} aria-hidden="true" style={animate ? { animationDelay: (i * 45) + "ms" } : undefined}>{ch === " " ? "\u00a0" : ch}</span>))}
    </h1>);
}

const TOOLS = [
  { k: "image", t: "Фото", i: "image" }, { k: "video", t: "Видео", i: "video" },
  { k: "music", t: "Музыка", i: "music" }, { k: "tts", t: "Озвучка", i: "wave" }, { k: "agent", t: "Агент", i: "agent" },
];
const SUGGEST = [
  { t: "Обложка трека", go: "image", p: { prompt: "Обложка трека: ночной город в неоне, атмосферно", style: "Арт" } },
  { t: "Логотип кофейни", go: "image", p: { prompt: "Логотип кофейни «Зерно»: чашка и зёрнышко, тёплые цвета", style: "Логотип" } },
  { t: "Оживить фото", go: "video", p: {} },
  { t: "Озвучить пост", go: "tts", p: {} },
  { t: "Фон для видео", go: "music", p: { prompt: "Спокойный фон для видео о путешествиях" } },
];

export default function Home({ go, me }) {
  const [text, setText] = useState("");
  const [jobs, setJobs] = useState(null);
  const [sheet, setSheet] = useState(null);
  const load = () => api("/api/jobs?limit=12").then(setJobs).catch(() => setJobs([]));
  useEffect(() => { load(); }, []);
  const active = useActiveJobs(load);
  const g = greeting();
  const done = (jobs || []).filter((j) => j.status === "done");
  const last = done[0];
  const lastTh = last && thumbOf(last);
  const tool = (t) => {
    haptic("light");
    if (t.k === "agent") return toast("Голосовой агент появится в следующем обновлении");
    go(t.k);
  };
  const a0 = active[0];
  return (
    <main className="screen home">
      <header className="top">
        <span className="brand">NOVA</span>
        <span className="balance" aria-label={`Баланс ${me?.balance ?? 0} кредитов`}><Icon n="spark" s={14} w={2} />{me?.balance ?? "…"}</span>
      </header>
      {a0 && (
        <button className="island" onClick={() => go("tasks")} aria-label="Открыть генерации в работе">
          <span className="isl-dot" aria-hidden="true" />
          <span className="isl-t">{KIND[a0.kind]}: {a0.stage.toLowerCase()}</span>
          <span className="isl-p">{active.length > 1 ? `+${active.length - 1} · ` : ""}{a0.progress}%</span>
          <span className="isl-bar" aria-hidden="true"><i style={{ width: `${a0.progress}%` }} /></span>
        </button>)}
      <Greeting text={g} />
      <Composer value={text} onChange={setText} onSend={(t) => go("chat", { draft: t })} />
      <div className="chips" role="list">
        {SUGGEST.map((x, i) => <button key={x.t} role="listitem" className="chip ghost" onClick={() => { haptic("select"); go(x.go, x.p); }}>
          {i === 0 && <Icon n="spark" s={13} w={2} />}{x.t}</button>)}
      </div>
      <nav className="tools" aria-label="Инструменты">
        {TOOLS.map((t) => <button key={t.k} className={"tool" + (t.k === "agent" ? " accent" : "")} onClick={() => tool(t)}>
          <span className="tool-ic"><Icon n={t.i} s={20} /></span><span className="tool-t">{t.t}</span></button>)}
      </nav>
      <section aria-labelledby="res-h">
        <div className="row-h"><h2 id="res-h">Результат</h2>{last && <button className="link" onClick={() => go(last.kind)}>Открыть</button>}</div>
        {last ? (
          <button className={"result k-" + last.kind} style={lastTh ? { backgroundImage: `url(${lastTh})` } : undefined} onClick={() => setSheet(last)}>
            <span className="pill">{KIND[last.kind]}</span>
            {!lastTh && <span className="result-ic"><Icon n={last.kind === "music" ? "music" : "wave"} s={28} /></span>}
            <span className="result-cap">{last.prompt}</span>
          </button>
        ) : (
          <div className="result empty">
            <Icon n="spark" s={22} />
            <p>Здесь появится первая работа</p>
            <span className="muted small">Опишите идею в строке выше — у вас {me?.balance ?? 300} кредитов на старт</span>
          </div>
        )}
      </section>
      {done.length > 1 && (
        <section aria-labelledby="rec-h">
          <div className="row-h"><h2 id="rec-h">Недавнее</h2><button className="link" onClick={() => go("archive")}>Все</button></div>
          <div className="recent">{done.slice(1, 9).map((j) => {
            const th = thumbOf(j);
            return <button key={j.id} className={"thumb k-" + j.kind + (th ? " img" : " ic")} style={th ? { backgroundImage: `url(${th})` } : undefined}
              onClick={() => setSheet(j)} aria-label={j.prompt}>{!th && <Icon n={j.kind === "music" ? "music" : "wave"} s={22} />}</button>;
          })}</div>
        </section>)}
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={(j) => { setSheet(j); load(); }} />
    </main>);
}
