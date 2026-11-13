"""Russian quality check for Gemini voices via OpenRouter: TTS -> transcription -> text similarity.
Usage (on the server): python tools/russian_check.py <report.md>"""
import base64, difflib, os, re, sys, time
import httpx

def env(k):
    if os.environ.get(k): return os.environ[k]
    try:
        for line in open("/opt/nova/.env"):
            if line.startswith(k + "="): return line.split("=", 1)[1].strip()
    except OSError: pass
    return ""

B = "https://openrouter.ai/api/v1"
H = {"Authorization": "Bearer " + env("OPENROUTER_KEY"), "Content-Type": "application/json", "X-Title": "NOVA check"}
STYLE = "Говори по-русски живо и тепло, естественным темпом, с лёгкими паузами и улыбкой в голосе, без дикторской интонации."
PH = ["Привет! Я NOVA. Скажи, что хочешь создать, и я всё сделаю сам.",
      "Сегодня в Белграде плюс двенадцать, к вечеру обещают небольшой дождь.",
      "Ёжик в тумане искал лошадку, но нашёл только свой фонарик.",
      "Счёт за третий квартал: двести сорок семь тысяч восемьсот рублей."]
norm = lambda s: re.sub(r"[^а-яa-z0-9 ]", "", s.lower().replace("ё", "е")).split()

def wav(pcm, rate=24000):
    import io, wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return b.getvalue()

def post(cl, path, body):
    last = ""
    for a in range(3):
        try: r = cl.post(B + path, headers=H, json=body)
        except httpx.HTTPError as e: last = type(e).__name__; time.sleep(2); continue
        if r.status_code == 200: return r
        last = f"{r.status_code} {r.text[:160]}"
        if r.status_code not in (408, 429, 500, 502, 503, 504): break
        time.sleep(2 * (a + 1))
    raise RuntimeError(last)

def main(path):
    out = ["# Проверка русского: голоса Gemini через OpenRouter", "", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "",
           "| Модель | Голос | Совпадение текста | Время | Что распозналось |", "|---|---|---|---|---|"]
    with httpx.Client(timeout=120) as cl:
        for model, voice in [("google/gemini-3.8-flash-tts", "Sulafat"), ("google/gemini-3.8-flash-lite-tts", "Sulafat"), ("google/gemini-3.8-flash-tts", "Puck")]:
            sims = []
            for t in PH:
                try:
                    t0 = time.time()
                    pcm = post(cl, "/audio/speech", {"model": model, "input": t, "voice": voice, "instructions": STYLE, "response_format": "pcm"}).content
                    dt = time.time() - t0
                    b64 = base64.b64encode(wav(pcm)).decode()
                    r = post(cl, "/chat/completions", {"model": "google/gemini-3.8-flash", "messages": [{"role": "user", "content": [
                        {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
                        {"type": "text", "text": "Дословно запиши русскую речь из аудио. Числа пиши словами. Только текст."}]}]}).json()
                    tr = (r["choices"][0]["message"].get("content") or "").strip()
                    s = difflib.SequenceMatcher(None, norm(t), norm(tr)).ratio(); sims.append(s)
                    out.append(f"| {model} | {voice} | {s:.2f} | {dt:.1f} с, {len(pcm)/48000:.1f} с звука | {tr} |")
                except Exception as e:
                    out.append(f"| {model} | {voice} | ошибка | — | {str(e)[:140]} |")
            if sims: out.append(f"| **{model}** | **{voice}** | **среднее {sum(sims)/len(sims):.3f}** | | |")
    open(path, "w").write("\n".join(out) + "\n"); print("\n".join(out))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "russian.md")
