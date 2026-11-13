import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";
import { toast } from "./Toast.jsx";

export default function Composer({ value, onChange, onSend, busy, placeholder = "Что создать?", autoFocus }) {
  const ref = useRef(null);
  const [mode, setMode] = useState("text");
  useEffect(() => {
    const el = ref.current; if (!el) return;
    el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, [value]);
  const send = () => {
    const t = value.trim();
    if (!t || busy) return;
    haptic("light"); onSend(t);
  };
  const voice = () => { haptic("select"); setMode("text"); toast("Голосовой ввод появится в следующем обновлении"); };
  return (
    <div className="composer">
      <button className="ic-btn sq" aria-label="Добавить фото, файл или камеру" onClick={() => toast("Фото и файлы появятся в следующем обновлении")}>
        <Icon n="plus" />
      </button>
      <label className="sr" htmlFor="composer-input">Сообщение</label>
      <textarea id="composer-input" ref={ref} rows={1} value={value} placeholder={placeholder} autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      <span className="seg" role="group" aria-label="Способ ввода">
        <button className={mode === "text" ? "on" : ""} aria-label="Печатать" aria-pressed={mode === "text"} onClick={() => setMode("text")}>Aa</button>
        <button className={mode === "voice" ? "on" : ""} aria-label="Говорить" aria-pressed={mode === "voice"} onClick={voice}><Icon n="wave" s={15} /></button>
      </span>
      <button className="send" aria-label="Отправить" disabled={!value.trim() || busy} onClick={send}><Icon n="send" w={2.2} /></button>
    </div>);
}
