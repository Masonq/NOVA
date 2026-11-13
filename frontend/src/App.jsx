import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, auth } from "./api.js";
import { inTelegram, tg, haptic } from "./tg.js";
import Icon from "./ui/Icon.jsx";
import { Toaster } from "./ui/Toast.jsx";
const Login = lazy(() => import("./screens/Login.jsx"));
import Home from "./screens/Home.jsx";
const Chat = lazy(() => import("./screens/Chat.jsx"));
const Archive = lazy(() => import("./screens/Archive.jsx"));
const Profile = lazy(() => import("./screens/Profile.jsx"));
const ImageStudio = lazy(() => import("./screens/ImageStudio.jsx"));
const VideoStudio = lazy(() => import("./screens/VideoStudio.jsx"));
const MusicStudio = lazy(() => import("./screens/MusicStudio.jsx"));
const TtsStudio = lazy(() => import("./screens/TtsStudio.jsx"));
const Tasks = lazy(() => import("./screens/Tasks.jsx"));
const Feed = lazy(() => import("./screens/Feed.jsx"));
const Agent = lazy(() => import("./screens/Agent.jsx"));
const Admin = lazy(() => import("./screens/Admin.jsx"));
import TabBar from "./ui/TabBar.jsx";
import { loadPrices } from "./jobs.js";
import Topup from "./ui/Topup.jsx";
import Onboarding from "./ui/Onboarding.jsx";
import { toast } from "./ui/Toast.jsx";

const parse = () => (location.hash.replace(/^#\/?/, "") || "home").split("?")[0];
const TABS = [{ k: "home", t: "Главная", i: "home" }, { k: "archive", t: "Архив", i: "clock" }, { k: "profile", t: "Профиль", i: "user" }];

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(!!auth.get());
  const [route, setRoute] = useState(parse());
  const [onb, setOnb] = useState(() => !localStorage.getItem("nova_onb"));
  const prevRoute = useRef(route);
  const DEPTH = { admin: 1, home: 0, archive: 0, profile: 0, image: 1, video: 1, music: 1, tts: 1, tasks: 1, chat: 1, agent: 1, feed: 2 };
  const dir = useMemo(() => {
    const a = DEPTH[prevRoute.current] ?? 0, b = DEPTH[route] ?? 0;
    const d = prevRoute.current === route ? "tab" : b > a ? "fwd" : b < a ? "back" : "tab";
    prevRoute.current = route;
    return d;
  }, [route]);
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
  useEffect(() => { if (authed) loadPrices(); }, [authed]);

  const go = (r, p = null) => { setParams(p); if (parse() !== r) location.hash = "#/" + r; else setRoute(r); window.scrollTo(0, 0); };

  useEffect(() => {
    const b = tg?.BackButton; if (!b || !inTelegram) return;
    const back = () => go(route === "feed" ? "archive" : "home");
    if (route !== "home") { b.show(); b.onClick(back); } else b.hide();
    return () => b.offClick?.(back);
  }, [route]);

  if (!ready) return <div className="boot" aria-label="Загрузка" />;
  if (fatal) return <main className="login"><h1>NOVA</h1><p className="err">{fatal}</p><button className="cta" onClick={() => location.reload()}>Повторить</button></main>;
  if (authed && onb && !me) return <div className="boot" aria-busy="true" />;   // no flash of home before the first-run intro
  if (!authed) return <><Suspense fallback={null}><Login onDone={() => setAuthed(true)} /></Suspense><Toaster /></>;

  const sp = { go, me, reloadMe: loadMe, params };
  const STUDIOS = { image: ImageStudio, video: VideoStudio, music: MusicStudio, tts: TtsStudio };
  const Studio = STUDIOS[route];
  const screen = Studio ? <Studio key={route + JSON.stringify(params || {})} {...sp} />
    : route === "admin" && me?.is_admin ? <Admin go={go} params={params} />
    : route === "agent" ? <Agent go={go} me={me} reloadMe={loadMe} />
    : route === "tasks" ? <Tasks go={go} />
    : route === "feed" ? <Feed go={go} />
    : route === "chat" ? <Chat go={go} params={params} />
    : route === "archive" ? <Archive go={go} params={params} />
    : route === "profile" ? <Profile me={me} reload={loadMe} go={go} />
    : <Home go={go} me={me} />;
  return (
    <div className={"app r-" + route}>
      <div key={route} className={"page " + dir}><Suspense fallback={<div className="screen"><div className="skeleton" /></div>}>{screen}</Suspense></div>
      {!["chat", "image", "video", "music", "tts", "feed", "agent", "admin"].includes(route) && (
        <TabBar tabs={TABS} active={TABS.find((t) => t.k === route) ? route : "home"} onSelect={(k) => go(k)}
          side={{ orb: true, label: "Голосовой агент", accent: true, onClick: () => go("agent") }} />)}
      {onb && me && me.jobs === 0 && <Onboarding balance={me.balance} onDone={() => setOnb(false)} />}
      <Topup me={me} reloadMe={loadMe} />
      <Toaster />
    </div>);
}
