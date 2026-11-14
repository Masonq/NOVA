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


/* ---------- WebGL energy orb: glowing rim, silky particle ribbons flowing around it, veils inside ---------- */
const VS = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const FS = `precision highp float;
uniform vec2 res; uniform float t; uniform float e; uniform float ang; uniform float sm;
float h(vec3 p){p=fract(p*0.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float n3(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);
 return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),
            mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){float a=.5,s=0.;for(int i=0;i<4;i++){s+=a*n3(p);p=p*2.03+vec3(1.7,9.2,3.1);a*=.5;}return s;}
mat3 rotY(float a){float c=cos(a),s=sin(a);return mat3(c,0,-s,0,1,0,s,0,c);}
mat3 rotX(float a){float c=cos(a),s=sin(a);return mat3(1,0,0,0,c,s,0,-s,c);}
float fbm3(vec3 p){return .55*n3(p)+.3*n3(p*2.1+vec3(4.2))+.15*n3(p*4.3+vec3(1.3));}
float ribbon(vec3 p,float tt,float k){
 float d=fbm3(p*.85+vec3(tt*.11,tt*.07,-tt*.05)+k);
 float v=p.y*1.6+d*3.2+sin(p.x*1.7+tt*.2+k)*.6;
 // phone GPUs may return |sin| a hair above 1: pow() of a negative number is NaN, and NaN pixels came out as flat blue
 // patches on the sphere — clamp before pow
 float b=clamp(1.-abs(sin(v*2.6)),0.,1.);
 return pow(b,7.)+pow(b,40.)*.8;
}
float silk(vec3 p,float tt){
 vec3 q=p;
 vec3 r2=vec3(p.z,p.x,p.y), r3=vec3(p.y,p.z,-p.x);
 float a=ribbon(q,tt,0.)*smoothstep(.25,.65,fbm3(q*1.1+tt*.05));
 float b=ribbon(r2,tt*.9,3.7)*smoothstep(.3,.7,fbm3(r2*1.1-tt*.04+2.));
 float c=ribbon(r3,tt*1.1,7.1)*smoothstep(.35,.75,fbm3(r3*1.2+tt*.03+5.));
 float veil=smoothstep(.45,.85,fbm3(p*.9+vec3(0.,tt*.06,0.)))*.35;
 return a+b*.8+c*.6+veil;
}
vec3 pal(float k){
 vec3 blue=vec3(.12,.32,1.),vio=vec3(.48,.16,1.),pink=vec3(1.,.16,.66),cyan=vec3(.25,.78,1.);
 // a closed loop blue → violet → pink → cyan → back to blue. It used to end on cyan and restart on blue, so wherever
 // the hue noise crossed 1.0 the colour jumped: those were the flat blue patches on and beside the sphere
 k=fract(k);
 return k<.3?mix(blue,vio,k/.3):k<.62?mix(vio,pink,(k-.3)/.32):k<.88?mix(pink,cyan*.9+blue*.1,(k-.62)/.26):mix(cyan*.9+blue*.1,blue,(k-.88)/.12);
}
void main(){
 vec2 uv=(gl_FragCoord.xy-.5*res)/(.5*res.y);
 float tt=t*(1.+e*1.6);
 float a=atan(uv.y,uv.x);
 float R=.8+.012*sin(t*1.3)+e*.035*(n3(vec3(a*2.,tt*.8,0.))-.5)*2.;
 float r=length(uv)/R;
 vec3 col=vec3(0.);
 float hue=.12+.5+.5*sin(a+tt*.22)*.42+fbm(vec3(uv*1.5,tt*.1))*.35;
 float edgeN=fbm(vec3(a*2.2,tt*.35,7.));
 if(r<1.){
  float z=sqrt(max(1.-r*r,0.));
  vec3 n=vec3(uv/R,z);
  mat3 m=rotY(ang)*rotX(.35+.12*sin(t*.31));
  vec3 pf=m*n, pb=m*vec3(n.xy,-z);
  float fres=pow(clamp(1.-z,0.,1.),1.7);
  float sf=silk(pf,tt), sb=silk(pb+vec3(3.1),tt);
  float grain=mix(.78+.44*h(vec3(floor(gl_FragCoord.xy/1.4),floor(t*4.))),1.,sm);   // fine sparkle; none on a small orb
  float front=sf*(.3+2.6*fres)*grain*(1.+sm*.35);
  float back=sb*(.3+.8*fres)*grain*.6;
  vec3 cf=pal(hue+sf*.3+pf.y*.18), cb=mix(vec3(.25,.35,1.),pal(hue+.3+pb.x*.2),.5);
  col+=cf*front*(1.2+e*.8)+cb*back;
  float band=smoothstep(.62+.22*edgeN,1.,r);                 // ragged fiery zone along the rim
  col+=pal(hue+.08+edgeN*.3)*band*band*(.85+1.3*sf)*(1.+e*.7);
  float rim=exp(-(1.-r)*mix(30.,16.,sm));
  col+=mix(vec3(1.),pal(hue+.1*sin(a*2.)),.82)*rim*(1.05+sm*.4);
  col+=vec3(.06,.04,.16)*z;
 }else{
  float g=exp(-(r-1.)*7.)*.7+exp(-(r-1.)*30.)*.9;
  g*=smoothstep(1.,.86,length(uv));      // the glow fades out inside the canvas: no visible square edge around the orb
  col+=pal(hue+.05*sin(a*3.+tt))*g*(.9+e*.6);
 }
 col=1.-exp(-col*1.35);
 float lum=dot(col,vec3(.3,.5,.2)); col=max(vec3(0.),mix(vec3(lum),col,1.45));
 col=clamp(col,0.,1.);
 float al=clamp(max(max(col.r,col.g),col.b),0.,1.);   // = brightest channel: light adds to the page, never darkens it
 gl_FragColor=vec4(min(col,vec3(al)),al);          // premultiplied: colour never exceeds alpha
}`;

let GL_OK = null;
function glSupported() {
  if (GL_OK !== null) return GL_OK;
  try {
    const c = document.createElement("canvas"); c.width = c.height = 4;
    const g = c.getContext("webgl");
    if (!g) return (GL_OK = false);
    const x = g.createShader(g.FRAGMENT_SHADER); g.shaderSource(x, FS); g.compileShader(x);
    GL_OK = !!g.getShaderParameter(x, g.COMPILE_STATUS);
    g.getExtension("WEBGL_lose_context")?.loseContext();
  } catch { GL_OK = false; }
  return GL_OK;
}

function makeGLOrb(canvas, size) {
  if (!glSupported()) return null;
  const dpr = Math.min(window.devicePixelRatio || 1, size > 120 ? 2 : 3);
  canvas.width = canvas.height = Math.round(size * dpr);
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
  if (!gl) return null;
  const sh = (type, src) => { const x = gl.createShader(type); gl.shaderSource(x, src); gl.compileShader(x); return gl.getShaderParameter(x, gl.COMPILE_STATUS) ? x : null; };
  const vs = sh(gl.VERTEX_SHADER, VS), fs = sh(gl.FRAGMENT_SHADER, FS);
  if (!vs || !fs) return null;
  const pr = gl.createProgram(); gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
  gl.useProgram(pr);
  const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = { res: gl.getUniformLocation(pr, "res"), t: gl.getUniformLocation(pr, "t"), e: gl.getUniformLocation(pr, "e"), ang: gl.getUniformLocation(pr, "ang"), sm: gl.getUniformLocation(pr, "sm") };
  gl.disable(gl.BLEND);                  // one full-screen pass writes the final premultiplied pixels
  const o = { visible: true, energy: 0, burst: 0, levelRef: null, gl: true };
  const seed = Math.random() * 50;
  // time since this orb was created, wrapped: phone GPUs lose float precision on large times (hours in Telegram),
  // which turned the noise into flat blocks — the blue patch beside the sphere
  const t0 = performance.now() / 1000;
  o.draw = (t) => {
    if (gl.isContextLost()) return;
    o.burst *= 0.94;
    const live = o.levelRef ? o.levelRef() : 0;
    o.smooth = (o.smooth || 0) * 0.82 + live * 0.18;
    const e = Math.min(1.5, o.energy + o.burst + o.smooth * 1.3);
    const dt = o.lastT ? Math.min(0.1, t - o.lastT) : 0; o.lastT = t;
    o.ang = (o.ang || 0) + dt * (0.18 + 0.7 * e);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(U.res, canvas.width, canvas.height);
    gl.uniform1f(U.t, ((t - t0) % 1800) + seed); gl.uniform1f(U.e, e); gl.uniform1f(U.ang, o.ang % 6283.185);
    gl.uniform1f(U.sm, size < 90 ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  return o;
}

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
    const o = makeGLOrb(cv, size) || makeOrb(cv, size, dense);
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
