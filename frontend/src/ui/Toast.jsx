import { useEffect, useState } from "react";
let push;
export function toast(text, kind = "info") { push?.({ text, kind, id: Date.now() + Math.random() }); }
export function Toaster() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    push = (t) => {
      setItems((x) => [...x.slice(-2), t]);
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== t.id)), 2800);
    };
    return () => { push = undefined; };
  }, []);
  return (
    <div className="toasts" role="status" aria-live="polite">
      {items.map((t) => <div key={t.id} className={"toast " + t.kind}>{t.text}</div>)}
    </div>);
}
