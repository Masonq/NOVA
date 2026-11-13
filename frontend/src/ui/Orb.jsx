import { useEffect, useRef } from "react";

/** Living wireframe orb (blue -> magenta mesh with a particle halo). One shared render loop for all orbs;
 *  paused off-screen and when the app is hidden. `energy` (0..1) will follow the voice in stage 3. */
const orbs = new Set();
let raf = 0;
const reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

function loop(now) {
  raf = 0;
  let any = false;
  for (const o of orbs) if (o.visible) { o.draw(now / 1000); any = true; }
  if (any && !document.hidden && !reduce) raf = requestAnimationFrame(loop);
}
function kick() { if (!raf) raf = requestAnimationFrame(loop); }
if (typeof document !== "undefined") document.addEventListener("visibilitychange", () => !document.hidden && kick());

function makeOrb(canvas, size, dense) {
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  canvas.width = canvas.height = Math.round(size * dpr);
  const ctx = canvas.getContext("2d");
  const LAT = dense ? 34 : 20, LON = dense ? 46 : 28, SEG = dense ? 72 : 36;
  const P = dense ? 320 : 90;
  const parts = Array.from({ length: P }, () => ({
    a: Math.random() * Math.PI * 2, b: Math.acos(2 * Math.random() - 1),
    r: 1.12 + Math.random() * 0.3, s: 0.15 + Math.random() * 0.5, tw: Math.random() * 6.28,
  }));
  const o = { visible: true, energy: 0, burst: 0 };
  const lw = Math.max(0.55, (size * dpr) / 260);
  o.levelRef = null;

  o.draw = (t) => {
    const W = canvas.width, c = W / 2, R = W * 0.38;
    o.burst *= 0.95;
    const live = o.levelRef ? o.levelRef() : 0;
    o.smooth = (o.smooth || 0) * 0.8 + live * 0.2;
    const e = Math.min(1.6, o.energy + o.burst + o.smooth * 1.4);
    const amp = 0.09 + 0.12 * e;
    const dt = o.lastT ? Math.min(0.1, t - o.lastT) : 0; o.lastT = t;
    o.ang = (o.ang ?? t * 0.32) + dt * (0.32 + 0.6 * o.smooth);
    const rotY = o.ang, tilt = 0.38 + Math.sin(t * 0.4) * 0.12;
    const cy = Math.cos(rotY), sy = Math.sin(rotY), ct = Math.cos(tilt), st = Math.sin(tilt);
    const shift = Math.sin(t * 0.25) * 0.35;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, W);

    // soft glow behind the mesh
    const g = ctx.createRadialGradient(c * 0.92, c * 1.05, R * 0.2, c, c, R * 1.55);
    g.addColorStop(0, `rgba(160,70,255,${0.42 + 0.25 * e})`); g.addColorStop(0.6, "rgba(80,70,255,.2)"); g.addColorStop(1, "rgba(20,10,60,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, W);

    // colour flows from blue (upper left) to magenta (lower right) and slowly drifts
    const grad = ctx.createLinearGradient(c - R * (1 + shift), c - R, c + R, c + R * (1 - shift));
    grad.addColorStop(0, "#5AA8FF"); grad.addColorStop(0.5, "#B07CFF"); grad.addColorStop(1, "#FF5BE4");

    const pt = (th, ph) => {
      const d = 1 + amp * (Math.sin(3 * th + t * 1.3) * Math.cos(2 * ph - t * 0.9) + 0.6 * Math.sin(5 * ph + 2 * th - t * 0.7) + 0.35 * Math.sin(7 * th - 3 * ph + t * 1.9));
      let x = Math.sin(th) * Math.cos(ph) * d, y = Math.cos(th) * d, z = Math.sin(th) * Math.sin(ph) * d;
      const x1 = x * cy - z * sy, z1 = x * sy + z * cy;
      const y2 = y * ct - z1 * st, z2 = y * st + z1 * ct;
      const k = 1 / (1 - z2 * 0.18);
      return [c + x1 * R * k, c - y2 * R * k, z2];
    };
    const line = (fn) => {
      let prev = fn(0);
      for (let i = 1; i <= SEG; i++) {
        const p = fn(i / SEG);
        (p[2] + prev[2] > 0 ? front : back).push(prev[0], prev[1], p[0], p[1]);
        prev = p;
      }
    };
    const front = [], back = [];
    for (let i = 1; i < LAT; i++) { const th = (i / LAT) * Math.PI; line((u) => pt(th, u * Math.PI * 2)); }
    for (let j = 0; j < LON; j++) { const ph = (j / LON) * Math.PI * 2; line((u) => pt(0.0001 + u * (Math.PI - 0.0002), ph)); }
    const stroke = (arr, alpha, w) => {
      ctx.globalAlpha = alpha; ctx.lineWidth = w; ctx.strokeStyle = grad; ctx.beginPath();
      for (let i = 0; i < arr.length; i += 4) { ctx.moveTo(arr[i], arr[i + 1]); ctx.lineTo(arr[i + 2], arr[i + 3]); }
      ctx.stroke();
    };
    ctx.globalCompositeOperation = "lighter";      // neon: light adds up where lines cross
    stroke(back, 0.28, lw * 0.8);
    stroke(front, 0.22, lw * 3.2);                 // soft glow under the lines
    stroke(front, 0.95, lw);

    // particle halo
    ctx.fillStyle = grad;
    const ps = Math.max(0.7, lw * 1.1);
    for (const p of parts) {
      const a = p.a + t * p.s * 0.25, rr = p.r + 0.22 * o.burst + 0.03 * Math.sin(t * 1.5 + p.tw);
      const x = Math.sin(p.b) * Math.cos(a) * rr, y = Math.cos(p.b) * rr, z = Math.sin(p.b) * Math.sin(a) * rr;
      const x1 = x * cy - z * sy;
      ctx.globalAlpha = (z < 0 ? 0.35 : 0.85) * (0.45 + 0.55 * Math.abs(Math.sin(t * 1.7 + p.tw)));
      ctx.fillRect(c + x1 * R - ps / 2, c - y * R - ps / 2, ps, ps);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  };
  return o;
}

export default function Orb({ size = 54, dense = false, energy = 0, className = "", pulseOnTap = true, level = null }) {
  const ref = useRef(null);
  const orb = useRef(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const o = makeOrb(cv, size, dense);
    orb.current = o; orbs.add(o);
    const io = new IntersectionObserver(([en]) => { o.visible = en.isIntersecting; if (o.visible) kick(); });
    io.observe(cv);
    o.draw(performance.now() / 1000);
    kick();
    return () => { io.disconnect(); orbs.delete(o); };
  }, [size, dense]);
  useEffect(() => { if (orb.current) orb.current.energy = energy; }, [energy]);
  useEffect(() => { if (orb.current) orb.current.levelRef = level; }, [level, size]);
  const pulse = () => { if (pulseOnTap && orb.current) { orb.current.burst = 1; kick(); } };
  return <canvas ref={ref} className={"orb " + className} style={{ width: size, height: size }} aria-hidden="true" onPointerDown={pulse} />;
}
