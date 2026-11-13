import { useEffect, useState } from "react";

/** Odometer: digits roll to the new number (balance after a charge or a top-up). The last shown value is remembered
 *  across screens, so a fresh screen rolls from what the user saw a moment ago, not from zero. */
let lastShown = null;
export default function Count({ value }) {
  const [shown, setShown] = useState(lastShown ?? value);
  const [dir, setDir] = useState("");
  useEffect(() => {
    if (value == null) return;
    if (value === shown) { lastShown = value; return; }
    let a = requestAnimationFrame(() => { a = requestAnimationFrame(() => { setDir(value > shown ? "up" : "down"); setShown(value); lastShown = value; }); });
    const t = setTimeout(() => setDir(""), 900);
    return () => { cancelAnimationFrame(a); clearTimeout(t); };
  }, [value]);
  if (value == null) return <>…</>;
  const digits = String(shown).split("");
  return (
    <span className={"odo " + dir} aria-label={String(value)}>
      {digits.map((d, i) => (
        <span key={digits.length - i} className="odo-c" aria-hidden="true">
          <span className="odo-s" style={{ transform: `translateY(${-Number(d) * 10}%)` }}>
            {"0123456789".split("").map((n) => <span key={n}>{n}</span>)}
          </span>
        </span>))}
    </span>);
}
