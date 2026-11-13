import { useState } from "react";
import { StudioTop, Opts, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import { JobSheet } from "../ui/Sheet.jsx";
import Icon from "../ui/Icon.jsx";
import { useStudio } from "../studio.js";
import { PRICE, priceOf, thumbOf } from "../jobs.js";

const OCCASIONS = ["День рождения", "Свадьба", "Юбилей", "Новый год", "Годовщина", "8 Марта", "23 Февраля", "Свой повод"];
const PARTS = [
  ["song", "Песня", "с именем в припеве", () => PRICE.music],
  ["card", "Открытка", "с надписью-поздравлением", () => PRICE.image + PRICE.image_hq],
  ["video", "Видео-открытка", "открытка оживает под песню", () => PRICE.video_std_s * 5 + PRICE.combo_fee],
];

/** One tap: a personal song, a card with the greeting and a video card. */
export default function GreetingStudio({ go, me, reloadMe }) {
  const s = useStudio("greeting", reloadMe);
  const [name, setName] = useState("");
  const [occ, setOcc] = useState("День рождения");
  const [own, setOwn] = useState("");
  const [about, setAbout] = useState("");
  const [voices, setVoices] = useState("auto");
  const [parts, setParts] = useState(["song", "card", "video"]);
  const [sheet, setSheet] = useState(null);
  const occasion = occ === "Свой повод" ? own.trim() : occ;
  const toggle = (k, on) => setParts((p) => {
    let n = on ? [...new Set([...p, k])] : p.filter((x) => x !== k);
    if (k === "video" && on && !n.includes("card")) n = [...n, "card"];       // the video card is made from the card
    return n;
  });
  const params = { name: name.trim(), occasion, voices, parts };
  const ok = name.trim().length >= 1 && occasion.length >= 2 && parts.length > 0;
  return (
    <main className="screen studio">
      <StudioTop title="Поздравление" me={me} go={go} />
      <label className="field"><span>Кого поздравляем</span>
        <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="Имя, например Аня" /></label>
      <Opts label="Повод" value={occ} options={OCCASIONS} onChange={setOcc} />
      {occ === "Свой повод" && <label className="field"><span>Ваш повод</span>
        <input value={own} maxLength={40} onChange={(e) => setOwn(e.target.value)} placeholder="Например, защита диплома" /></label>}
      <PromptBox value={about} onChange={setAbout} max={600}
        placeholder="Пара слов о человеке и пожелания: что любит, общие шутки, чего пожелать. Песня получится личной" />
      <div className="opts" role="group" aria-label="Что входит">
        <div className="opts-h"><span>Что входит</span><small>можно выбрать любое</small></div>
        <div className="card toggles">
          {PARTS.map(([k, t, sub, price]) => (
            <Toggle key={k} label={`${t} · ${price()} кр.`} sub={sub} on={parts.includes(k)} onChange={(on) => toggle(k, on)} />))}
        </div>
      </div>
      {parts.includes("song") && <Opts label="Кто поёт" value={voices} onChange={setVoices}
        options={[{ v: "auto", t: "Авто" }, { v: "male", t: "Мужской" }, { v: "female", t: "Женский" }, { v: "duet", t: "Дуэт" }]} />}
      {s.active && <Progress job={s.active} />}
      {s.recent.length > 0 && (
        <section className="list" aria-label="Ваши поздравления">
          <h2>Ваши поздравления</h2>
          {s.recent.map((j) => (
            <button key={j.id} className="row-btn gr-row" onClick={() => setSheet(j)}>
              <span className="gr-th" style={thumbOf(j) ? { backgroundImage: `url(${thumbOf(j)})` } : undefined}>{!thumbOf(j) && <Icon n="gift" s={18} />}</span>
              <span className="sr-t"><span>{j.params?.occasion} — {j.params?.name}</span><small>{(j.files || []).map((f) => ({ video: "видео", image: "открытка", audio: "песня" })[f.type]).filter(Boolean).join(" · ")}</small></span>
              <Icon n="chevron" s={15} />
            </button>))}
        </section>)}
      <Dock label="Создать поздравление" price={priceOf("greeting", params)} balance={me?.balance} busy={s.busy}
        disabled={!ok || !!s.active} onClick={() => s.run(about.trim() || `${occasion} — ${name.trim()}`, params)} />
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => { setSheet(null); s.reload(); }} />
    </main>);
}
