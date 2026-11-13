import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { api } from "../api.js";

const KIND = { image: "Фото", video: "Видео", music: "Трек", tts: "Озвучка" };
function left(iso) {
  if (!iso) return "";
  const d = Math.ceil((new Date(iso) - Date.now()) / 864e5);
  return d <= 0 ? "удаляется" : `удалится через ${d} дн.`;
}
export default function Archive({ go }) {
  const [jobs, setJobs] = useState(null);
  useEffect(() => { api("/api/jobs?limit=60").then(setJobs).catch(() => setJobs([])); }, []);
  return (
    <main className="screen">
      <header className="bar"><h1>Архив</h1></header>
      {jobs === null && <div className="skeleton" />}
      {jobs?.length === 0 && (
        <div className="empty-state">
          <Icon n="clock" s={26} />
          <p>Здесь будут все ваши работы</p>
          <span className="muted small">Картинки, видео, треки и озвучка хранятся 30 дней</span>
          <button className="cta small" onClick={() => go("home")}>Создать первую</button>
        </div>)}
      <div className="grid">
        {jobs?.map((j) => (
          <div key={j.id} className={"cell k-" + j.kind}>
            <span className="pill">{KIND[j.kind] || j.kind}</span>
            <span className="cell-t">{j.prompt}</span>
            <span className="cell-m">{left(j.expires)}</span>
          </div>))}
      </div>
    </main>);
}
