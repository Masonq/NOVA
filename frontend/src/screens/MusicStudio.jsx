import { useEffect, useState } from "react";
import { StudioTop, Opts, OptsMulti, PromptBox, Dock, Progress, Toggle } from "../ui/Studio.jsx";
import Sheet, { JobSheet } from "../ui/Sheet.jsx";
import Icon from "../ui/Icon.jsx";
import { api } from "../api.js";
import Player from "../ui/Player.jsx";
import { useStudio } from "../studio.js";
import { priceOf, parseSections } from "../jobs.js";
import { toast } from "../ui/Toast.jsx";
import { haptic } from "../tg.js";

const GENRES = ["Авто", "Рэп", "Поп", "Lo-fi", "Хип-хоп", "Электроника", "Рок", "Эмбиент", "Джаз", "Кино"];
const MOODS = ["Авто", "Спокойно", "Энергично", "Грустно", "Романтично", "Эпично"];
const LENGTHS = [{ v: 0, t: "Авто" }, { v: 30, t: "30 с" }, { v: 60, t: "1 мин" }, { v: 120, t: "2 мин" }, { v: 180, t: "3 мин" }];
const coverUrl = (f) => f.cover_url || null;
const VOC = { male: "мужской вокал", female: "женский вокал", duet: "дуэт" };

export default function MusicStudio({ go, me, reloadMe, params }) {
  const [vj, setVj] = useState(params?.voice_job ? { id: params.voice_job, text: params.voice_text || "", voice: params.voice || "" } : null);
  const [pick, setPick] = useState(false);
  const [tts, setTts] = useState(null);
  const openPick = () => { setPick(true); api("/api/jobs?limit=40").then((r) => setTts(r.filter((j) => j.kind === "tts" && j.status === "done"))).catch(() => setTts([])); };
  const [prompt, setPrompt] = useState(params?.prompt || "");
  const [genre, setGenre] = useState([]);
  const [mood, setMood] = useState([]);
  const [voices, setVoices] = useState("auto");
  const [vjVoices, setVjVoices] = useState("same");
  const [vocal, setVocal] = useState(false);
  const [sheet, setSheet] = useState(null);
  const [length, setLength] = useState(0);
  const [avoid, setAvoid] = useState("");
  const [wild, setWild] = useState(false);
  const [artists, setArtists] = useState(null);
  const [artist, setArtist] = useState(null);
  const [artPick, setArtPick] = useState(false);
  const loadArtists = () => api("/api/artists").then(setArtists).catch(() => setArtists([]));
  useEffect(() => { loadArtists(); }, []);
  useEffect(() => {                       // «Спеть этим исполнителем» from a track's sheet
    if (params?.artist && artists) { const a = artists.find((x) => x.id === params.artist); if (a) { setArtist(a); setVocal(true); } }
  }, [params?.artist, artists]);
  const delArtist = async (a) => {
    if (!window.confirm(`Удалить исполнителя «${a.name}»?`)) return;
    await api(`/api/artists/${a.id}`, { method: "DELETE" }).catch(() => {});
    if (artist?.id === a.id) setArtist(null);
    loadArtists();
  };
  const s = useStudio("music", reloadMe);
  const list = s.current ? [s.current, ...s.recent.filter((j) => j.id !== s.current.id)] : s.recent;
  return (
    <main className="screen studio">
      <StudioTop title="Музыка" me={me} go={go} />
      {vj ? (
        <div className="card voicejob">
          <span className="vj-ic"><Icon n="wave" s={18} /></span>
          <span className="sr-t"><b>Голос из озвучки{vj.voice ? ` · ${vj.voice}` : ""}</b><small>{vj.text}</small></span>
          <button className="ic-btn" aria-label="Убрать голос" onClick={() => setVj(null)}><Icon n="x" s={14} /></button>
        </div>
      ) : (
        <button className="row-btn vj-add" onClick={openPick}><Icon n="wave" /><span className="sr-t"><span>Голос из озвучки</span><small>ваш голос и текст станут треком</small></span><Icon n="chevron" s={15} /></button>
      )}
      <PromptBox value={prompt} onChange={setPrompt} max={2900}
        placeholder={vj ? "Пожелания к музыке — необязательно: темп, инструменты, атмосфера" : vocal ? "О чём песня и как звучит: тема, история, на кого похоже" : "Для чего трек и как звучит: фон для видео, учёба, тренировка"} />
      {!vj && vocal && parseSections(prompt).length > 0 && <p className="muted small mus-tip">Ваш текст с разметкой — Suno споёт его как написано, голоса по пометкам</p>}
      <OptsMulti label="Жанр" value={genre} options={GENRES} onChange={setGenre} />
      <OptsMulti label="Настроение" value={mood} options={MOODS} onChange={setMood} />
      {!vj && <Toggle label="С вокалом" sub={vocal ? "ИИ напишет текст, поёт по‑русски" : "только музыка, без голоса"} on={vocal} onChange={setVocal} />}
      {vj && <Opts label="Кто поёт" value={vjVoices} onChange={setVjVoices}
        hint={{ same: `голос озвучки${vj.voice ? ` · ${vj.voice}` : ""}`, male: "мужской голос", female: "женский голос", duet: "ИИ поделит текст на партии" }[vjVoices]}
        options={[{ v: "same", t: "Как в озвучке" }, { v: "male", t: "Мужской" }, { v: "female", t: "Женский" }, { v: "duet", t: "Дуэт" }]} />}
      {!vj && vocal && (
        <button className="row-btn vj-add" onClick={() => { haptic("select"); setArtPick(true); }}>
          <Icon n="user" /><span className="sr-t"><span>Исполнитель{artist ? ` · ${artist.name}` : ""}</span>
            <small>{artist ? "поёт ваш сохранённый исполнитель" : "один голос во всех ваших песнях"}</small></span><Icon n="chevron" s={15} />
        </button>)}
      {!vj && vocal && !artist && <Opts label="Голос" value={voices} onChange={setVoices}
        hint={{ auto: "ИИ решит по смыслу песни", male: "", female: "", duet: "ИИ распределит части" }[voices]}
        options={[{ v: "auto", t: "Авто" }, { v: "male", t: "Мужской" }, { v: "female", t: "Женский" }, { v: "duet", t: "Дуэт" }]} />}
      {!vj && <Opts label="Длина" value={length} onChange={setLength} hint={length ? "примерно" : "ИИ решит сам"} options={LENGTHS} />}
      <label className="field">
        <span className="opts-h"><span>Без чего</span><small>необязательно</small></span>
        <input value={avoid} maxLength={200} onChange={(e) => setAvoid(e.target.value)} placeholder="Например: без гитары, без автотюна" />
      </label>
      {!vj && <Toggle label="Эксперимент" sub={wild ? "модель V6 Wild — смелее и необычнее, результат непредсказуем" : "необычное звучание на модели V6 Wild"} on={wild} onChange={setWild} />}
      {s.active && (
        <section className="card render" aria-label="Идёт генерация">
          <p className="render-p">{s.active.prompt}</p>
          <Progress job={s.active} />
          <p className="muted small">Пишу текст и записываю трек — около 2 минут.</p>
        </section>)}
      {list.length > 0 && (
        <section className="tracks" aria-label="Треки">
          {list.slice(0, 8).flatMap((j) => (j.files || []).filter((f) => f.type === "audio").slice(0, 1).map((f, i) => (
            <Player key={f.url} src={f.url} cover={coverUrl(f)} title={f.title || j.prompt.slice(0, 40)}
              sub={[j.params?.genre, j.params?.instrumental === false
                ? (j.params?.artist_name || VOC[j.params?.brief?.vocals] || "с вокалом") : "инструментал"].filter(Boolean).join(" · ")} onMore={() => setSheet({ j, f })} />)))}
        </section>)}
      <Dock label={vj ? "Создать трек из озвучки" : vocal ? "Создать песню" : "Создать трек"} price={priceOf("music", vj ? { voice_chars: vj.text.length } : {})}
        balance={me?.balance} busy={s.busy} disabled={(!vj && prompt.trim().length < 2) || !!s.active}
        onClick={() => s.run(prompt.trim() || "Трек из озвучки", { genre: genre.join(", "), mood: mood.join(", "),
          instrumental: vj ? false : !vocal, ...(avoid.trim() ? { avoid: avoid.trim() } : {}),
          ...(vj ? { voice_job: vj.id, voices: vjVoices } : { ...(length ? { length } : {}), ...(wild ? { wild } : {}),
            ...(vocal ? (artist ? { artist: artist.id } : { voices }) : {}) }) })} />
      <Sheet open={artPick} onClose={() => setArtPick(false)} title="Исполнитель">
        <h3 className="sheet-title">Кто поёт</h3>
        <button className={"sheet-row" + (!artist ? " accent" : "")} onClick={() => { setArtist(null); setArtPick(false); }}>
          <span className="sr-ic"><Icon n={!artist ? "check" : "spark"} /></span>
          <span className="sr-t"><span>Новый голос</span><small>ИИ подберёт голос под песню</small></span>
        </button>
        {artists === null ? <div className="skeleton" /> : artists.map((a) => (
          <div key={a.id} className={"sheet-row" + (artist?.id === a.id ? " accent" : "")} role="button" tabIndex={0}
            onClick={() => { haptic("select"); setArtist(a); setArtPick(false); }}>
            <span className="sr-ic"><Icon n={artist?.id === a.id ? "check" : "user"} /></span>
            <span className="sr-t"><span>{a.name}</span>{a.style && <small>{a.style}</small>}</span>
            <button className="ic-btn art-del" aria-label={`Удалить исполнителя ${a.name}`} onClick={(e) => { e.stopPropagation(); delArtist(a); }}><Icon n="trash" s={15} /></button>
          </div>))}
        <p className="muted small art-tip">Чтобы добавить исполнителя, откройте готовую песню через «⋯» и нажмите «Сохранить исполнителя».</p>
      </Sheet>
      <Sheet open={pick} onClose={() => setPick(false)} title="Голос из озвучки">
        <h3 className="sheet-title">Выберите озвучку</h3>
        {tts === null ? <div className="skeleton" /> : tts.length === 0 ? (
          <div className="empty-state slim"><p>Озвучек пока нет</p><button className="cta small" onClick={() => go("tts")}>Сделать озвучку</button></div>
        ) : tts.map((j) => (
          <button key={j.id} className="sheet-row" onClick={() => { setVj({ id: j.id, text: j.prompt, voice: j.params?.voice || "" }); setPick(false); }}>
            <span className="sr-ic"><Icon n="wave" /></span>
            <span className="sr-t"><span>{j.prompt}</span><small>{[j.params?.voice, j.params?.tone].filter(Boolean).join(" · ")}</small></span>
          </button>))}
      </Sheet>
      <JobSheet job={sheet?.j} file={sheet?.f} onClose={() => setSheet(null)} go={go} onChange={() => s.reload()}
        onArtist={(a) => { loadArtists(); setArtist(a); setVocal(true); reloadMe?.(); }} />
    </main>);
}
