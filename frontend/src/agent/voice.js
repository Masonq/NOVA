/** Hands-free voice I/O: mic with voice-activity detection (adaptive noise floor, pre-roll),
 *  WAV 16 kHz encoding, ordered playback of the agent's sentences, live level for the orb, barge-in. */
const TARGET = 16000;

function toWav16k(chunks, rate) {
  const len = chunks.reduce((a, c) => a + c.length, 0);
  const all = new Float32Array(len);
  let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
  const ratio = rate / TARGET, n = Math.floor(len / ratio);
  const pcm = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio), b = Math.min(len, Math.floor((i + 1) * ratio));
    let s = 0; for (let k = a; k < b; k++) s += all[k];
    const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2), dv = new DataView(buf);
  const w = (p, s) => [...s].forEach((ch, i) => dv.setUint8(p + i, ch.charCodeAt(0)));
  w(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, TARGET, true);
  dv.setUint32(28, TARGET * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data");
  dv.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  let bin = ""; const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return { b64: btoa(bin), sec: pcm.length / TARGET };
}

export class Voice {
  constructor({ onUtterance, onBargeIn, onState }) {
    this.onUtterance = onUtterance; this.onBargeIn = onBargeIn; this.onState = onState || (() => {});
    this.level = 0; this.muted = false; this.speaking = false; this.listening = false;
    this.queue = []; this.playing = null; this.nextSeq = 0; this.pend = new Map();
  }

  async start() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    await this.ctx.resume();
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(2048, 1, 1);
    this.outAn = this.ctx.createAnalyser(); this.outAn.fftSize = 512; this.outAn.connect(this.ctx.destination);
    const rate = this.ctx.sampleRate, chunkMs = (2048 / rate) * 1000;
    const pre = []; const preMax = Math.ceil(400 / chunkMs);
    let floor = 0.006, rec = null, quiet = 0, loud = 0, startT = 0;
    this.proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0);
      let s = 0; for (let i = 0; i < d.length; i += 2) s += d[i] * d[i];
      const rms = Math.sqrt(s / (d.length / 2));
      const copy = new Float32Array(d);
      if (this.muted) { this.level *= 0.8; return; }
      const thr = Math.max(0.012, floor * 3) * (this.speaking ? 2.6 : 1);
      if (!rec) {
        floor = floor * 0.97 + Math.min(rms, 0.05) * 0.03;
        pre.push(copy); if (pre.length > preMax) pre.shift();
        loud = rms > thr ? loud + 1 : 0;
        if (loud >= (this.speaking ? 4 : 2)) {
          if (this.speaking) { this.stopPlayback(); this.onBargeIn?.(); }
          rec = [...pre]; quiet = 0; startT = performance.now(); this.listening = true; this.onState("listening");
        }
      } else {
        rec.push(copy);
        quiet = rms < thr * 0.7 ? quiet + chunkMs : 0;
        const dur = performance.now() - startT;
        if ((quiet > 850 && dur > 450) || dur > 30000) {
          const chunks = rec; rec = null; this.listening = false; pre.length = 0; loud = 0;
          if (dur - quiet > 300) { const w = toWav16k(chunks, rate); this.onUtterance(w); } else this.onState("idle");
        }
      }
      if (!this.speaking) this.level = this.level * 0.6 + Math.min(1, rms * 9) * 0.4;
    };
    src.connect(this.proc);
    const mute = this.ctx.createGain(); mute.gain.value = 0;
    this.proc.connect(mute); mute.connect(this.ctx.destination);
    this._lvl = setInterval(() => {
      if (!this.speaking) return;
      const a = new Uint8Array(this.outAn.fftSize); this.outAn.getByteTimeDomainData(a);
      let s = 0; for (const v of a) s += ((v - 128) / 128) ** 2;
      this.level = this.level * 0.5 + Math.min(1, Math.sqrt(s / a.length) * 5) * 0.5;
    }, 50);
  }

  setMuted(m) { this.muted = m; }

  /** Sentences arrive with seq numbers; they are played strictly in order. */
  async enqueue(seq, url) {
    try {
      const r = await fetch(url); const buf = await this.ctx.decodeAudioData(await r.arrayBuffer());
      this.pend.set(seq, buf); this._pump();
    } catch { this.pend.set(seq, null); this._pump(); }
  }
  _pump() {
    if (this.playing) return;
    while (this.pend.has(this.nextSeq) && this.pend.get(this.nextSeq) === null) { this.pend.delete(this.nextSeq); this.nextSeq++; }
    const buf = this.pend.get(this.nextSeq);
    if (!buf) { if (this.speaking && this.turnDone && !this.pend.size) { this.speaking = false; this.onState("idle"); } return; }
    this.pend.delete(this.nextSeq); this.nextSeq++;
    const s = this.ctx.createBufferSource(); s.buffer = buf; s.connect(this.outAn);
    this.playing = s; this.speaking = true; this.onState("speaking");
    s.onended = () => { if (this.playing === s) { this.playing = null; this._pump(); } };
    s.start();
  }
  newTurn() { this.stopPlayback(); this.nextSeq = 0; this.pend.clear(); this.turnDone = false; }
  endTurn() { this.turnDone = true; this._pump(); }
  stopPlayback() {
    const p = this.playing; this.playing = null; this.pend.clear();
    if (p) { try { p.onended = null; p.stop(); } catch {} }
    if (this.speaking) { this.speaking = false; this.onState("idle"); }
  }
  stop() {
    this.stopPlayback(); clearInterval(this._lvl);
    try { this.proc && (this.proc.onaudioprocess = null); } catch {}
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close().catch(() => {});
  }
}
