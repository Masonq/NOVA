import { useState } from "react";
import Orb from "./Orb.jsx";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";

const SLIDES = [
  { t: "Создавай что угодно", p: "Картинки и логотипы, видео со звуком, музыку и озвучку — одной фразой.", art: "tiles" },
  { t: "Просто скажи голосом", p: "Агент NOVA слышит, отвечает живым голосом и сам запускает генерации — после твоего «да».", art: "orb" },
  { t: "300 кредитов в подарок", p: "Этого хватит на 25 картинок или час разговора с агентом. Все работы хранятся 30 дней.", art: "gift" },
];

export default function Onboarding({ onDone, balance }) {
  const [i, setI] = useState(0);
  const s = SLIDES[i];
  const next = () => { haptic("light"); if (i < SLIDES.length - 1) setI(i + 1); else { localStorage.setItem("nova_onb", "1"); onDone(); } };
  return (
    <div className="onb" role="dialog" aria-label="Знакомство с NOVA">
      <button className="onb-skip link" onClick={() => { localStorage.setItem("nova_onb", "1"); onDone(); }}>Пропустить</button>
      <div className="onb-art" key={i}>
        {s.art === "orb" && <Orb size={230} dense />}
        {s.art === "tiles" && <div className="onb-tiles">{[["image", "Фото"], ["video", "Видео"], ["music", "Музыка"], ["wave", "Озвучка"]].map(([ic, t], k) =>
          <span key={t} style={{ animationDelay: `${k * 90}ms` }}><Icon n={ic} s={28} /><b>{t}</b></span>)}</div>}
        {s.art === "gift" && <div className="onb-gift"><Icon n="spark" s={40} w={1.6} /><b>{balance ?? 300}</b><span>кредитов</span></div>}
      </div>
      <div className="onb-txt" key={"t" + i}><h2>{s.t}</h2><p>{s.p}</p></div>
      <div className="onb-dots" aria-hidden="true">{SLIDES.map((_, k) => <i key={k} className={k === i ? "on" : ""} />)}</div>
      <button className="cta wide" onClick={next}>{i < SLIDES.length - 1 ? "Дальше" : "Начать"}</button>
    </div>);
}
