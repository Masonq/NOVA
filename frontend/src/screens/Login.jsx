import { useEffect, useRef, useState } from "react";
import { api, auth } from "../api.js";
import { openLink } from "../tg.js";

export default function Login({ onDone }) {
  const [state, setState] = useState("idle"); // idle | waiting | error
  const [err, setErr] = useState("");
  const timer = useRef();
  useEffect(() => () => clearInterval(timer.current), []);
  const start = async () => {
    setErr(""); setState("waiting");
    try {
      const c = await api("/api/auth/code", { method: "POST" });
      openLink(c.link);
      clearInterval(timer.current);
      timer.current = setInterval(async () => {
        try {
          const r = await api(`/api/auth/code/${c.code}`);
          if (r.status === "ok") { clearInterval(timer.current); auth.set(r.token); onDone(); }
        } catch (e) {
          clearInterval(timer.current); setState("error"); setErr(e.message);
        }
      }, 2000);
    } catch (e) { setState("error"); setErr(e.message); }
  };
  return (
    <main className="login">
      <div className="login-mark" aria-hidden="true" />
      <h1>NOVA</h1>
      <p className="muted">Голосовой ИИ-агент: картинки, видео, музыка и озвучка в одном месте.</p>
      <button className="cta" onClick={start}>{state === "waiting" ? "Ждём подтверждения в Telegram…" : "Войти через Telegram"}</button>
      {state === "waiting" && <p className="muted small">Нажмите «Старт» в боте — страница войдёт сама. <button className="link" onClick={start}>Открыть бота снова</button></p>}
      {err && <p className="err">{err}</p>}
    </main>);
}
