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
        if k:   # the key is locked to the server IP: check the IPv4 route the app uses and the default route
            for label, tr in (("IPv4", httpx.HTTPTransport(local_address="0.0.0.0")), ("по умолчанию", None)):
                try:
                    with httpx.Client(timeout=20, transport=tr) as c2:
                        r = c2.get("https://api.kie.ai/api/v1/jobs/recordInfo", params={"taskId": "nova-check"}, headers={"Authorization": "Bearer " + k}).json()
                    blocked = "whitelist" in str(r.get("msg", "")).lower()
                    out.append(f"- Kie {label}: {'IP не в белом списке' if blocked else 'адрес разрешён'} ({r.get('code')})")
                except Exception as e:
                    out.append(f"- Kie {label}: ошибка {type(e).__name__}")
            try:
                r = cl.get("https://api.kie.ai/api/v1/chat/credit", headers={"Authorization": "Bearer " + k}).json()
                out.append(f"- Kie: код {r.get('code')}, баланс {r.get('data')} кредитов {r.get('msg') or ''}")
            except Exception as e:
                out.append(f"- Kie: ошибка {type(e).__name__} {e}")
        else:
            out.append("- Kie: ключа нет")
        if env("YOOKASSA_SHOP_ID") and env("YOOKASSA_SECRET"):
            try:
                r = cl.get("https://api.yookassa.ru/v3/me", auth=(env("YOOKASSA_SHOP_ID"), env("YOOKASSA_SECRET")))
                d = r.json()
                out.append(f"- ЮKassa: {r.status_code}, магазин {d.get('account_id', '?')}, статус {d.get('status', d.get('description', '?'))}, тестовый {d.get('test')}, методы {', '.join(d.get('payment_methods', []))[:120]}")
            except Exception as e:
                out.append(f"- ЮKassa: ошибка {type(e).__name__} {e}")
        o = env("OPENROUTER_KEY")
        try:
            r = cl.get("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + o}).json().get("data", {})
            out.append(f"- OpenRouter: ключ работает, потрачено ${r.get('usage')}, лимит {r.get('limit')}")
        except Exception as e:
            out.append(f"- OpenRouter: ошибка {e}")
        # voice agent: does the model call the create tool (no generation is started here)?
        try:
            import json as _j
            tools = [{"type": "function", "function": {"name": "create_media", "description": "Подготовить генерацию",
                      "parameters": {"type": "object", "required": ["kind", "prompt"], "properties": {"kind": {"type": "string", "enum": ["image", "video", "music", "tts"]}, "prompt": {"type": "string"}}}}}]
            t0 = time.time()
            r = cl.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer " + o}, json={
                "model": "google/gemini-3.8-flash", "tools": tools,
                "messages": [{"role": "system", "content": "Ты голосовой агент NOVA. Для генераций вызывай create_media."}, {"role": "user", "content": "Сделай логотип кофейни Зерно"}]}).json()
            tc = (r["choices"][0]["message"].get("tool_calls") or [{}])[0].get("function", {})
            out.append(f"- Агент: инструмент {tc.get('name') or 'не вызван'} {tc.get('arguments', '')[:120]} за {time.time() - t0:.1f} с")
            t0 = time.time()
            r = cl.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer " + o}, json={
                "model": "google/gemini-3.8-flash", "plugins": [{"id": "web", "max_results": 3}],
                "messages": [{"role": "user", "content": "Какой сегодня курс евро к динару? Коротко."}]})
            out.append(f"- Поиск в интернете: {r.status_code}, {time.time() - t0:.1f} с: {(r.json()['choices'][0]['message'].get('content') or '')[:160] if r.status_code == 200 else r.text[:160]}")
        except Exception as e:
            out.append(f"- Агент: ошибка {type(e).__name__} {e}")
        if image:   # one real picture per photo mode through the images API (~$0.17 once)
            tests = [({"model": "bytedance-seed/seedream-5-5", "resolution": "2K"}, "Photorealistic portrait of a barista in a cosy coffee shop, morning window light, 85mm lens"),
                     ({"model": "openai/gpt-image-2.6-flare", "quality": "medium"}, "Minimalist vector logo of a coffee shop with the word \"Зерно\": a cup and a coffee bean, warm colours, plain background"),
                     ({"model": "google/gemini-nano-banana-2.1", "resolution": "2K"}, "A cosy coffee cup on a wooden table, soft daylight")]
            for extra, prompt in tests:
                model, res = extra["model"], extra.get("resolution") or extra.get("quality")
                t0 = time.time()
                try:
                    r = cl.post("https://openrouter.ai/api/v1/images", headers={"Authorization": "Bearer " + o}, timeout=240,
                                json={"prompt": prompt, "aspect_ratio": "1:1", "n": 1, **extra})
                    if r.status_code != 200:
                        out.append(f"- Фото {model} {res}: {r.status_code} {r.text[:200]}"); continue
                    d = r.json(); it = (d.get("data") or [{}])[0]
                    raw = base64.b64decode(it["b64_json"]) if it.get("b64_json") else b""
                    size = ""
                    try:
                        from PIL import Image; import io
                        size = "%sx%s" % Image.open(io.BytesIO(raw)).size
                    except Exception:
                        pass
                    out.append(f"- Фото {model} {res}: {time.time() - t0:.1f} с, {size}, {len(raw) // 1024} КБ, стоимость {(d.get('usage') or {}).get('cost')}")
                except Exception as e:
                    out.append(f"- Фото {model}: ошибка {type(e).__name__} {e}")
    open(path, "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], "--image" in sys.argv)
