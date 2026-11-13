import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { Progress } from "../ui/Studio.jsx";
import { useActiveJobs, KIND, thumbOf } from "../jobs.js";
import { api } from "../api.js";
import { toast } from "../ui/Toast.jsx";

const STUDIO = { image: "image", video: "video", music: "music", tts: "tts" };

export default function Tasks({ go }) {
  const [done, setDone] = useState([]);
  const load = () => api("/api/jobs?limit=12").then((r) => setDone(r.filter((j) => j.status !== "queued" && j.status !== "running"))).catch(() => {});
  useEffect(() => { load(); }, []);
  const active = useActiveJobs(load);
  const cancel = async (j) => {
    try { await api(`/api/jobs/${j.id}/cancel`, { method: "POST" }); toast("Отменено, кредиты вернулись"); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  return (
    <main className="screen">
      <header className="bar"><button className="ic-btn" aria-label="Назад" onClick={() => go("home")}><Icon n="back" /></button><h1>В работе</h1></header>
      {active.length === 0 && <div className="empty-state slim"><Icon n="check" s={22} /><p>Сейчас ничего не генерируется</p></div>}
      {active.map((j) => (
        <section key={j.id} className="card task">
          <div className="task-h"><span className={"tag k-" + j.kind}>{KIND[j.kind]}</span><span className="task-p">{j.prompt}</span></div>
          <Progress job={j} />
          <div className="task-f">
            <button className="link" onClick={() => go(STUDIO[j.kind])}>Открыть</button>
            {j.status === "queued" && <button className="link danger" onClick={() => cancel(j)}>Отменить</button>}
          </div>
        </section>))}
      {done.length > 0 && (
        <section aria-labelledby="td-h">
          <div className="row-h"><h2 id="td-h">Недавно</h2></div>
          <ul className="list">
            {done.map((j) => (
              <li key={j.id} onClick={() => go(STUDIO[j.kind])} className="tap">
                <span className={"mini k-" + j.kind} style={thumbOf(j) ? { backgroundImage: `url(${thumbOf(j)})` } : undefined} />
                <span><span className="t">{j.prompt.slice(0, 40)}</span><span className={"muted small" + (j.status === "failed" ? " danger" : "")}>
                  {j.status === "done" ? `${KIND[j.kind]} · готово` : j.status === "failed" ? "Не получилось, кредиты вернулись" : "Отменено"}</span></span>
                <Icon n="chevron" s={15} />
              </li>))}
          </ul>
        </section>)}
    </main>);
}
