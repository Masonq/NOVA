import { useEffect, useState } from "react";
import { StudioTop, PromptBox, Dock, Progress } from "../ui/Studio.jsx";
import { Tiles, Glow } from "../ui/Creative.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Player from "../ui/Player.jsx";
import Icon from "../ui/Icon.jsx";
import { useStudio } from "../studio.js";
import { priceOf, parseSections, WHO_RU } from "../jobs.js";
import { api } from "../api.js";
import { toast } from "../ui/Toast.jsx";

let sampleAudio = null;
const TONES = [
  { v: "Спокойно", t: "Спокойно", a: "#4FD1C5", b: "#0B3330", m: "calm" },
  { v: "Бодро", t: "Бодро", a: "#FF8A3D", b: "#3D1A05", m: "bolt" },
  { v: "Диктор", t: "Диктор", a: "#4FA3FF", b: "#0B2342", m: "mic" },
  { v: "Шёпот", t: "Шёпот", a: "#B18CFF", b: "#211340", m: "whisper" },
];

export default function TtsStudio({ go, me, reloadMe, params }) {
  const [text, setText] = useState(params?.prompt || "");
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState("Sulafat");
  const [tone, setTone] = useState("Спокойно");
  const [male, setMale] = useState("Orus");
  const [female, setFemale] = useState("Sulafat");
  const sections = parseSections(text);
  const needs = new Set(sections.flatMap((p) => p.who === "duet" ? ["male", "female"] : [p.who]));
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
    <main className="screen studio mus">
      <Glow color={TONES.find((x) => x.v === tone)?.a} />
      <StudioTop title="Озвучка" me={me} go={go} />
      <PromptBox value={text} onChange={setText} max={5000} placeholder="Вставьте текст — прочитаю его живым голосом" />
      {sections.length === 0 ? (
        <p className="muted small tts-tip">Можно читать разными голосами: отметьте части как <code>[Куплет 1: мужской]</code>, <code>[Припев: женский]</code>, <code>[Бридж: дуэт]</code></p>
      ) : (
        <div className="card parts">
          <b>Частей: {sections.length}</b>
          <div className="parts-row">{sections.map((p, i) => <span key={i} className={"part " + (p.who || "none")}>{p.label} · {WHO_RU[p.who]}</span>)}</div>
        </div>)}
      {needs.has("male") && <VoiceGrid short title="Мужской голос" list={voices.filter((v) => v.name.includes("мужской"))} value={male} onPick={setMale} playing={playing} sample={sample} />}
      {needs.has("female") && <VoiceGrid short title="Женский голос" list={voices.filter((v) => v.name.includes("женский"))} value={female} onPick={setFemale} playing={playing} sample={sample} />}
      {(sections.length === 0 || needs.has("")) && <VoiceGrid title={sections.length ? "Голос для частей без пометки" : "Голос"} list={voices} value={voice} onPick={setVoice} playing={playing} sample={sample} hint="нажмите ▶, чтобы послушать" />}
      <Tiles label="Интонация" items={TONES} value={tone} onChange={setTone} grid />
      {s.active && <section className="card render"><Progress job={s.active} /></section>}
      {list.length > 0 && (
        <section className="tracks" aria-label="Озвучки">
          {list.slice(0, 6).map((j) => j.files?.[0] && (
            <Player key={j.id} src={j.files[0].url} title={j.prompt.slice(0, 44)} sub={`${j.params?.voice || ""} · ${j.params?.tone || ""}`}
              onMore={() => setSheet(j)} />))}
        </section>)}
      <Dock label="Озвучить" price={priceOf("tts", {}, text)} balance={me?.balance} busy={s.busy}
        disabled={text.trim().length < 2 || !!s.active} onClick={() => s.run(text.trim(), { voice, tone, ...(sections.length ? { male, female } : {}) })} />
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => s.reload()} />
    </main>);
}


function VoiceGrid({ title, list, value, onPick, playing, sample, hint, short }) {
  const label = (n) => { const t = n.replace(/\s*(мужской|женский)$/, ""); return t[0].toUpperCase() + t.slice(1); };   // the avatar colour shows the gender
  return (
    <div className="opts" role="group" aria-label={title}>
      <div className="opts-h"><span>{title}</span>{hint && <small>{hint}</small>}</div>
      <div className="voices">
        {list.map((v) => (
          <div key={v.id} className={"voice" + (value === v.id ? " on" : "")}>
            <button className="v-pick" aria-pressed={value === v.id} onClick={() => onPick(v.id)}>
              <span className={"v-av " + (v.name.includes("мужской") ? "m" : "f")} aria-hidden="true">{label(v.name)[0]}</span>
              <span className="v-tx"><b>{label(v.name)}</b><small>{v.id}</small></span></button>
            <button className={"v-play" + (playing === v.id ? " on" : "")} aria-label={`Послушать: ${v.name}`} onClick={() => sample(v.id)}>
              {playing === v.id ? <span className="eq sm"><i /><i /><i /></span> : <Icon n="play" s={13} />}</button>
          </div>))}
      </div>
    </div>);
}
