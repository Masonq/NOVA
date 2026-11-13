import { useEffect, useState } from "react";
import Icon from "../ui/Icon.jsx";
import { openTopup } from "../ui/Topup.jsx";
import { toast } from "../ui/Toast.jsx";
import { api, auth } from "../api.js";
import { inTelegram, haptic, tg } from "../tg.js";

const fmt = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export default function Profile({ me, reload, go }) {
  const [led, setLed] = useState(null);
  const [mem, setMem] = useState(null);
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
      <header className="bar"><h1>Профиль</h1></header>
      <section className="card bal">
        <div><span className="muted small">Баланс</span><b>{me?.balance ?? "…"} <small>кредитов</small></b></div>
        <button className="cta small" onClick={() => openTopup()}>Пополнить</button>
      </section>
      <PromoBox reloadMe={reload} onDone={() => api("/api/me/ledger").then(setLed).catch(() => {})} />
      <Invite />
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


function Invite() {
  const [r, setR] = useState(null);
  useEffect(() => { api("/api/me/referral").then(setR).catch(() => {}); }, []);
  if (!r) return null;
  const text = `Попробуй NOVA — голосовой ИИ-агент: картинки, видео и музыка одной фразой. По моей ссылке +${r.friend_bonus} кредитов`;
  const share = async () => {
    haptic("light");
    if (tg?.openTelegramLink && tg.initData) { tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(r.link)}&text=${encodeURIComponent(text)}`); return; }
    try { if (navigator.share) { await navigator.share({ url: r.link, text }); return; } } catch (e) { if (e?.name === "AbortError") return; }
    try { await navigator.clipboard.writeText(r.link); toast("Ссылка скопирована"); } catch { toast(r.link); }
  };
  return (
    <section className="card invite">
      <div className="inv-h"><span className="inv-ic"><Icon n="gift" s={20} /></span>
        <span className="sr-t"><b>Пригласите друга</b><small>Другу +{r.friend_bonus} кредитов сразу, вам +{r.bonus} после его первой покупки</small></span></div>
      <div className="inv-stats"><span><b>{r.invited}</b>пришли</span><span><b>{r.paid}</b>купили</span><span><b>+{r.earned}</b>заработано</span></div>
      <button className="cta wide" onClick={share}>Поделиться ссылкой</button>
    </section>);
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
