import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { openTopup } from "../ui/Topup.jsx";
import { toast } from "../ui/Toast.jsx";
import { api, auth } from "../api.js";
import { inTelegram, haptic } from "../tg.js";

const fmt = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export default function Profile({ me, reload, go }) {
  const [led, setLed] = useState(null);
  const [mem, setMem] = useState(null);
  useEffect(() => {
    api("/api/me/ledger").then(setLed).catch(() => setLed([]));
    api("/api/me/memory").then(setMem).catch(() => setMem([]));
  }, []);
  const forget = async (id) => { haptic("select"); await api(`/api/me/memory/${id}`, { method: "DELETE" }).catch(() => {}); setMem((m) => m.filter((x) => x.id !== id)); };
  const forgetAll = async () => { if (!window.confirm("Стереть всё, что агент о вас помнит?")) return; await api("/api/me/memory", { method: "DELETE" }); setMem([]); };
  const del = async () => {
    if (!window.confirm("Удалить аккаунт? Пропадут кредиты, работы, переписка и память. Это нельзя отменить.")) return;
    await api("/api/me", { method: "DELETE" }); auth.clear(); location.reload();
  };
  return (
    <main className="screen profile">
      <header className="bar"><h1>Профиль</h1></header>
      <section className="card bal">
        <div><span className="muted small">Баланс</span><b>{me?.balance ?? "…"} <small>кредитов</small></b></div>
        <button className="cta small" onClick={() => openTopup()}>Пополнить</button>
      </section>
      <PromoBox reloadMe={reload} onDone={() => api("/api/me/ledger").then(setLed).catch(() => {})} />
      {me?.is_admin && (
        <button className="row-btn adm-entry" onClick={() => go("admin")}><Icon n="spark" />Админка<Icon n="chevron" s={15} /></button>)}
      <section aria-labelledby="mem-h">
        <div className="row-h"><h2 id="mem-h">Что я о вас знаю</h2>{mem?.length > 0 && <button className="link danger" onClick={forgetAll}>Забыть всё</button>}</div>
        {mem?.length === 0 && <p className="muted small pad">Пока ничего. Агент будет запоминать важное из разговоров — всё можно удалить здесь.</p>}
        <ul className="list">{mem?.map((m) => (
          <li key={m.id}><span>{m.text}</span><button className="ic-btn" aria-label="Забыть" onClick={() => forget(m.id)}><Icon n="x" s={15} /></button></li>))}</ul>
      </section>
      <section aria-labelledby="led-h">
        <div className="row-h"><h2 id="led-h">История</h2></div>
        <ul className="list">{led?.map((r) => (
          <li key={r.id}><span><b className="t">{r.title}</b><span className="muted small">{fmt.format(new Date(r.at))}</span></span>
            <span className={"delta " + (r.delta > 0 ? "plus" : "")}>{r.delta > 0 ? "+" : ""}{r.delta}</span></li>))}</ul>
      </section>
      <section className="danger-zone">
        {!inTelegram && <button className="row-btn" onClick={() => { auth.clear(); location.reload(); }}><Icon n="logout" />Выйти</button>}
        <button className="row-btn danger" onClick={del}><Icon n="trash" />Удалить аккаунт</button>
      </section>
    </main>);
}


function PromoBox({ reloadMe, onDone }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    if (busy || code.trim().length < 3) return;
    setBusy(true);
    try {
      const r = await api("/api/me/promo", { method: "POST", body: { code: code.trim() } });
      haptic("success"); toast(`Промокод активирован: +${r.credits} кредитов`); setCode(""); reloadMe?.(); onDone?.();
    } catch (e) { haptic("error"); toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <div className="promo">
      <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ""))} onKeyDown={(e) => e.key === "Enter" && apply()}
        placeholder="Промокод" aria-label="Промокод" maxLength={32} autoCapitalize="characters" />
      <button className="row-btn" disabled={busy || code.trim().length < 3} onClick={apply}>{busy ? "…" : "Применить"}</button>
    </div>);
}
