const KEY = "nova_token";
export const auth = {
  get: () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } },
  set: (t) => { try { localStorage.setItem(KEY, t); } catch {} },
  clear: () => { try { localStorage.removeItem(KEY); } catch {} },
};

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", body, signal } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = auth.get();
  if (t) headers.Authorization = "Bearer " + t;
  let r;
  try {
    r = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, "Нет связи с сервером. Проверьте интернет и попробуйте ещё раз");
  }
  if (r.status === 401) { auth.clear(); window.dispatchEvent(new Event("nova:logout")); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, data.detail || "Что-то пошло не так, попробуйте ещё раз");
  return data;
}

/** POST that answers with Server-Sent Events; calls onEvent for each data line. */
export async function stream(path, body, onEvent, signal) {
  const t = auth.get();
  const r = await fetch(path, {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + t },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new ApiError(r.status, d.detail || "Не удалось отправить сообщение");
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data:")) { try { onEvent(JSON.parse(line.slice(5))); } catch {} }
      }
    }
  }
}

export async function upload(file) {
  const fd = new FormData(); fd.append("file", file);
  const t = auth.get();
  let r;
  try { r = await fetch("/api/uploads", { method: "POST", headers: t ? { Authorization: "Bearer " + t } : {}, body: fd }); }
  catch { throw new ApiError(0, "Нет связи с сервером"); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, d.detail || "Не удалось загрузить фото");
  return d.url;
}
