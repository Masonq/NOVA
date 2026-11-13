import { useEffect, useMemo, useState } from "react";
import Icon from "../ui/Icon.jsx";
import Composer from "../ui/Composer.jsx";
import { toast } from "../ui/Toast.jsx";
import { api } from "../api.js";
import { haptic } from "../tg.js";

function greeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "Доброе утро";
  if (h >= 12 && h < 17) return "Добрый день";
  if (h >= 17 && h < 23) return "Добрый вечер";
  return "Доброй ночи";
}

function Particles() {
  const dots = useMemo(() => Array.from({ length: 14 }, (_, i) => ({
    x: 2 + ((i * 37) % 60), y: 6 + ((i * 53) % 20), d: 1.4 + (i % 3) * 0.6, delay: (i * 0.13).toFixed(2),
  })), []);
  return <span className="particles" aria-hidden="true">{dots.map((p, i) =>
    <i key={i} style={{ left: p.x, top: p.y, width: p.d, height: p.d, animationDelay: p.delay + "s" }} />)}</span>;
}

const TOOLS = [
  { k: "image", t: "Фото", i: "image" }, { k: "video", t: "Видео", i: "video" },
  { k: "music", t: "Музыка", i: "music" }, { k: "tts", t: "Озвучка", i: "wave" }, { k: "agent", t: "Агент", i: "agent" },
];
const SUGGEST = ["Обложка трека", "Логотип кофейни", "Озвучить пост"];

export default function Home({ go, me }) {
  const [text, setText] = useState("");
  const [jobs, setJobs] = useState(null);
  useEffect(() => { api("/api/jobs?limit=8").then(setJobs).catch(() => setJobs([])); }, []);
  const g = greeting();
  const last = jobs?.find((j) => j.status === "done");
  const tool = (t) => { haptic("light"); toast(t.k === "agent" ? "Голосовой агент появится в ближайшем обновлении" : `${t.t} появится в ближайшем обновлении`); };
  return (
    <main className="screen home">
      <header className="top">
        <span className="brand">NOVA</span>
        <span className="balance" aria-label={`Баланс ${me?.balance ?? 0} кредитов`}><Icon n="spark" s={14} w={2} />{me?.balance ?? "…"}</span>
      </header>
      <div className="greet" aria-label={g}>
        <span>{g.slice(0, -1)}</span><span className="fade">{g.slice(-1)}</span><Particles />
      </div>
      <Composer value={text} onChange={setText} onSend={(t) => go("chat", { draft: t })} />
      <div className="chips" role="list">
        {SUGGEST.map((s, i) => <button key={s} role="listitem" className="chip ghost" onClick={() => { haptic("select"); setText(s); }}>
          {i === 0 && <Icon n="spark" s={13} w={2} />}{s}</button>)}
      </div>
      <nav className="tools" aria-label="Инструменты">
        {TOOLS.map((t) => <button key={t.k} className={"tool" + (t.k === "agent" ? " accent" : "")} onClick={() => tool(t)}>
          <span className="tool-ic"><Icon n={t.i} s={20} /></span><span className="tool-t">{t.t}</span></button>)}
      </nav>
      <section aria-labelledby="res-h">
        <div className="row-h"><h2 id="res-h">Результат</h2></div>
        {last ? (
          <div className="result" style={{ backgroundImage: last.files?.[0]?.url ? `url(${last.files[0].url})` : undefined }}>
            <span className="pill">{last.prompt.slice(0, 40)}</span>
          </div>
        ) : (
          <div className="result empty">
            <Icon n="spark" s={22} />
            <p>Здесь появится первая работа</p>
            <span className="muted small">Опишите идею в строке выше — у вас {me?.balance ?? 300} кредитов на старт</span>
          </div>
        )}
      </section>
      {jobs?.length > 0 && (
        <section aria-labelledby="rec-h">
          <div className="row-h"><h2 id="rec-h">Недавнее</h2><button className="link" onClick={() => go("archive")}>Все</button></div>
          <div className="recent">{jobs.slice(0, 4).map((j) => <div key={j.id} className={"thumb k-" + j.kind}><span>{j.prompt.slice(0, 18)}</span></div>)}</div>
        </section>)}
    </main>);
}
