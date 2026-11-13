import { openTopup } from "../ui/Topup.jsx";
import { PRICE } from "../jobs.js";
import { useEffect, useRef, useState } from "react";
import Icon from "../ui/Icon.jsx";
import Composer from "../ui/Composer.jsx";
import { toast } from "../ui/Toast.jsx";
import { api, stream } from "../api.js";
import { haptic } from "../tg.js";

export default function Chat({ go, params }) {
  const [msgs, setMsgs] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const ctrl = useRef(null);
  const sentDraft = useRef(false);

  const send = async (t) => {
    setText(""); setBusy(true);
    setMsgs((m) => [...(m || []), { role: "user", text: t, id: "u" + Date.now() }, { role: "model", text: "", id: "m" + Date.now(), live: true }]);
    ctrl.current = new AbortController();
    try {
      await stream("/api/chat", { text: t }, (e) => {
        if (e.t) setMsgs((m) => { const c = [...m]; const l = c[c.length - 1]; c[c.length - 1] = { ...l, text: l.text + e.t }; return c; });
        if (e.error) { toast(e.error, "error"); setMsgs((m) => m.slice(0, -1)); }
      }, ctrl.current.signal);
      haptic("success");
    } catch (e) {
      if (e.name !== "AbortError") {
        setMsgs((m) => m.slice(0, -2)); setText(t);
        if (e.status === 402) openTopup(PRICE.chat_msg); else toast(e.message, "error");
      }
    } finally {
      setBusy(false);
      setMsgs((m) => m && m.map((x) => (x.live ? { ...x, live: false } : x)));
    }
  };

  useEffect(() => {
    api("/api/chat").then((h) => {
      setMsgs(h);
      if (params?.draft && !sentDraft.current) { sentDraft.current = true; send(params.draft); }
    }).catch((e) => { setMsgs([]); toast(e.message, "error"); });
    return () => ctrl.current?.abort();
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs]);

  const clear = async () => {
    if (!window.confirm("Очистить переписку?")) return;
    await api("/api/chat", { method: "DELETE" }).catch(() => {});
    setMsgs([]);
  };
  return (
    <main className="screen chat">
      <header className="bar">
        <button className="ic-btn" aria-label="Назад" onClick={() => go("home")}><Icon n="back" /></button>
        <h1>Чат</h1>
        {msgs?.length > 0 && <button className="link" onClick={clear}>Очистить</button>}
      </header>
      <div className="msgs" aria-live="polite">
        {msgs === null && <div className="skeleton" />}
        {msgs?.length === 0 && <p className="muted center">Спросите что угодно или опишите, что нужно создать.</p>}
        {msgs?.map((m) => m.role === "user"
          ? <div key={m.id} className="bubble">{m.text}</div>
          : <div key={m.id} className="answer"><span className="who"><i />NOVA</span>
              <p>{m.text}{m.live && <span className="cursor" aria-hidden="true" />}</p></div>)}
        <div ref={end} />
      </div>
      <div className="dock"><Composer value={text} onChange={setText} onSend={send} busy={busy} placeholder={`Сообщение · ${PRICE.chat_msg} кр.`} /></div>
    </main>);
}
