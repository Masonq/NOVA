/* NOVA service worker: pages always come from the network (fresh after every deploy),
   hashed assets are cached forever, and an offline screen is shown when there is no connection. */
const V = "nova-v1";
const OFFLINE = `<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0A0A0C"><title>NOVA — нет сети</title><style>body{margin:0;min-height:100vh;display:flex;flex-direction:column;
align-items:center;justify-content:center;gap:14px;background:#0A0A0C;color:#F2F2F5;font:15px/1.5 -apple-system,system-ui,sans-serif;text-align:center;padding:24px}
img{width:110px;height:110px;border-radius:28px}h1{margin:6px 0 0;font-size:20px}p{margin:0;color:#8A8A94;max-width:280px}
button{margin-top:10px;height:50px;padding:0 26px;border:0;border-radius:16px;background:#fff;color:#0A0A0C;font-weight:700;font-size:15px}</style></head>
<body><img src="/icon-192.png" alt=""><h1>Нет подключения</h1><p>Проверьте интернет — NOVA откроется, как только связь вернётся.</p>
<button onclick="location.reload()">Повторить</button><script>addEventListener("online",()=>location.reload())</script></body></html>`;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll(["/icon-192.png", "/manifest.webmanifest"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin) return;
  if (u.pathname.startsWith("/api/") || u.pathname.startsWith("/files/") || u.pathname.startsWith("/s/")) return;
  if (r.mode === "navigate") {
    e.respondWith(fetch(r).catch(() => new Response(OFFLINE, { headers: { "Content-Type": "text/html; charset=utf-8" } })));
    return;
  }
  if (u.pathname.startsWith("/assets/")) {      // file names contain a hash: safe to keep
    e.respondWith(caches.open(V).then(async (c) => (await c.match(r)) || fetch(r).then((res) => { if (res.ok) c.put(r, res.clone()); return res; })));
  }
});
