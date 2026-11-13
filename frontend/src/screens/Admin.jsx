import { useEffect, useMemo, useState } from "react";
import Icon from "../ui/Icon.jsx";
import Sheet from "../ui/Sheet.jsx";
import { SlideTabs } from "../ui/TabBar.jsx";
import { api } from "../api.js";
import { toast } from "../ui/Toast.jsx";
import { KIND, thumbOf } from "../jobs.js";
import { haptic } from "../tg.js";

const TABS = [{ k: "stats", t: "Сводка" }, { k: "users", t: "Люди" }, { k: "jobs", t: "Работы" }, { k: "prices", t: "Цены" },
  { k: "promo", t: "Промо" }, { k: "send", t: "Рассылка" }, { k: "log", t: "Журнал" }];
const fmt = (n) => Number(n || 0).toLocaleString("ru-RU");
const when = (iso) => iso ? new Date(iso).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const STATUS = { review: "На проверке", queued: "В очереди", running: "Идёт", done: "Готово", failed: "Ошибка", cancelled: "Отменено", rejected: "Отклонено" };

export default function Admin({ go, params }) {
  const [tab, setTab] = useState(params?.tab || new URLSearchParams(location.hash.split("?")[1] || "").get("tab") || "stats");
  return (
    <main className="screen admin">
      <header className="bar"><button className="ic-btn" aria-label="Назад" onClick={() => go("profile")}><Icon n="back" /></button><h1>Админка</h1></header>
      <SlideTabs label="Разделы" items={TABS} value={tab} onChange={setTab} />
      {tab === "stats" && <Stats />}
      {tab === "users" && <Users />}
      {tab === "jobs" && <Jobs />}
      {tab === "prices" && <Prices />}
      {tab === "promo" && <Promo />}
      {tab === "send" && <Send />}
      {tab === "log" && <Log />}
    </main>);
}

function Stats() {
  const [s, setS] = useState(null);
  const [m, setM] = useState("revenue");
  useEffect(() => { api("/api/admin/stats?days=30").then(setS).catch((e) => toast(e.message, "error")); }, []);
  if (!s) return <div className="skeleton" />;
  const val = (r) => m === "revenue" ? r.stars * 0.013 + r.usd + (r.rub || 0) / 90 : m === "users" ? r.users : r.jobs;
  const max = Math.max(1, ...s.series.map(val));
  return (
    <>
      <div className="kpis">
        <div className="kpi"><span>Пользователи</span><b>{fmt(s.users.total)}</b><small>{s.users.dau} за день · {s.users.wau} за неделю</small></div>
        <div className="kpi"><span>Выручка 30 дн.</span><b>${fmt(s.money.revenue_usd)}</b><small>{fmt(s.money.stars)} ⭐ · {fmt(s.money.rub)} ₽ · ${s.money.usd}</small></div>
        <div className="kpi"><span>Расходы на модели</span><b>${fmt(s.money.cost_usd)}</b><small>оценка по выполненным</small></div>
        <div className={"kpi" + (s.money.margin_usd < 0 ? " neg" : " pos")}><span>Маржа</span><b>${fmt(s.money.margin_usd)}</b><small>{fmt(s.money.credits_spent)} кредитов потрачено</small></div>
      </div>
      <section className="card">
        <div className="row-h"><h2>30 дней</h2></div>
        <div className="payseg three">
          {[["revenue", "Выручка"], ["users", "Новые"], ["jobs", "Генерации"]].map(([k, t]) =>
            <button key={k} className={m === k ? "on" : ""} onClick={() => setM(k)}>{t}</button>)}
        </div>
        <div className="bars" role="img" aria-label="График за 30 дней">
          {s.series.map((r) => <span key={r.day} title={`${r.day}: ${val(r).toFixed(m === "revenue" ? 2 : 0)}`} style={{ height: `${Math.max(2, (val(r) / max) * 100)}%` }} />)}
        </div>
        <div className="bars-x"><span>{s.series[0].day.slice(5)}</span><span>сегодня</span></div>
      </section>
      <section className="card">
        <div className="row-h"><h2>Генерации по типам</h2></div>
        <table className="tbl"><thead><tr><th>Тип</th><th>Всего</th><th>Готово</th><th>Ошибки</th><th>Кредиты</th></tr></thead>
          <tbody>{Object.entries(s.by_kind).map(([k, v]) => <tr key={k}><td>{KIND[k]}</td><td>{v.total}</td><td>{v.done}</td><td>{v.failed}</td><td>{fmt(v.credits)}</td></tr>)}
            <tr><td>Агент</td><td colSpan={3}>{fmt(s.money.agent_turns)} реплик</td><td></td></tr></tbody></table>
      </section>
    </>);
}

function Users() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  const load = (text) => api(`/api/admin/users?q=${encodeURIComponent(text)}`).then(setRows).catch((e) => toast(e.message, "error"));
  useEffect(() => { const t = setTimeout(() => load(q), 250); return () => clearTimeout(t); }, [q]);
  return (
    <>
      <div className="search"><Icon n="search" s={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Имя, @ник или Telegram ID" aria-label="Поиск" /></div>
      {!rows ? <div className="skeleton" /> : rows.length === 0 ? <p className="muted center small">Никого не нашлось</p> : (
        <ul className="list">{rows.map((u) => (
          <li key={u.id} className="tap" onClick={() => setOpen(u.id)}>
            <span className="ava">{(u.name || u.username || "?")[0].toUpperCase()}</span>
            <span><span className="t">{u.name || "Без имени"} {u.username && <small className="muted">@{u.username}</small>}{u.blocked && <em className="tag danger">заблокирован</em>}</span>
              <span className="muted small">{fmt(u.balance)} кр. · был {when(u.seen)}</span></span>
            <Icon n="chevron" s={15} />
          </li>))}</ul>)}
      <UserSheet id={open} onClose={() => setOpen(null)} onChange={() => load(q)} />
    </>);
}

function UserSheet({ id, onClose, onChange }) {
  const [u, setU] = useState(null);
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const load = () => api(`/api/admin/users/${id}`).then(setU).catch((e) => toast(e.message, "error"));
  useEffect(() => { setU(null); if (id) load(); }, [id]);
  const credits = async (sign) => {
    const n = parseInt(delta, 10);
    if (!n || n <= 0 || reason.trim().length < 2) return toast("Укажите сумму и причину", "error");
    try { await api(`/api/admin/users/${id}/credits`, { method: "POST", body: { delta: sign * n, reason } }); setDelta(""); setReason(""); load(); onChange(); toast("Готово"); }
    catch (e) { toast(e.message, "error"); }
  };
  const block = async () => {
    if (!u.blocked && !window.confirm("Заблокировать пользователя? Он не сможет открыть NOVA.")) return;
    await api(`/api/admin/users/${id}/block`, { method: "POST", body: { blocked: !u.blocked } }); load(); onChange();
  };
  return (
    <Sheet open={!!id} onClose={onClose} title="Пользователь">
      {!u ? <div className="skeleton" /> : <>
        <div className="sheet-head"><span className="ava big">{(u.name || "?")[0].toUpperCase()}</span>
          <span className="sr-t"><b>{u.name || "Без имени"}</b><small>{u.username ? "@" + u.username + " · " : ""}ID {u.tg_id} · с {when(u.created)}</small></span></div>
        <div className="kpis two">
          <div className="kpi"><span>Баланс</span><b>{fmt(u.balance)}</b></div>
          <div className="kpi"><span>Оплатил</span><b>{[u.paid.XTR && fmt(u.paid.XTR) + " ⭐", u.paid.RUB && fmt(u.paid.RUB) + " ₽", u.paid.USD && "$" + u.paid.USD].filter(Boolean).join(" · ") || "—"}</b></div>
        </div>
        <div className="card adm-form">
          <div className="adm-row"><input inputMode="numeric" value={delta} onChange={(e) => setDelta(e.target.value.replace(/\D/g, ""))} placeholder="Кредиты" aria-label="Кредиты" />
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Причина" aria-label="Причина" maxLength={200} /></div>
          <div className="agc-b"><button className="row-btn" onClick={() => credits(-1)}>Списать</button><button className="cta" onClick={() => credits(1)}>Начислить</button></div>
        </div>
        {u.jobs.length > 0 && <div className="ag-cards">{u.jobs.map((j) => { const th = thumbOf(j); return (
          <span key={j.id} className={"ag-card k-" + j.kind} style={th ? { backgroundImage: `url(${th})` } : undefined} title={j.prompt}><span>{KIND[j.kind]}</span></span>); })}</div>}
        <ul className="list">{u.ledger.slice(0, 12).map((l, i) => (
          <li key={i}><span><span className="t">{l.title}</span><span className="muted small">{when(l.at)}</span></span><b className={"delta " + (l.delta > 0 ? "plus" : "")}>{l.delta > 0 ? "+" : ""}{fmt(l.delta)}</b></li>))}</ul>
        <button className={"sheet-row" + (u.blocked ? " accent" : " danger")} onClick={block}><span className="sr-ic"><Icon n={u.blocked ? "check" : "x"} /></span>
          <span className="sr-t"><span>{u.blocked ? "Разблокировать" : "Заблокировать"}</span></span></button>
      </>}
    </Sheet>);
}

function Jobs() {
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  const load = () => api(`/api/admin/jobs?status=${status}&kind=${kind}`).then(setRows).catch((e) => toast(e.message, "error"));
  useEffect(() => { setRows(null); load(); }, [status, kind]);
  const del = async (j) => {
    if (!window.confirm("Удалить работу без возврата кредитов?")) return;
    await api(`/api/admin/jobs/${j.id}`, { method: "DELETE" }); setOpen(null); load(); toast("Удалено");
  };
  return (
    <>
      <SlideTabs label="Статус" value={status} onChange={setStatus}
        items={[{ k: "", t: "Все" }, { k: "done", t: "Готово" }, { k: "failed", t: "Ошибки" }]} />
      <div className="chips">{[["", "Все типы"], ["image", "Фото"], ["video", "Видео"], ["music", "Музыка"], ["tts", "Озвучка"]].map(([k, t]) =>
        <button key={k} className={"chip" + (kind === k ? " on" : "")} onClick={() => setKind(k)}>{t}</button>)}</div>
      {!rows ? <div className="skeleton" /> : rows.length === 0 ? <div className="empty-state slim"><Icon n="check" s={22} /><p>Пусто</p></div> : (
        <div className="adm-jobs">{rows.map((j) => { const th = thumbOf(j); return (
          <div key={j.id} className="card adm-job">
            <button className={"mini k-" + j.kind} style={th ? { backgroundImage: `url(${th})` } : undefined} onClick={() => setOpen(j)} aria-label="Открыть" />
            <div className="aj-b">
              <div className="aj-h"><span className={"tag k-" + j.kind}>{KIND[j.kind]}</span><span className={"st st-" + j.status}>{STATUS[j.status] || j.status}</span><span className="muted small">{when(j.created || j.at)}</span></div>
              <p className="aj-p">{j.prompt}</p>
              <span className="muted small">{j.user.name || j.user.username || j.user.id} · {j.cost} кр.{j.error ? ` · ${j.error.slice(0, 80)}` : ""}</span>
            </div>
          </div>); })}</div>)}
      <Sheet open={!!open} onClose={() => setOpen(null)} title="Работа">
        {open && <>
          {open.kind === "image" && open.files?.[0] && <img className="sheet-media" src={open.files[0].url} alt="" />}
          {open.kind === "video" && open.files?.find((f) => f.type === "video") && <video className="sheet-media" src={open.files.find((f) => f.type === "video").url} controls playsInline />}
          {(open.kind === "music" || open.kind === "tts") && open.files?.[0] && <audio src={open.files[0].url} controls className="adm-audio" />}
          <p className="aj-p full">{open.prompt}</p>
          <button className="sheet-row danger" onClick={() => del(open)}><span className="sr-ic"><Icon n="trash" /></span><span className="sr-t"><span>Удалить работу</span></span></button>
        </>}
      </Sheet>
    </>);
}

const PRICE_LABELS = [["image", "Фото «Быстро», 4 варианта"], ["image_max", "Фото «Максимум» 2K, 4 варианта"], ["video_std_s", "Видео 720p, за секунду"], ["video_pro_s", "Видео 1080p, за секунду"],
  ["video_sound_k", "Видео со звуком, множитель"], ["music", "Музыка, 2 трека"], ["tts_1k", "Озвучка, за 1000 символов"], ["tts_min", "Озвучка, минимум"],
  ["agent_min", "Агент, за минуту"], ["welcome", "Приветственные кредиты"], ["ref_friend", "Другу по ссылке"], ["ref_bonus", "Пригласившему за покупку друга"]];

function Prices() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/api/admin/prices").then(setD).catch((e) => toast(e.message, "error")); }, []);
  if (!d) return <div className="skeleton" />;
  const setP = (k, v) => setD({ ...d, price: { ...d.price, [k]: v } });
  const setPack = (i, k, v) => setD({ ...d, packs: d.packs.map((p, j) => j === i ? { ...p, [k]: v } : p) });
  const save = async (body) => {
    setBusy(true);
    try { const r = await api("/api/admin/prices", { method: "PUT", body }); setD({ ...d, ...r }); toast("Цены сохранены и уже действуют"); }
    catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <>
      <section className="card adm-form">
        <div className="row-h"><h2>Цены в кредитах</h2></div>
        {PRICE_LABELS.map(([k, t]) => (
          <label key={k} className="adm-field"><span>{t}</span>
            <input inputMode="decimal" value={d.price[k]} onChange={(e) => setP(k, e.target.value.replace(",", "."))} /></label>))}
      </section>
      <section className="card adm-form">
        <div className="row-h"><h2>Пакеты</h2></div>
        <div className="pk-head five"><span>Кредиты</span><span>Бонус</span><span>⭐</span><span>$</span><span>₽</span></div>
        {d.packs.map((p, i) => (
          <div key={i} className="pk-row five">
            {["credits", "bonus", "stars", "usd", "rub"].map((k) => <input key={k} inputMode="decimal" value={p[k]} aria-label={k} onChange={(e) => setPack(i, k, e.target.value.replace(",", "."))} />)}
          </div>))}
        <p className="muted small">1 ⭐ ≈ $0.013 при выводе. Бонус показывается зелёным в листе пополнения.</p>
      </section>
      <div className="agc-b">
        <button className="row-btn" disabled={busy} onClick={() => window.confirm("Вернуть все цены по умолчанию?") && save(d.defaults)}>По умолчанию</button>
        <button className="cta" disabled={busy} onClick={() => save({ price: d.price, packs: d.packs })}>{busy ? "Сохраняю…" : "Сохранить"}</button>
      </div>
    </>);
}

function Promo() {
  const [rows, setRows] = useState(null);
  const [f, setF] = useState({ code: "", credits: "100", max_uses: "100", days: "" });
  const load = () => api("/api/admin/promos").then(setRows);
  useEffect(() => { load(); }, []);
  const add = async () => {
    try {
      await api("/api/admin/promos", { method: "POST", body: { code: f.code.trim(), credits: +f.credits, max_uses: +f.max_uses, days: f.days ? +f.days : null } });
      setF({ ...f, code: "" }); load(); toast("Промокод создан");
    } catch (e) { toast(e.message, "error"); }
  };
  return (
    <>
      <section className="card adm-form">
        <div className="row-h"><h2>Новый промокод</h2></div>
        <label className="adm-field"><span>Код</span><input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, "") })} placeholder="START100" /></label>
        <label className="adm-field"><span>Кредитов</span><input inputMode="numeric" value={f.credits} onChange={(e) => setF({ ...f, credits: e.target.value.replace(/\D/g, "") })} /></label>
        <label className="adm-field"><span>Активаций всего</span><input inputMode="numeric" value={f.max_uses} onChange={(e) => setF({ ...f, max_uses: e.target.value.replace(/\D/g, "") })} /></label>
        <label className="adm-field"><span>Дней действует</span><input inputMode="numeric" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value.replace(/\D/g, "") })} placeholder="бессрочно" /></label>
        <button className="cta wide" disabled={f.code.length < 3} onClick={add}>Создать</button>
      </section>
      <ul className="list">{(rows || []).map((p) => (
        <li key={p.id}>
          <span><span className="t mono">{p.code}</span><span className="muted small">{p.credits} кр. · {p.used}/{p.max_uses}{p.expires ? ` · до ${when(p.expires)}` : ""}</span></span>
          <button className={"switch" + (p.active ? " on" : "")} role="switch" aria-checked={p.active} aria-label="Активен"
            onClick={async () => { await api(`/api/admin/promos/${p.id}/toggle`, { method: "POST" }); load(); }}><i /></button>
        </li>))}</ul>
    </>);
}

function Send() {
  const [text, setText] = useState("");
  const [button, setButton] = useState("Открыть NOVA");
  const [hist, setHist] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => api("/api/admin/broadcasts").then(setHist).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);
  const preview = async () => {
    setBusy(true);
    try { await api("/api/admin/broadcast/preview", { method: "POST", body: { text, button } }); toast("Отправил тебе в бот — проверь, как выглядит"); }
    catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  const send = async () => {
    if (!window.confirm("Отправить рассылку всем пользователям? Отменить можно только пока она идёт.")) return;
    setBusy(true);
    try { const r = await api("/api/admin/broadcast", { method: "POST", body: { text, button } }); toast(`Рассылка запущена: ${r.total} получателей`); setText(""); load(); }
    catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <>
      <section className="card adm-form">
        <div className="row-h"><h2>Сообщение</h2></div>
        <textarea className="adm-text" rows={6} value={text} onChange={(e) => setText(e.target.value)} maxLength={3500} placeholder="Например: «Новое в NOVA — голосовой агент. Скажи, что создать, и он сделает»" />
        <p className="muted small adm-hint">Можно &lt;b&gt;жирный&lt;/b&gt; и &lt;i&gt;курсив&lt;/i&gt;. Кнопка откроет NOVA.</p>
        <label className="adm-field wide"><span>Кнопка</span><input value={button} onChange={(e) => setButton(e.target.value)} maxLength={40} placeholder="без кнопки" /></label>
        <div className="agc-b"><button className="row-btn" disabled={busy || text.trim().length < 2} onClick={preview}>Предпросмотр</button>
          <button className="cta" disabled={busy || text.trim().length < 2} onClick={send}>Отправить всем</button></div>
      </section>
      {hist.length > 0 && <ul className="list">{hist.map((b) => (
        <li key={b.id}>
          <span><span className="t">{b.text}</span><span className="muted small">{when(b.at)} · {({ queued: "в очереди", sending: "идёт", done: "готово", cancelled: "отменена" })[b.status]} · {b.sent}/{b.total}{b.failed ? ` · ошибок ${b.failed}` : ""}</span>
            {b.status === "sending" && <span className="bar-line"><i style={{ width: `${(b.sent / Math.max(1, b.total)) * 100}%` }} /></span>}</span>
          {(b.status === "sending" || b.status === "queued") && <button className="link danger" onClick={async () => { await api(`/api/admin/broadcasts/${b.id}/cancel`, { method: "POST" }); load(); }}>Стоп</button>}
        </li>))}</ul>}
    </>);
}

function Log() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api("/api/admin/log").then(setRows); }, []);
  const ACT = { credits: "Кредиты", block: "Блокировка", unblock: "Разблокировка",
    delete_job: "Удалена работа", prices: "Цены", promo_add: "Новый промокод", promo_on: "Промокод вкл.", promo_off: "Промокод выкл.", broadcast: "Рассылка", broadcast_cancel: "Рассылка остановлена" };
  if (!rows) return <div className="skeleton" />;
  if (!rows.length) return <p className="muted center small">Пока пусто</p>;
  return <ul className="list">{rows.map((r, i) => (
    <li key={i}><span><span className="t">{ACT[r.action] || r.action}{r.target ? ` · ${r.target}` : ""}</span>
      <span className="muted small">{r.admin} · {when(r.at)}{r.detail && r.action !== "prices" ? ` · ${r.detail.slice(0, 90)}` : ""}</span></span></li>))}</ul>;
}
