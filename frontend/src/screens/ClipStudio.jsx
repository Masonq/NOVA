import { useEffect, useState } from "react";
import { StudioTop, Opts, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Player from "../ui/Player.jsx";
import { useStudio } from "../studio.js";
import { api } from "../api.js";
import { priceOf } from "../jobs.js";

/** A vertical clip for one of the user's tracks: scenes from the lyrics, cut to the chorus, with synced subtitles. */
export default function ClipStudio({ go, me, reloadMe, params }) {
  const s = useStudio("clip", reloadMe);
  const [track, setTrack] = useState(params?.track || null);
  const [tracks, setTracks] = useState(null);
  const [mode, setMode] = useState("camera");
  const [subs, setSubs] = useState(true);
  const [sheet, setSheet] = useState(null);
  useEffect(() => { if (!track) api("/api/jobs?limit=40").then((r) => setTracks(r.filter((j) => j.kind === "music" && j.status === "done"))).catch(() => setTracks([])); }, [track]);
  const live = mode === "live";
  const f = track?.files?.find((x) => x.type === "audio");
  const v = s.current?.files?.find((x) => x.type === "video");
  return (
    <main className="screen studio">
      <StudioTop title="Клип" me={me} go={go} />
      {track ? (
        <div className="clip-track">
          <Player src={f?.url} title={f?.title || track.prompt.slice(0, 40)} sub={track.params?.genre || "Трек"} cover={f?.cover_url || null} />
          <button className="link" onClick={() => setTrack(null)}>Выбрать другой трек</button>
        </div>
      ) : (
        <section className="list" aria-label="Выберите трек">
          <h2>Выберите трек</h2>
          {tracks === null ? <div className="skeleton" /> : tracks.length === 0 ? (
            <div className="empty-state slim"><p>Треков пока нет</p><button className="cta small" onClick={() => go("music")}>Сделать трек</button></div>
          ) : tracks.map((j) => {
            const a = j.files.find((x) => x.type === "audio");
            return <button key={j.id} className="row-btn gr-row" onClick={() => setTrack(j)}>
              <span className="gr-th" style={a?.cover_url ? { backgroundImage: `url(${a.cover_url})` } : undefined} />
              <span className="sr-t"><span>{a?.title || j.prompt}</span><small>{j.params?.genre || "Трек"}</small></span></button>;
          })}
        </section>)}
      <Opts label="Сцены" value={mode} onChange={setMode}
        hint={live ? "4 живые сцены по 5 с · дольше и дороже" : "6 сцен с движением камеры · ~30 с"}
        options={[{ v: "camera", t: "Движение камеры" }, { v: "live", t: "Живые сцены" }]} />
      <Toggle label="Субтитры" sub="строки песни появляются в такт" on={subs} onChange={setSubs} />
      <p className="muted small mus-tip">ИИ придумает сцены по тексту песни в одном стиле и возьмёт самый яркий фрагмент — обычно припев.</p>
      {s.active && <Progress job={s.active} />}
      {!s.active && v && (
        <section className="clip-out" aria-label="Готовый клип">
          <video src={v.url} poster={s.current.files.find((x) => x.type === "thumb")?.url} controls playsInline preload="metadata" />
          <button className="row-btn" onClick={() => setSheet(s.current)}>Скачать, поделиться и другое</button>
        </section>)}
      <Dock label="Сделать клип" price={priceOf("clip", { live })} balance={me?.balance} busy={s.busy}
        disabled={!track || !!s.active} onClick={() => s.run(`Клип: ${(f?.title || track.prompt).slice(0, 80)}`, { track_job: track.id, live, subs })} />
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => { setSheet(null); s.reload(); }} />
    </main>);
}
