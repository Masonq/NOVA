import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import { SlideTabs } from "../ui/TabBar.jsx";
import { api } from "../api.js";
import { COMBO, KIND, thumbOf } from "../jobs.js";

const FILTERS = [{ k: "", t: "Все" }, { k: "image", t: "Фото", i: "image" }, { k: "video", t: "Видео", i: "video" }, { k: "music", t: "Музыка", i: "music" }, { k: "tts", t: "Озвучка", i: "wave" }, { k: "combo", t: "Сборки", i: "film" }, { k: "fav", t: "Избранное", i: "heart" }];
function left(iso) {
  if (!iso) return "";
  const d = Math.ceil((new Date(iso) - Date.now()) / 864e5);
  return d <= 0 ? "удаляется" : `ещё ${d} дн.`;
}
export default function Archive({ go, params }) {
  const [jobs, setJobs] = useState(null);
  const [f, setF] = useState(params?.kind || "");
  const [sheet, setSheet] = useState(null);
  const load = () => api("/api/jobs?limit=100").then((r) => setJobs(r.filter((j) => j.status === "done"))).catch(() => setJobs([]));
  useEffect(() => { load(); }, []);
  const shown = (jobs || []).filter((j) => !f || (f === "fav" ? j.favorite : f === "combo" ? COMBO.has(j.kind) : j.kind === f));
  return (
    <main className="screen">
      <header className="bar"><h1>Архив</h1>
        {jobs?.some((j) => j.kind === "image" || j.kind === "video") && <button className="chip" onClick={() => go("feed")}>Лента</button>}</header>
      {jobs?.length > 0 && (
        <SlideTabs label="Фильтр" items={FILTERS} value={f} onChange={setF} />)}
      {jobs === null && <div className="skeleton" />}
      {jobs?.length === 0 && (
        <div className="empty-state">
          <Icon n="clock" s={26} />
          <p>Здесь будут все ваши работы</p>
          <span className="muted small">Картинки, видео, треки и&nbsp;озвучка хранятся 30&nbsp;дней</span>
          <button className="cta small" onClick={() => go("home")}>Создать первую</button>
        </div>)}
      {jobs?.length > 0 && shown.length === 0 && <p className="muted center small">Здесь пока пусто</p>}
      <div className="grid">
        {shown.map((j) => {
          const th = thumbOf(j);
          return (
            <button key={j.id} className={"cell k-" + j.kind + (th ? " has" : "")} style={th ? { backgroundImage: `url(${th})` } : undefined} onClick={() => setSheet(j)}>
              <span className="pill">{KIND[j.kind]}{j.kind === "video" ? ` · ${j.params?.duration || 5} с` : ""}</span>
              {j.favorite && <span className="fav-dot" aria-label="В избранном"><Icon n="heart" s={12} /></span>}
              {!th && (j.kind === "music" || j.kind === "tts") && <span className="cell-ic"><Icon n={j.kind === "music" ? "music" : "wave"} s={22} /></span>}
              <span className="cell-t">{j.prompt}</span>
              <span className="cell-m">{left(j.expires)}</span>
            </button>);
        })}
      </div>
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go}
        onChange={(j) => { if (!j) load(); else { setJobs((x) => x.map((y) => y.id === j.id ? j : y)); setSheet(j); } }} />
    </main>);
}
