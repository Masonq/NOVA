import { useEffect, useRef, useState } from "react";
import { makeVoiceOrb } from "./voiceOrb.js";
import OrbLegacy from "./OrbLegacy.jsx";

/** NOVA's orb: a glowing shader ring (WebGL2) that breathes with the voice. One render loop for all orbs, paused
 *  off-screen and while the app is hidden. Falls back to the canvas orb where WebGL2 is missing. */
const orbs = new Set();
let raf = 0;
function loop(now) {
  raf = 0;
  let any = false;
  for (const o of orbs) if (o.visible) { o.draw(now / 1000); any = true; }
  if (any && !document.hidden) raf = requestAnimationFrame(loop);
}
function kick() { if (!raf) raf = requestAnimationFrame(loop); }
if (typeof document !== "undefined") document.addEventListener("visibilitychange", () => !document.hidden && kick());

export default function Orb(props) {
  const { size = 54, energy = 0, className = "", pulseOnTap = true, level = null } = props;
  const ref = useRef(null), orb = useRef(null);
  const [legacy, setLegacy] = useState(false);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const o = makeVoiceOrb(cv, size);
    if (!o) { setLegacy(true); return; }
    orb.current = o; o.energy = energy; o.levelRef = level; orbs.add(o);
    const io = new IntersectionObserver(([en]) => { o.visible = en.isIntersecting; if (o.visible) kick(); });
    io.observe(cv);
    o.draw(performance.now() / 1000); kick();
    return () => { io.disconnect(); orbs.delete(o); o.destroy(); orb.current = null; };
  }, [size]);
  useEffect(() => { if (orb.current) orb.current.energy = energy; }, [energy]);
  useEffect(() => { if (orb.current) orb.current.levelRef = level; }, [level]);
  if (legacy) return <OrbLegacy {...props} />;
  const tap = () => { if (pulseOnTap && orb.current) { orb.current.tap(); kick(); } };
  return <canvas ref={ref} className={"orb " + className} style={{ width: size, height: size }} aria-hidden="true" onPointerDown={tap} />;
}
