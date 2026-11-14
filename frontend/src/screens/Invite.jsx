import { useEffect, useState } from "react";
import { ShareFat, Copy, CaretRight, Gift } from "@phosphor-icons/react";
import Icon from "../ui/Icon.jsx";
import { HeroArt } from "../ui/Art3D.jsx";
import { api } from "../api.js";
import { toast } from "../ui/Toast.jsx";
import { haptic, tg, setChrome } from "../tg.js";

const HERO = "#1E2A6E";          // Telegram's bar takes this colour: the hero starts right under it with no seam

/** «Пригласите друзей» as its own page (like Walt): coloured hero with a 3D gift, share + copy, how it works, FAQ. */
export default function Invite({ go, params }) {
  const [r, setR] = useState(null);
  useEffect(() => {
    setChrome(HERO);
    api("/api/me/referral").then(setR).catch((e) => toast(e.message, "error"));
    return () => setChrome();
  }, []);
  const text = r ? `Попробуй NOVA — голосовой ИИ-агент: картинки, видео и музыка одной фразой. По моей ссылке +${r.friend_bonus} кредитов` : "";
  const share = async () => {
    if (!r) return;
    haptic("light");
    if (tg?.openTelegramLink && tg.initData) { tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(r.link)}&text=${encodeURIComponent(text)}`); return; }
    try { if (navigator.share) { await navigator.share({ url: r.link, text }); return; } } catch (e) { if (e?.name === "AbortError") return; }
    copy();
  };
  const copy = async () => {
    if (!r) return;
    try { await navigator.clipboard.writeText(r.link); haptic("success"); toast("Ссылка скопирована"); } catch { toast(r.link); }
  };
  const fb = r?.friend_bonus ?? 50, bonus = r?.bonus ?? 100;
  return (
    <main className="screen invite-pg">
      <section className="hero" style={{ "--hero": HERO }}>
        <button className="ic-btn back-btn hero-back" aria-label="Назад" onClick={() => go(params?.from || "profile")}><Icon n="back" /></button>
        <HeroArt name="gift" size={150} />
        <h1>Пригласите друзей и&nbsp;получайте кредиты</h1>
        <p>Другу +{fb} кредитов сразу, вам +{bonus} после его первой покупки — за каждого друга.</p>
        <div className="hero-act">
          <button className="cta hero-cta" onClick={share} disabled={!r}><ShareFat size={18} weight="fill" />Поделиться ссылкой</button>
          <button className="hero-copy" aria-label="Скопировать ссылку" onClick={copy} disabled={!r}><Copy size={22} weight="fill" /></button>
        </div>
      </section>

      <section className="inv-kpis" aria-label="Ваши приглашения">
        {r ? (<>
          <div><b>{r.invited}</b><span>пришли</span></div>
          <div><b>{r.paid}</b><span>купили</span></div>
          <div><b className="plus">+{r.earned}</b><span>заработано</span></div>
        </>) : [0, 1, 2].map((i) => <div key={i} className="skeleton line" />)}
      </section>

      <section aria-labelledby="how-h">
        <h2 id="how-h" className="sec-h">Как это работает</h2>
        <ol className="how">
          <li><i>1</i><span><b>Отправьте другу ссылку</b><small>Через Telegram или любой мессенджер</small></span></li>
          <li><i>2</i><span><b>Друг открывает NOVA</b><small><em>+{fb} кредитов</em> ему сразу</small></span></li>
          <li><i className="gift-i"><Gift size={20} weight="fill" /></i><span><b>Друг пополняет баланс</b><small><em>+{bonus} кредитов</em> вам за каждого друга</small></span></li>
        </ol>
      </section>

      <section aria-labelledby="faq-h">
        <h2 id="faq-h" className="sec-h">Частые вопросы</h2>
        <div className="faq">
          {[
            ["Сколько друзей можно пригласить?", "Сколько угодно — бонус начисляется за каждого друга, который пополнит баланс."],
            ["Когда придут мои кредиты?", "Сразу после первой покупки друга. В истории профиля появится строка «Друг … сделал первую покупку»."],
            ["Что получит мой друг?", `+${fb} кредитов на старт сверх приветственных — этого хватит на несколько картинок.`],
            ["Почему друг не засчитался?", "Друг должен впервые открыть NOVA именно по вашей ссылке. Если он уже был в NOVA раньше, бонус не начисляется."],
          ].map(([q, a]) => (
            <details key={q}><summary>{q}<CaretRight size={14} weight="bold" /></summary><p>{a}</p></details>))}
        </div>
      </section>
    </main>);
}
