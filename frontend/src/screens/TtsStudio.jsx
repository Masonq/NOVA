import { useEffect, useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Player from "../ui/Player.jsx";
import Icon from "../ui/Icon.jsx";
import { useStudio } from "../studio.js";
import { priceOf } from "../jobs.js";
import { api } from "../api.js";
import { toast } from "../ui/Toast.jsx";

let sampleAudio = null;

export default function TtsStudio({ go, me, reloadMe, params }) {
  const [text, setText] = useState(params?.prompt || "");
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState("Sulafat");
  const [tone, setTone] = useState("Спокойно");
  const [playing, setPlaying] = useState(null);
  const [sheet, setSheet] = useState(null);
  const s = useStudio("tts", reloadMe);
  useEffect(() => { api("/api/voices").then((r) => { setVoices(r.voices); setVoice(r.default); }).catch(() => {}); return () => sampleAudio?.pause(); }, []);
  const sample = async (id) => {
    if (playing === id) { sampleAudio?.pause(); setPlaying(null); return; }
    setPlaying(id);
    try {
      const { url } = await api(`/api/voices/${id}/sample`);
      sampleAudio?.pause(); sampleAudio = new Audio(url);
      sampleAudio.onended = () => setPlaying(null);
      await sampleAudio.play();
    } catch (e) { setPlaying(null); toast(e.message || "Не удалось проиграть", "error"); }
  };
  const list = s.current ? [s.current, ...s.recent.filter((j) => j.id !== s.current.id)] : s.recent;
  return (
    <main className="screen studio">
      <StudioTop title="Озвучка" me={me} go={go} />
      <PromptBox value={text} onChange={setText} max={5000} placeholder="Вставьте текст — прочитаю его живым голосом" />
      <div className="opts" role="group" aria-label="Голос">
        <div className="opts-h"><span>Голос</span><small>нажмите ▶, чтобы послушать</small></div>
        <div className="voices">
          {voices.map((v) => (
            <div key={v.id} className={"voice" + (voice === v.id ? " on" : "")}>
              <button className="v-pick" aria-pressed={voice === v.id} onClick={() => setVoice(v.id)}>
                <b>{v.name[0].toUpperCase() + v.name.slice(1)}</b><small>{v.id}</small></button>
              <button className="v-play" aria-label={`Послушать: ${v.name}`} onClick={() => sample(v.id)}>
                {playing === v.id ? <Icon n="pause" s={13} /> : <Icon n="play" s={13} />}</button>
            </div>))}
        </div>
      </div>
      <Opts label="Интонация" value={tone} options={["Спокойно", "Бодро", "Диктор", "Шёпот"]} onChange={setTone} />
      {s.active && <section className="card render"><Progress job={s.active} /></section>}
      {list.length > 0 && (
        <section className="tracks" aria-label="Озвучки">
          {list.slice(0, 6).map((j) => j.files?.[0] && (
            <Player key={j.id} src={j.files[0].url} title={j.prompt.slice(0, 44)} sub={`${j.params?.voice || ""} · ${j.params?.tone || ""}`}
              onMore={() => setSheet(j)} />))}
        </section>)}
      <Dock label="Озвучить" price={priceOf("tts", {}, text)} balance={me?.balance} busy={s.busy}
        disabled={text.trim().length < 2 || !!s.active} onClick={() => s.run(text.trim(), { voice, tone })} />
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => s.reload()} />
    </main>);
}
