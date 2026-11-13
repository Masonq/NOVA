import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { upload } from "../api.js";
import { toast } from "./Toast.jsx";
import { haptic } from "../tg.js";
import { openTopup } from "./Topup.jsx";

export function StudioTop({ title, me, go }) {
  return (
    <header className="bar studio-top">
      <button className="ic-btn" aria-label="Назад" onClick={() => go("home")}><Icon n="back" /></button>
      <h1>{title}</h1>
      <span className="balance" role="button" tabIndex={0} onClick={() => openTopup()} aria-label={`Баланс ${me?.balance ?? 0} кредитов, пополнить`}><Icon n="spark" s={14} w={2} />{me?.balance ?? "…"}</span>
    </header>);
}

export function Opts({ label, value, options, onChange, hint }) {
  return (
    <div className="opts" role="group" aria-label={label}>
      <div className="opts-h"><span>{label}</span>{hint && <small>{hint}</small>}</div>
      <div className="opts-row">
        {options.map((o) => {
          const v = typeof o === "object" ? o.v : o, t = typeof o === "object" ? o.t : o;
          return <button key={String(v)} className={"opt" + (value === v ? " on" : "")} aria-pressed={value === v}
            onClick={() => { haptic("select"); onChange(v); }}>{t}</button>;
        })}
      </div>
    </div>);
}

export function Toggle({ label, sub, on, onChange }) {
  return (
    <button className="toggle-row" role="switch" aria-checked={on} onClick={() => { haptic("select"); onChange(!on); }}>
      <span className="sr-t"><span>{label}</span>{sub && <small>{sub}</small>}</span>
      <span className={"switch" + (on ? " on" : "")} aria-hidden="true"><i /></span>
    </button>);
}

export function PromptBox({ value, onChange, placeholder, max, attach, onAttach, attachLabel = "Фото" }) {
  const ref = useRef(null);
  const file = useRef(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { const t = ref.current; if (t) { t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 220) + "px"; } }, [value]);
  const pick = async (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    setBusy(true);
    try { onAttach(await upload(f)); haptic("light"); } catch (er) { toast(er.message, "error"); } finally { setBusy(false); }
  };
  return (
    <div className="pbox">
      <textarea ref={ref} rows={3} value={value} maxLength={max} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-label={placeholder} />
      <div className="pbox-foot">
        {onAttach && (attach
          ? <span className="att" style={{ backgroundImage: `url(${attach})` }}><button aria-label="Убрать фото" onClick={() => onAttach(null)}><Icon n="x" s={12} w={2.4} /></button></span>
          : <button className="att-add" onClick={() => file.current?.click()} disabled={busy}><Icon n="clip" s={15} />{busy ? "Загружаю…" : attachLabel}</button>)}
        <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick} />
        {max && <span className="count">{value.length} / {max}</span>}
      </div>
    </div>);
}

export function Dock({ label, price, balance, disabled, onClick, busy }) {
  const short = balance != null && price > balance;
  return (
    <div className="dock studio-dock">
      <button className={"cta wide" + (short ? " short" : "")} disabled={disabled || busy} onClick={short ? () => openTopup(price - balance) : onClick}>
        {busy ? "Запускаю…" : short ? <>Пополнить баланс<span className="cta-price"><Icon n="spark" s={13} w={2.2} />{price}</span></> : <>{label}<span className="cta-price"><Icon n="spark" s={13} w={2.2} />{price}</span></>}
      </button>
    </div>);
}

export function Progress({ job, steps }) {
  const idx = steps ? Math.max(0, steps.findIndex((s) => s.match.includes(job.stage))) : -1;
  return (
    <div className="prog" aria-live="polite">
      {steps && (
        <ol className="steps">
          {steps.map((s, i) => <li key={s.t} className={i < idx ? "done" : i === idx ? "now" : ""}><i>{i < idx ? <Icon n="check" s={11} w={3} /> : null}</i><span>{s.t}</span></li>)}
        </ol>)}
      <div className="bar-line"><i style={{ width: `${job.progress}%` }} /></div>
      <div className="prog-t"><span>{job.stage}</span><span>{job.progress}%</span></div>
    </div>);
}
