"""Live check of the paid services from the server (Kie key is locked to the server IP).
Kie: free balance request. OpenRouter: one real picture (~$0.034) to confirm the response format.
Usage: python tools/services_check.py <report.md> [--image]"""
import base64, os, sys, time
import httpx


def env(k):
    if os.environ.get(k): return os.environ[k]
    try:
        for line in open("/opt/nova/.env"):
            if line.startswith(k + "="): return line.split("=", 1)[1].strip()
    except OSError: pass
    return ""


def main(path, image):
    out = ["# Проверка сервисов", "", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), ""]
    with httpx.Client(timeout=120) as cl:
        k = env("KIE_KEY")
        if k:
            try:
                r = cl.get("https://api.kie.ai/api/v1/chat/credit", headers={"Authorization": "Bearer " + k}).json()
                out.append(f"- Kie: код {r.get('code')}, баланс {r.get('data')} кредитов {r.get('msg') or ''}")
            except Exception as e:
                out.append(f"- Kie: ошибка {type(e).__name__} {e}")
        else:
            out.append("- Kie: ключа нет")
        o = env("OPENROUTER_KEY")
        try:
            r = cl.get("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + o}).json().get("data", {})
            out.append(f"- OpenRouter: ключ работает, потрачено ${r.get('usage')}, лимит {r.get('limit')}")
        except Exception as e:
            out.append(f"- OpenRouter: ошибка {e}")
        if image:
            t0 = time.time()
            body = {"model": "google/gemini-nano-banana-2.1", "modalities": ["image", "text"], "image_config": {"aspect_ratio": "1:1"},
                    "messages": [{"role": "user", "content": [{"type": "text", "text": "Minimalist vector logo of a coffee shop: a cup and a coffee bean, warm colors, plain background"}]}]}
            r = cl.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer " + o}, json=body)
            dt = time.time() - t0
            if r.status_code != 200:
                out.append(f"- Картинка: {r.status_code} {r.text[:300]}")
            else:
                d = r.json(); msg = d["choices"][0]["message"]
                ims = msg.get("images") or []
                u = ((ims[0] if ims else {}).get("image_url") or {}).get("url", "")
                kind = "base64" if u.startswith("data:") else ("ссылка" if u.startswith("http") else "нет")
                size = len(base64.b64decode(u.split(",", 1)[1])) if kind == "base64" else 0
                out.append(f"- Картинка: {dt:.1f} с, картинок {len(ims)}, формат {kind}, {size // 1024} КБ, стоимость {d.get('usage', {}).get('cost')}")
                out.append(f"- Ключи ответа: {sorted(msg.keys())}")
    open(path, "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], "--image" in sys.argv)
