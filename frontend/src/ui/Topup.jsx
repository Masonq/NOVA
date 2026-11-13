import { useEffect, useState } from "react";
import Sheet from "./Sheet.jsx";
import Icon from "./Icon.jsx";
import { api } from "../api.js";
import { tg, haptic } from "../tg.js";
import { toast } from "./Toast.jsx";

/** Anywhere in the app: openTopup() shows the credit packs. */
export const openTopup = (need) => window.dispatchEvent(new CustomEvent("nova:topup", { detail: { need } }));

const fmt = (n) => n.toLocaleString("ru-RU");
const plural = (n, one, few, many) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many; };

export default function Topup({ me, reloadMe }) {
  const [open, setOpen] = useState(false);
  const [need, setNeed] = useState(0);
  const [data, setData] = useState(null);
  const [pack, setPack] = useState("p1500");
  const [method, setMethod] = useState("stars");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(null);

  useEffect(() => {
    const on = (e) => { setNeed(e.detail?.need || 0); setOpen(true); haptic("light"); };
    window.addEventListener("nova:topup", on);
    return () => window.removeEventListener("nova:topup", on);
  }, []);
  useEffect(() => { if (open && !data) api("/api/pay/packs").then(setData).catch(() => toast("Не удалось загрузить пакеты", "error")); }, [open]);

  const poll = async (pid, tries = 40) => {
    setWait(pid);
    for (let i = 0; i < tries; i++) {
      const s = await api(`/api/pay/${pid}`).catch(() => null);
      if (s?.status === "paid") {
        setWait(null); setOpen(false); haptic("success"); reloadMe?.();
        toast(`Готово: +${fmt(s.credits)} кредитов`); return;
      }
      await new Promise((r) => setTimeout(r, i < 10 ? 1500 : 3000));
    }
    setWait(null); toast("Оплата пока не подтверждена — кредиты придут сами, как только она пройдёт");
  };

  const buy = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api(`/api/pay/${method}`, { method: "POST", body: { pack } });
      if (method === "stars") {
        if (tg?.openInvoice) {
          tg.openInvoice(r.link, (status) => {
            if (status === "paid") poll(r.payment.id);
            else if (status === "failed") toast("Оплата не прошла", "error");
          });
        } else { window.open(r.link, "_blank"); poll(r.payment.id, 80); }
      } else {
        if (tg?.openTelegramLink && r.link.startsWith("https://t.me/")) tg.openTelegramLink(r.link); else window.open(r.link, "_blank");
        poll(r.payment.id, 120);
      }
    } catch (e) { toast(e.message, "error"); }
    finally { setBusy(false); }
  };

  const p = data?.packs.find((x) => x.id === pack);
  return (
    <Sheet open={open} onClose={() => { setOpen(false); setWait(null); }} title="Пополнение">
      <h3 className="sheet-title">Пополнить баланс</h3>
      <p className="muted small center tp-sub">{need > 0 ? `Не хватает ${fmt(need)} кредитов` : `Сейчас на балансе ${fmt(me?.balance ?? 0)} кредитов`}</p>
      {!data ? <div className="skeleton" /> : (
        <>
          <div className="packs" role="radiogroup" aria-label="Пакет">
            {data.packs.map((x) => (
              <button key={x.id} role="radio" aria-checked={pack === x.id} className={"pack" + (pack === x.id ? " on" : "")} onClick={() => { haptic("select"); setPack(x.id); }}>
                {x.hit && <span className="pk-hit">Выгодно</span>}
                <span className="pk-c"><Icon n="spark" s={15} w={2} />{fmt(x.total)}</span>
                <span className={"pk-b" + (x.bonus ? " bonus" : "")}>{x.bonus ? `+${fmt(x.bonus)} бонусом` : "кредитов"}</span>
                <span className="pk-p">{method === "stars" ? `${fmt(x.stars)} ⭐` : `$${x.usd}`}</span>
              </button>))}
          </div>
          {data.methods.length > 1 && (
            <div className="payseg" role="tablist" aria-label="Способ оплаты">
              <button role="tab" aria-selected={method === "stars"} className={method === "stars" ? "on" : ""} onClick={() => setMethod("stars")}>⭐ Telegram Stars</button>
              <button role="tab" aria-selected={method === "crypto"} className={method === "crypto" ? "on" : ""} onClick={() => setMethod("crypto")}>Крипта</button>
            </div>)}
          {p && (() => { const im = Math.floor(p.total / 40), mi = Math.floor(p.total / 5);
            return <p className="muted small tp-what">Хватит на {im} {plural(im, "картинку", "картинки", "картинок")} или {fmt(mi)} {plural(mi, "минуту", "минуты", "минут")} с&nbsp;агентом</p>; })()}
          <button className="cta wide" onClick={buy} disabled={busy || !!wait}>
            {wait ? "Жду подтверждение оплаты…" : busy ? "Открываю оплату…" : `Оплатить ${method === "stars" ? `${fmt(p?.stars || 0)} ⭐` : `$${p?.usd}`}`}
          </button>
          <p className="muted small center tp-note">{method === "stars" ? "Оплата внутри Telegram, кредиты придут сразу" : "USDT, TON и другие монеты через @CryptoBot. Кредиты придут автоматически"}</p>
        </>)}
    </Sheet>);
}
