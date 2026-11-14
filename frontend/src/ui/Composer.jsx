import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { haptic } from "../tg.js";
import { toast } from "./Toast.jsx";
import { api, upload } from "../api.js";
import { Dictation } from "../agent/voice.js";
import { useFlip } from "./flip.js";

const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Prompt row: «+» attaches a photo (gallery or camera), the wave dictates into the field (1 credit), the arrow sends.
 *  onSend(text, imageUrl) — imageUrl only when `attach` is on and a photo is attached. */
export default function Composer({ value, onChange, onSend, busy, placeholder = "Что создать?", autoFocus, attach = false, onBalance }) {
  const ref = useRef(null);
  const file = useRef(null);
  const dict = useRef(null);
  const bars = useRef(null);
  const [img, setImg] = useState(null);           // { preview, url|null while uploading }
  const [rec, setRec] = useState("off");          // off | rec | stt
  const [sec, setSec] = useState(0);
  const [focus, setFocus] = useState(false);
  const root = useRef(null);
  const open = focus || !!value.trim() || !!img || rec !== "off";          // grows while typing; folds back when empty and left
  // folds back only when the user taps somewhere else on the page (not on blur: iOS fires stray blurs while the
  // keyboard opens and the field grows, which made it fold and unfold by itself)
  useEffect(() => {
    if (!focus) return;
    const out = (e) => { if (!root.current?.contains(e.target)) setFocus(false); };
    document.addEventListener("pointerdown", out, true);
    return () => document.removeEventListener("pointerdown", out, true);
  }, [focus]);
  // the floating tab bar sits on the keyboard: hide it while the field itself has focus on a phone
  const kb = (on) => { if (window.matchMedia?.("(pointer: coarse)").matches) document.documentElement.classList.toggle("kb-open", on); };
  useEffect(() => () => document.documentElement.classList.remove("kb-open"), []);

  // the field's height is set before paint (a post-paint fix-up showed one wrong frame: the «hitch»)
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return;
    el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, open ? 220 : 140) + "px";
  }, [value, rec, open]);

  // grow / fold as one motion (see useFlip)
  const plusRef = useRef(null), segRef = useRef(null), sendRef = useRef(null);
  useFlip(root, () => [ref.current, plusRef.current, segRef.current, sendRef.current], [open, !!img, rec]);
  useEffect(() => () => { dict.current?.stop(); if (img?.preview) URL.revokeObjectURL(img.preview); }, []);   // eslint-disable-line
  useEffect(() => {
    if (rec !== "rec") return;
    const t0 = Date.now(), id = setInterval(() => setSec((Date.now() - t0) / 1000), 250);
    return () => clearInterval(id);
  }, [rec]);

  const uploading = img && !img.url;
  const send = () => {
    const t = value.trim();
    if (!t || busy || uploading || rec !== "off") return;
    haptic("light"); onSend(t, img?.url || null);
  };

  const pick = async (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (!/^image\/(jpeg|png|webp|heic|heif)$/i.test(f.type) && !/\.(jpe?g|png|webp|heic)$/i.test(f.name)) { toast("Нужно фото в JPG, PNG или WebP", "error"); return; }
    haptic("select");
    const preview = URL.createObjectURL(f);
    setImg({ preview, url: null });
    try {
      const blob = await toJpeg(f);
      const url = await upload(blob);
      setImg((cur) => (cur?.preview === preview ? { preview, url } : cur));
      ref.current?.focus();
    } catch (er) {
      toast(er.message || "Не удалось загрузить фото", "error");
      setImg((cur) => (cur?.preview === preview ? null : cur)); URL.revokeObjectURL(preview);
    }
  };
  const unpick = () => { haptic("select"); if (img?.preview) URL.revokeObjectURL(img.preview); setImg(null); };

  const level = (v) => {             // live bars while recording, straight to the DOM (no re-render per audio chunk)
    const el = bars.current; if (!el) return;
    const kids = el.children, n = kids.length;
    for (let i = 0; i < n - 1; i++) kids[i].style.transform = kids[i + 1].style.transform;
    kids[n - 1].style.transform = `scaleY(${Math.max(0.12, Math.min(1, v * 1.4))})`;
  };
  const startRec = async () => {
    haptic("medium");
    const d = new Dictation();
    d.onLimit = () => stopRec();
    try { await d.start(level); dict.current = d; setSec(0); setRec("rec"); }
    catch { d.stop(); toast("Нужен доступ к микрофону — разрешите его и попробуйте снова", "error"); }
  };
  const stopRec = async () => {
    const d = dict.current; if (!d) return;
    dict.current = null; haptic("light");
    const w = d.stop();
    if (!w || w.sec < 0.5) { setRec("off"); toast("Слишком коротко — скажите ещё раз"); return; }
    setRec("stt");
    try {
      const r = await api("/api/agent/stt", { method: "POST", body: { audio: w.b64 } });
      const cur = value.trim();
      onChange(cur ? cur + " " + r.text : r.text);
      onBalance?.(r.balance);
      setTimeout(() => { const el = ref.current; if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 30);
    } catch (er) { toast(er.message, "error"); }
    setRec("off");
  };
  const cancelRec = () => { if (rec === "rec") { dict.current?.stop(); dict.current = null; setRec("off"); } ref.current?.focus(); };
  const wave = () => (rec === "rec" ? stopRec() : rec === "off" ? startRec() : null);

  return (
    <div ref={root} className={"composer" + (open ? " open" : "") + (img ? " has-att" : "") + (rec !== "off" ? " recording" : "")}
      onFocus={() => setFocus(true)}
      // a tap on our own buttons keeps the typing focus (iOS doesn't focus buttons, so the field would fold under the finger)
      onMouseDown={(e) => { if (e.target.closest("button")) e.preventDefault(); }}
>
      {img && (
        <div className="cmp-att">
          <span className={"cmp-thumb" + (uploading ? " up" : "")} style={{ backgroundImage: `url(${img.preview})` }}>
            {uploading && <i className="spin" aria-label="Загружаю фото" />}
            <button aria-label="Убрать фото" onClick={unpick}><Icon n="x" s={12} w={2.6} /></button>
          </span>
        </div>)}
      {attach
        ? <button ref={plusRef} className="ic-btn sq" aria-label="Прикрепить фото" onClick={() => { haptic("select"); setFocus(false); ref.current?.blur(); file.current?.click(); }} disabled={rec !== "off"}><Icon n="plus" /></button>
        : null}
      {attach && <input ref={file} type="file" accept="image/*" hidden onChange={pick} />}
      <label className="sr" htmlFor="composer-input">Сообщение</label>
      {rec === "off"
        ? <textarea id="composer-input" ref={ref} rows={open ? 3 : 1} onFocusCapture={() => kb(true)} onBlurCapture={() => kb(false)} value={value} placeholder={img ? "Что сделать с фото?" : placeholder} autoFocus={autoFocus}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        : <div className="cmp-rec" aria-live="polite">
            {rec === "rec"
              ? <><i className="rec-dot" /><span className="rec-bars" ref={bars} aria-hidden="true">{Array.from({ length: 22 }, (_, i) => <i key={i} />)}</span><span className="rec-t">{mmss(sec)}</span></>
              : <><i className="spin" /><span className="rec-l">Распознаю…</span></>}
          </div>}
      <span ref={segRef} className="seg" role="group" aria-label="Способ ввода">
        <button className={rec === "off" ? "on" : ""} aria-label="Печатать" aria-pressed={rec === "off"} onClick={cancelRec}>Aa</button>
        <button className={rec !== "off" ? "on rec" : ""} aria-label={rec === "rec" ? "Закончить диктовку" : "Надиктовать · 1 кредит"} aria-pressed={rec !== "off"} onClick={wave} disabled={rec === "stt"}>
          {rec === "rec" ? <i className="stop-sq" /> : <Icon n="wave" s={15} />}</button>
      </span>
      <button ref={sendRef} className="send" aria-label="Отправить" disabled={!value.trim() || busy || uploading || rec !== "off"} onClick={send}><Icon n="send" w={2.2} /></button>
    </div>);
}

/** Phone photos are huge (and HEIC on iPhone): downscale to ≤2048 px JPEG before upload. */
async function toJpeg(f) {
  try {
    const bmp = await createImageBitmap(f);
    const k = Math.min(1, 2048 / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    const b = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
    return b ? new File([b], "photo.jpg", { type: "image/jpeg" }) : f;
  } catch { return f; }
}
