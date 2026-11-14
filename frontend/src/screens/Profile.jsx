import { useEffect, useState } from "react";
import Count from "../ui/Count.jsx";
import Icon from "../ui/Icon.jsx";
import { openTopup } from "../ui/Topup.jsx";
import { toast } from "../ui/Toast.jsx";
import { api, auth } from "../api.js";
import { inTelegram, haptic, tg } from "../tg.js";
import Sheet from "../ui/Sheet.jsx";
import { PRICE } from "../jobs.js";
import Art3D from "../ui/Art3D.jsx";
import { CreditCard, Gift, Ticket, ClockCounterClockwise } from "@phosphor-icons/react";

const tfmt = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const dfmt = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
const dayKey = (d) => d.toDateString();
const dayName = (d) => {
  const t = new Date(), y = new Date(t); y.setDate(t.getDate() - 1);
  return dayKey(d) === dayKey(t) ? "Сегодня" : dayKey(d) === dayKey(y) ? "Вчера" : dfmt.format(d);
};
// one line per entry, grouped by day; same-titled neighbours (old per-turn agent charges) fold into «×N»
function groupLedger(rows) {
  const days = [];
  for (const r of rows || []) {
    const d = new Date(r.at), k = dayKey(d);
    let day = days[days.length - 1];
    if (!day || day.k !== k) days.push(day = { k, name: dayName(d), items: [] });
    const last = day.items[day.items.length - 1];
    if (last && last.title === r.title && Math.sign(last.delta) === Math.sign(r.delta)) { last.delta += r.delta; last.n += 1; continue; }
    day.items.push({ ...r, n: 1, time: tfmt.format(d) });
  }
  return days;
}
const PAGE = 20;
export default function Profile({ me, reload, go }) {
  const [led, setLed] = useState(null);
  const [mem, setMem] = useState(null);
  const [more, setMore] = useState(false);
  const [promo, setPromo] = useState(false);
  const toHistory = () => document.getElementById("led-h")?.scrollIntoView({ behavior: "smooth", block: "start" });
  useEffect(() => {
    if (location.hash.includes("topup=card")) {           // came from Telegram to pay by card
      history.replaceState(null, "", location.pathname + "#/profile");
      setTimeout(() => openTopup(0, "yookassa"), 350);
    }
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
      <section className="pf-hero" aria-label="Баланс">
        <span className="pf-cap">Баланс</span>
        <b className="pf-bal"><Count value={me?.balance} /></b>
        <span className="pf-unit">кредитов{me?.name ? ` · ${me.name}` : ""}</span>
        <div className="pf-acts">
          {[[CreditCard, "Пополнить", () => openTopup()], [Gift, "Пригласить", () => go("invite", { from: "profile" })],
            [Ticket, "Промокод", () => setPromo(true)], [ClockCounterClockwise, "История", toHistory]].map(([G, t, fn]) => (
            <button key={t} className="pf-act" onClick={() => { haptic("light"); fn(); }}><G size={22} weight="duotone" /><span>{t}</span></button>))}
        </div>
      </section>
      <button className="inv-row" onClick={() => { haptic("light"); go("invite", { from: "profile" }); }}>
        <Art3D name="gift" size={52} className="inv-art" />
        <span className="sr-t"><b>Пригласите друзей</b><small>+{PRICE.ref_bonus ?? 100} кредитов за каждого, кто пополнит баланс</small></span>
        <Icon n="chevron" s={15} />
      </button>
      <Sheet open={promo} onClose={() => setPromo(false)} title="Промокод">
        <h3 className="sheet-title">Промокод</h3>
        <PromoBox reloadMe={reload} onDone={() => { setPromo(false); api("/api/me/ledger").then(setLed).catch(() => {}); }} />
      </Sheet>
      <DesktopLogin />
      <Install />
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
        {led === null && <div className="led-day">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton line" />)}</div>}
        {(() => {
          let left = more ? Infinity : PAGE, total = 0;
          const days = groupLedger(led);
          days.forEach((d) => { total += d.items.length; });
          return (<>
            {days.map((d) => {
              if (left <= 0) return null;
              const items = d.items.slice(0, left); left -= items.length;
              return (<div className="led-day" key={d.k}>
                <div className="led-dh">{d.name}</div>
                <ul className="led">{items.map((r) => (
                  <li key={r.id}>
                    <span className="led-t">{r.title}{r.n > 1 && <em> ×{r.n}</em>}</span>
                    <span className="led-time">{r.time}</span>
                    <span className={"led-d " + (r.delta > 0 ? "plus" : "")}>{r.delta > 0 ? "+" : ""}{r.delta}</span>
                  </li>))}</ul>
              </div>);
            })}
            {!more && total > PAGE && <button className="led-more" onClick={() => { haptic("select"); setMore(true); }}>Показать всё</button>}
            {led && !led.length && <p className="muted small">Пока пусто</p>}
          </>);
        })()}
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


function Install() {
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const [prompt, setPrompt] = useState(() => window.__installPrompt || null);
  const [help, setHelp] = useState(false);
  useEffect(() => { const f = () => setPrompt(window.__installPrompt); window.addEventListener("nova:installable", f); return () => window.removeEventListener("nova:installable", f); }, []);
  if (inTelegram || standalone || (!prompt && !ios)) return null;
  const go = async () => {
    if (prompt) { prompt.prompt(); const r = await prompt.userChoice.catch(() => null); if (r?.outcome === "accepted") { window.__installPrompt = null; setPrompt(null); } return; }
    setHelp((h) => !h);
  };
  return (
    <section className="card install">
      <button className="row-btn" onClick={go}><Icon n="download" />Установить NOVA на телефон<Icon n="chevron" s={15} /></button>
      {help && <p className="muted small inst-help">В Safari нажмите <b>«Поделиться»</b> внизу экрана, затем <b>«На экран „Домой“»</b>. NOVA откроется как приложение — без адресной строки.</p>}
    </section>);
}


/** Sign in on a computer: scan the QR on the NOVA website with Telegram's scanner, check the device, confirm. */
function DesktopLogin() {
  const can = inTelegram && typeof tg?.showScanQrPopup === "function";
  if (!can) return null;
  const confirm = (info) => {
    const text = `Войти в NOVA на этом устройстве?\n\n${info.device}${info.ip ? `\nIP ${info.ip}` : ""}\nКод создан ${info.ago}\n\nПодтверждайте, только если это ваш компьютер.`;
    tg.showConfirm(text, async (ok) => {
      if (!ok) return;
      try { await api("/api/auth/scan/confirm", { method: "POST", body: { code: info.code } }); haptic("success"); toast("Готово — компьютер вошёл в NOVA"); }
      catch (e) { haptic("error"); toast(e.message, "error"); }
    });
  };
  const scan = () => {
    haptic("light");
    let busy = false;
    tg.showScanQrPopup({ text: "Наведите на QR-код на сайте NOVA" }, (text) => {
      if (busy || !/login_|^[A-Za-z0-9_-]{16,40}$/.test(text || "")) return false;    // keep scanning until our code shows up
      busy = true;
      api("/api/auth/scan", { method: "POST", body: { qr: text } })
        .then(confirm).catch((e) => { haptic("error"); toast(e.message, "error"); });
      return true;                                                                       // closes the scanner
    });
  };
  return (
    <section className="install">
      <button className="row-btn" onClick={scan}><Icon n="qr" />Войти на компьютере<span className="muted small rb-sub">сканер QR</span><Icon n="chevron" s={15} /></button>
    </section>);
}
