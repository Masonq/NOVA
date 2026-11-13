import { useCallback, useEffect, useState } from "react";
import { api, auth } from "./api.js";
import { inTelegram, tg, haptic } from "./tg.js";
import Icon from "./ui/Icon.jsx";
import { Toaster } from "./ui/Toast.jsx";
import Login from "./screens/Login.jsx";
import Home from "./screens/Home.jsx";
import Chat from "./screens/Chat.jsx";
import Archive from "./screens/Archive.jsx";
import Profile from "./screens/Profile.jsx";

const parse = () => (location.hash.replace(/^#\/?/, "") || "home").split("?")[0];
const TABS = [{ k: "home", t: "Главная", i: "home" }, { k: "archive", t: "Архив", i: "clock" }, { k: "profile", t: "Профиль", i: "user" }];

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(!!auth.get());
  const [route, setRoute] = useState(parse());
  const [params, setParams] = useState(null);
  const [me, setMe] = useState(null);
  const [fatal, setFatal] = useState("");

  const loadMe = useCallback(() => api("/api/me").then(setMe).catch(() => {}), []);

  useEffect(() => {
    (async () => {
      if (inTelegram) {
        try {
          const r = await api("/api/auth/webapp", { method: "POST", body: { initData: tg.initData } });
          auth.set(r.token); setAuthed(true);
        } catch (e) { setFatal(e.message); }
      }
      setReady(true);
    })();
    const out = () => setAuthed(false);
    const hc = () => setRoute(parse());
    window.addEventListener("nova:logout", out); window.addEventListener("hashchange", hc);
    return () => { window.removeEventListener("nova:logout", out); window.removeEventListener("hashchange", hc); };
  }, []);
  useEffect(() => { if (authed) loadMe(); }, [authed, route]);

  const go = (r, p = null) => { setParams(p); if (parse() !== r) location.hash = "#/" + r; else setRoute(r); window.scrollTo(0, 0); };

  useEffect(() => {
    const b = tg?.BackButton; if (!b || !inTelegram) return;
    const back = () => go("home");
    if (route !== "home") { b.show(); b.onClick(back); } else b.hide();
    return () => b.offClick?.(back);
  }, [route]);

  if (!ready) return <div className="boot" aria-label="Загрузка" />;
  if (fatal) return <main className="login"><h1>NOVA</h1><p className="err">{fatal}</p><button className="cta" onClick={() => location.reload()}>Повторить</button></main>;
  if (!authed) return <><Login onDone={() => setAuthed(true)} /><Toaster /></>;

  const screen = route === "chat" ? <Chat go={go} params={params} />
    : route === "archive" ? <Archive go={go} />
    : route === "profile" ? <Profile me={me} reload={loadMe} />
    : <Home go={go} me={me} />;
  return (
    <div className={"app r-" + route}>
      {screen}
      {route !== "chat" && (
        <nav className="tabbar" aria-label="Разделы">
          {TABS.map((t) => (
            <button key={t.k} className={route === t.k ? "on" : ""} aria-current={route === t.k ? "page" : undefined}
              onClick={() => { haptic("select"); go(t.k); }}>
              <Icon n={t.i} s={21} /><span>{t.t}</span>
            </button>))}
        </nav>)}
      <Toaster />
    </div>);
}
