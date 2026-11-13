import { useEffect, useRef, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { openTopup } from "../ui/Topup.jsx";
import Orb from "../ui/Orb.jsx";
import Sheet, { JobSheet } from "../ui/Sheet.jsx";
import { Progress } from "../ui/Studio.jsx";
import { Voice } from "../agent/voice.js";
import { api, stream } from "../api.js";
import { toast } from "../ui/Toast.jsx";
import { haptic } from "../tg.js";
import { kickJobs, useActiveJobs, KIND, thumbOf, PRICE } from "../jobs.js";

const STATUS = {
  off: "Коснитесь сферы, чтобы начать разговор",
  idle: "Говорите — я слушаю",
  listening: "Слушаю…",
  thinking: "Думаю…",
  speaking: "Отвечаю · коснитесь, чтобы перебить",
  muted: "Микрофон выключен",
};
const WHAT = { image: "Картинка", video: "Видео", music: "Трек", tts: "Озвучка" };

export default function Agent({ go, me, reloadMe }) {
  const [phase, setPhase] = useState("off");
  const [muted, setMuted] = useState(false);
  const [heard, setHeard] = useState("");
  const [answer, setAnswer] = useState("");
  const [steps, setSteps] = useState([]);
  const [confirm, setConfirm] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [cards, setCards] = useState([]);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const [settings, setSettings] = useState(null);
  const [pick, setPick] = useState(false);
  const [sheet, setSheet] = useState(null);
  const voice = useRef(null);
  const ctrl = useRef(null);
  const levelFn = useRef(() => voice.current?.level || 0).current;
  const active = useActiveJobs((fin) => setJobs((js) => js.map((j) => (j.id === fin.id ? fin : j))));

  useEffect(() => {
    api("/api/agent/settings").then(setSettings).catch(() => {});
    return () => { ctrl.current?.abort(); voice.current?.stop(); };
  }, []);

  const send = async (payload) => {
    ctrl.current?.abort();
    const ac = new AbortController(); ctrl.current = ac;
    voice.current?.newTurn();
    setPhase("thinking"); setAnswer(""); setSteps([]); setCards([]);
    if (payload.text) setHeard(payload.text);
    let gotAudio = false;
    try {
      await stream("/api/agent/turn", payload, (e) => {
        if (ac.signal.aborted) return;
        if (e.type === "heard") setHeard(e.text || "Не расслышала — повторите, пожалуйста");
        else if (e.type === "text") setAnswer((a) => a + e.t);
        else if (e.type === "audio") { gotAudio = true; voice.current?.enqueue(e.seq, e.url); }
        else if (e.type === "step") setSteps((s) => e.done ? s.map((x) => x.text === e.text ? { ...x, done: true } : x) : [...s, { text: e.text, done: false }]);
        else if (e.type === "confirm") { setConfirm(e); haptic("light"); }
        else if (e.type === "confirm_cancel") setConfirm(null);
        else if (e.type === "job") { setConfirm(null); setJobs((j) => [e.job, ...j]); kickJobs(); haptic("success"); }
        else if (e.type === "cards") setCards(e.jobs);
        else if (e.type === "memory") toast(`Запомнила: ${e.text}`);
        else if (e.type === "error") toast(e.text, "error");
        else if (e.type === "notice") toast(e.text);
        else if (e.type === "done") { reloadMe?.(); }
      }, ac.signal);
    } catch (er) {
      if (er.name !== "AbortError") { toast(er.message, "error"); setPhase(muted ? "muted" : "idle"); }
      return;
    }
    if (ac.signal.aborted) return;
    voice.current?.endTurn();
    if (!gotAudio) setPhase(muted ? "muted" : "idle");
  };

  const begin = async () => {
    if (voice.current) { if (phase === "speaking") voice.current.stopPlayback(); return; }
    haptic("medium");
    const v = new Voice({
      onUtterance: (w) => send({ audio: w.b64 }),
      onBargeIn: () => { ctrl.current?.abort(); navigator.sendBeacon?.("/api/agent/barge"); },     // visible in the server log
      onState: (s) => setPhase((p) => (s === "idle" ? (p === "thinking" ? p : "idle") : s)),
    });
    try { await v.start(); voice.current = v; setPhase("idle"); }
    catch { toast("Нужен доступ к микрофону — разрешите его в настройках и попробуйте снова", "error"); v.stop(); }
  };

  const toggleMute = () => {
    const m = !muted; setMuted(m); voice.current?.setMuted(m); haptic("select");
    if (phase === "idle" || phase === "muted") setPhase(m ? "muted" : "idle");
  };
  const sendText = () => { const t = text.trim(); if (!t) return; setText(""); setTyping(false); send({ text: t }); };
  const setVoice = async (id) => { const r = await api("/api/agent/settings", { method: "PUT", body: { voice: id } }); setSettings((s) => ({ ...s, voice: r.voice })); toast("Голос выбран"); };
  const vname = settings?.voices?.find((v) => v.id === settings.voice)?.name;
  const liveJobs = jobs.map((j) => active.find((a) => a.id === j.id) || j);
  const orbSize = Math.min(300, (typeof window !== "undefined" ? window.innerWidth : 390) - 70);

  return (
    <main className={"agent ph-" + phase}>
      <header className="ag-top">
        <button className="ic-btn back-btn" aria-label="Назад" onClick={() => go("home")}><Icon n="back" /></button>
        <button className="ag-voice" onClick={() => setPick(true)} aria-label="Выбрать голос"><Icon n="wave" s={15} />{vname ? vname[0].toUpperCase() + vname.slice(1) : "Голос"}</button>
        <span className="balance" role="button" tabIndex={0} onClick={() => openTopup()} aria-label={`Баланс ${me?.balance ?? 0} кредитов, пополнить`}><Icon n="spark" s={14} w={2} />{me?.balance ?? "…"}</span>
      </header>

      <section className={"ag-stage" + (heard || answer || confirm || jobs.length ? " compact" : "")}>
        <button className="ag-orb" onClick={begin} aria-label={phase === "off" ? "Начать разговор" : phase === "speaking" ? "Перебить" : "Сфера агента"}>
          <Orb size={orbSize} dense level={levelFn} energy={phase === "thinking" ? 0.35 : 0} pulseOnTap={false} />
        </button>
        <p className="ag-status" aria-live="polite">{STATUS[phase]}</p>
        {phase === "off" && <p className="ag-hint">Разговор — {settings?.per_min ?? 5} кредитов в минуту, поиск в интернете +{PRICE.agent_search}. Генерации запускаю только после вашего «да».</p>}
      </section>

      <section className="ag-talk" aria-live="polite">
        {heard && <p className="ag-heard appear" key={heard}>{heard}</p>}
        {answer && <p className="ag-answer appear">{answer}</p>}
        {steps.length > 0 && <ul className="ag-steps">{steps.map((s, i) => <li key={i} className={s.done ? "done" : ""}><i>{s.done ? <Icon n="check" s={11} w={3} /> : null}</i>{s.text}</li>)}</ul>}

        {confirm && (
          <div className="card ag-confirm appear">
            <div className="agc-h"><span className={"tag k-" + confirm.kind}>{WHAT[confirm.kind]}</span><b>{confirm.cost} кр.</b></div>
            <p>{confirm.prompt}</p>
            {confirm.cost > confirm.balance
              ? <button className="cta wide" onClick={() => openTopup(confirm.cost - confirm.balance)}>Пополнить баланс</button>
              : <div className="agc-b"><button className="row-btn" onClick={() => send({ text: "нет, не надо" })}>Отмена</button>
                  <button className="cta" onClick={() => send({ text: "да, запускай" })}>Запустить</button></div>}
          </div>)}

        {liveJobs.map((j) => (
          <div key={j.id} className="card ag-job appear">
            <div className="agc-h"><span className={"tag k-" + j.kind}>{WHAT[j.kind]}</span><span className="agj-p">{j.prompt}</span></div>
            {j.status === "done" ? <button className="link" onClick={() => go(j.kind)}>Открыть результат</button>
              : j.status === "failed" ? <p className="muted small">Не получилось — кредиты вернулись на баланс</p>
              : <Progress job={j} />}
          </div>))}

        {cards.length > 0 && (
          <div className="ag-cards appear">{cards.map((j) => {
            const th = thumbOf(j);
            return <button key={j.id} className={"ag-card k-" + j.kind} style={th ? { backgroundImage: `url(${th})` } : undefined} onClick={() => setSheet(j)}>
              {!th && <Icon n={j.kind === "music" ? "music" : "wave"} s={22} />}<span>{KIND[j.kind]}</span></button>;
          })}</div>)}
      </section>

      <footer className="ag-dock">
        {typing ? (
          <div className="ag-type">
            <input autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendText()} placeholder="Напишите агенту" aria-label="Сообщение агенту" maxLength={2000} />
            <button className="send" aria-label="Отправить" onClick={sendText} disabled={!text.trim()}><Icon n="send" s={18} /></button>
            <button className="ic-btn" aria-label="Закрыть ввод" onClick={() => setTyping(false)}><Icon n="x" s={16} /></button>
          </div>
        ) : (
          <>
            <button className={"ag-btn" + (muted ? " on" : "")} onClick={toggleMute} disabled={!voice.current} aria-label={muted ? "Включить микрофон" : "Выключить микрофон"}>
              <Icon n={muted ? "micoff" : "mic"} s={21} /></button>
            <button className="ag-btn" onClick={() => setTyping(true)} aria-label="Написать текстом"><Icon n="keyboard" s={21} /></button>
            <button className="ag-btn end" onClick={() => go("home")} aria-label="Завершить разговор"><Icon n="x" s={21} /></button>
          </>)}
      </footer>

      <Sheet open={pick} onClose={() => setPick(false)} title="Голос агента">
        <h3 className="sheet-title">Голос NOVA</h3>
        {settings?.voices?.map((v) => (
          <button key={v.id} className={"sheet-row" + (settings.voice === v.id ? " accent" : "")} onClick={() => setVoice(v.id)}>
            <span className="sr-ic"><Icon n={settings.voice === v.id ? "check" : "wave"} /></span>
            <span className="sr-t"><span>{v.name[0].toUpperCase() + v.name.slice(1)}</span><small>{v.id}</small></span>
            <span className="v-play" role="button" tabIndex={0} aria-label={`Послушать: ${v.name}`} onClick={async (e) => {
              e.stopPropagation();
              try { const { url } = await api(`/api/voices/${v.id}/sample`); new Audio(url).play(); } catch (er) { toast(er.message, "error"); }
            }}><Icon n="play" s={13} /></span>
          </button>))}
      </Sheet>
      <JobSheet job={sheet} onClose={() => setSheet(null)} go={go} onChange={() => {}} />
    </main>);
}
