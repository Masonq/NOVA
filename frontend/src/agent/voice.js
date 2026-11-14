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
  /** onUtterance(wav) — a phrase is over (sent early, after ~0.55 s of quiet);
   *  onResume() — the user went on talking before the answer started: drop that request, the phrase continues;
   *  onBargeIn() — the user really talks over NOVA (not a cough): playback stopped. */
  constructor({ onUtterance, onBargeIn, onResume, onState }) {
    this.onUtterance = onUtterance; this.onBargeIn = onBargeIn; this.onResume = onResume; this.onState = onState || (() => {});
    this.level = 0; this.muted = false; this.speaking = false; this.listening = false;
    this.sents = new Map(); this.nextSeq = 0; this.srcs = new Set(); this.t = 0; this.turnDone = true;
    this.tentative = null;            // the last phrase, kept to be continued if the user goes on talking
  }

  async start() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    await this.ctx.resume();
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(2048, 1, 1);
    this.outAn = this.ctx.createAnalyser(); this.outAn.fftSize = 512; this.outAn.connect(this.ctx.destination);
    this.duckGain = this.ctx.createGain(); this.duckGain.connect(this.outAn);
    const rate = this.ctx.sampleRate, chunkMs = (2048 / rate) * 1000;
    const pre = []; const preMax = Math.ceil(400 / chunkMs);
    let floor = 0.006, rec = null, quiet = 0, loud = 0, startT = 0, duckQuiet = 0;
    this.proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0);
      let s = 0; for (let i = 0; i < d.length; i += 2) s += d[i] * d[i];
      const rms = Math.sqrt(s / (d.length / 2));
      const copy = new Float32Array(d);
      if (this.muted) { this.level *= 0.8; return; }
      // while NOVA speaks, the speaker's echo leaks into the mic: a higher bar, and a short deaf window when a sentence starts
      const echo = this.speaking && performance.now() - (this.sentenceAt || 0) < 300;
      const thr = Math.max(0.012, floor * 3) * (this.speaking ? 3.4 : 1);
      if (!rec) {
        floor = floor * 0.97 + Math.min(rms, 0.05) * 0.03;
        pre.push(copy); if (pre.length > preMax) pre.shift();
        loud = rms > thr && !echo ? loud + 1 : 0;
        if (this.speaking) {
          // talking over NOVA: first she turns down and listens; real speech (~0.35 s) stops her, a cough lets her go on
          if (loud >= 2 && !this.ducked) this._duck(true);
          if (this.ducked) { duckQuiet = loud ? 0 : duckQuiet + chunkMs; if (duckQuiet > 450) this._duck(false); }
          if (loud >= Math.ceil(350 / chunkMs)) {
            this.stopPlayback(); this.onBargeIn?.();
            rec = [...pre]; quiet = 0; startT = performance.now(); this.listening = true; this.onState("listening");
          }
        } else if (loud >= 2) {
          const t = this.tentative;
          if (t && (t.hold || performance.now() - t.at < 2500)) {      // the same phrase goes on: continue it, cancel the early request
            this.tentative = null; this.onResume?.();
            rec = [...t.chunks, ...pre]; startT = t.start;
          } else { this.tentative = null; rec = [...pre]; startT = performance.now(); }
          quiet = 0; this.listening = true; this.onState("listening");
        }
      } else {
        rec.push(copy);
        quiet = rms < thr * 0.7 ? quiet + chunkMs : 0;
        const dur = performance.now() - startT;
        if ((quiet > 550 && dur > 400) || dur > 45000) {
          const chunks = rec; rec = null; this.listening = false; pre.length = 0; loud = 0;
          if (dur - quiet > 300) {
            this.tentative = { chunks, at: performance.now(), start: startT };
            this.onUtterance(toWav16k(chunks, rate));
          } else this.onState("idle");
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
  /** The server says the phrase isn't finished: keep it, the next words are added to it. */
  hold() { if (this.tentative) this.tentative.hold = true; }
  /** The answer has started: the phrase is final. */
  commit() { this.tentative = null; }

  _duck(on) {
    this.ducked = on;
    const g = this.duckGain.gain, now = this.ctx.currentTime;
    g.cancelScheduledValues(now); g.setValueAtTime(g.value, now); g.linearRampToValueAtTime(on ? 0.22 : 1, now + (on ? 0.06 : 0.2));
  }

  /** Streamed sound: pieces of sentence `seq` (16-bit PCM, 24 kHz, base64) are played gaplessly, sentences strictly in order. */
  pcm(seq, b64) {
    const bin = atob(b64), n = bin.length >> 1, f = new Float32Array(n);
    for (let i = 0; i < n; i++) { let v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8); if (v > 32767) v -= 65536; f[i] = v / 32768; }
    const st = this.sents.get(seq) || { q: [], ended: false };
    st.q.push(f); this.sents.set(seq, st); this._pump();
  }
  pcmEnd(seq) { const st = this.sents.get(seq) || { q: [], ended: false }; st.ended = true; this.sents.set(seq, st); this._pump(); }
  _pump() {
    if (!this.ctx) return;
    for (;;) {
      const st = this.sents.get(this.nextSeq);
      if (!st) break;
      while (st.q.length) {
        const f = st.q.shift(), buf = this.ctx.createBuffer(1, f.length, 24000); buf.copyToChannel(f, 0);
        const s = this.ctx.createBufferSource(); s.buffer = buf; s.connect(this.duckGain);
        const now = this.ctx.currentTime;
        if (this.t < now + 0.02) { this.t = now + 0.06; if (!st.started) this.sentenceAt = performance.now(); }   // (re)start with a small cushion
        st.started = true;
        s.start(this.t); this.t += buf.duration; this.srcs.add(s);
        s.onended = () => { this.srcs.delete(s); this._idleCheck(); };
        if (!this.speaking) { this.speaking = true; this.onState("speaking"); }
      }
      if (!st.ended) break;
      this.sents.delete(this.nextSeq); this.nextSeq++;
    }
  }
  _idleCheck() {
    if (!this.srcs.size && this.turnDone && !this.sents.size && this.speaking) {
      this.speaking = false; if (this.ducked) this._duck(false); this.onState("idle");
    }
  }
  newTurn() { this.stopPlayback(); this.nextSeq = 0; this.sents.clear(); this.turnDone = false; }
  endTurn() { this.turnDone = true; this._idleCheck(); }
  stopPlayback() {
    for (const s of this.srcs) { try { s.onended = null; s.stop(); } catch {} }
    this.srcs.clear(); this.sents.clear(); this.t = 0;
    if (this.ducked) this._duck(false);
    if (this.speaking) { this.speaking = false; this.onState("idle"); }
  }
  stop() {
    this.stopPlayback(); clearInterval(this._lvl);
    try { this.proc && (this.proc.onaudioprocess = null); } catch {}
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close().catch(() => {});
  }
}

/** Tap-to-start / tap-to-stop dictation for the composer: raw mic → WAV 16 kHz (max 2 min), plus a live level. */
export class Dictation {
  async start(onLevel) {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    await this.ctx.resume();
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(2048, 1, 1);
    this.chunks = []; this.rate = this.ctx.sampleRate; this.t0 = performance.now();
    this.proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(d));
      if (onLevel) { let s = 0; for (let i = 0; i < d.length; i += 4) s += d[i] * d[i]; onLevel(Math.min(1, Math.sqrt(s / (d.length / 4)) * 9)); }
      if (performance.now() - this.t0 > 120000) this.onLimit?.();
    };
    src.connect(this.proc);
    const mute = this.ctx.createGain(); mute.gain.value = 0;
    this.proc.connect(mute); mute.connect(this.ctx.destination);
  }
  stop() {
    try { this.proc?.disconnect(); } catch { /* already closed */ }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close().catch(() => {});
    const w = this.chunks?.length ? toWav16k(this.chunks, this.rate) : null;
    this.chunks = []; return w;
  }
}
