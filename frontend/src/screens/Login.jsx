import { useEffect, useRef, useState } from "react";
import qrcode from "qrcode-generator";
import { api, auth } from "../api.js";
import { openLink } from "../tg.js";
import Orb from "../ui/Orb.jsx";

// a computer is recognised by its mouse, not by the window width (a narrow browser window is still a computer)
const desktop = typeof window !== "undefined" && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

function QR({ text }) {
  const svg = (() => { const q = qrcode(0, "M"); q.addData(text); q.make(); return q.createSvgTag({ cellSize: 6, margin: 0, scalable: true }); })();
  return <div className="qr" aria-label="QR-код для входа" dangerouslySetInnerHTML={{ __html: svg }} />;
}

/** Sign-in outside Telegram: a one-time code confirmed in the bot. On a computer — scan the QR with the phone. */
export default function Login({ onDone }) {
  const [code, setCode] = useState(null);
  const [state, setState] = useState("idle"); // idle | waiting | expired | error
  const [err, setErr] = useState("");
  const [showQr, setShowQr] = useState(desktop);
  const timer = useRef();
  useEffect(() => () => clearInterval(timer.current), []);

  const fresh = async (open) => {
    setErr(""); setState("waiting");
    try {
      const c = await api("/api/auth/code", { method: "POST" });
      setCode(c);
      if (open) openLink(c.link);
      clearInterval(timer.current);
      const until = Date.now() + c.ttl * 1000;
      timer.current = setInterval(async () => {
        if (Date.now() > until) { clearInterval(timer.current); setState("expired"); return; }
        try {
          const r = await api(`/api/auth/code/${c.code}`);
          if (r.status === "ok") { clearInterval(timer.current); auth.set(r.token); onDone(); }
        } catch (e) { clearInterval(timer.current); setState("error"); setErr(e.message); }
      }, 2000);
    } catch (e) { setState("error"); setErr(e.message); }
  };
  useEffect(() => { if (desktop) fresh(false); }, []);

  return (
    <main className={"login" + (desktop ? " desk" : "")}>
      <div className="login-orb"><Orb size={desktop ? 150 : 180} dense /></div>
      <h1>NOVA</h1>
      <p className="muted">Голосовой ИИ-агент: картинки, видео, музыка и&nbsp;озвучка в&nbsp;одном месте.</p>
      {showQr && code && state !== "expired" && (
        <div className="qr-card">
          <QR text={code.link} />
          <ol className="qr-steps"><li>В&nbsp;Telegram откройте NOVA → Профиль → «Войти на&nbsp;компьютере»</li><li>Наведите сканер на&nbsp;код и&nbsp;подтвердите</li><li>Эта страница войдёт сама</li></ol>
        </div>)}
      {showQr && state === "expired" && <button className="cta" onClick={() => fresh(false)}>Обновить код</button>}
      {!desktop && <button className="cta" onClick={() => fresh(true)}>{state === "waiting" && !showQr ? "Ждём подтверждения в Telegram…" : "Войти через Telegram"}</button>}
      {desktop && code && <p className="muted small qr-alt">Или наведите камеру телефона и нажмите «Старт» в боте. <button className="link" onClick={() => openLink(code.link)}>Открыть Telegram на компьютере</button></p>}
      {!desktop && state === "waiting" && !showQr && <p className="muted small">Нажмите «Старт» в боте — страница войдёт сама. <button className="link" onClick={() => fresh(true)}>Открыть бота снова</button></p>}
      {!desktop && !showQr && <button className="link" onClick={() => { setShowQr(true); fresh(false); }}>Показать QR-код для входа с другого устройства</button>}
      {err && <p className="err">{err}</p>}
    </main>);
}
