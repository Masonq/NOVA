"""Russian quality check for voice models: TTS -> transcription -> text similarity, and a Live round-trip.
Writes a markdown report. Usage: python tools/russian_check.py <report.md>"""
import asyncio, base64, difflib, json, os, re, sys, time
import httpx

def env(k):
    v = os.environ.get(k)
    if v: return v
    for line in open("/opt/nova/.env"):
        if line.startswith(k + "="): return line.split("=", 1)[1].strip()
    return ""

K = env("GEMINI_KEY"); B = "https://generativelanguage.googleapis.com/v1beta"
H = {"x-goog-api-key": K, "Content-Type": "application/json"}
PH = ["Привет! Я NOVA. Скажи, что хочешь создать, и я всё сделаю сам.",
      "Сегодня в Белграде плюс двенадцать, к вечеру обещают небольшой дождь.",
      "Ёжик в тумане искал лошадку, но нашёл только свой фонарик.",
      "Счёт за третий квартал: двести сорок семь тысяч восемьсот рублей."]
TRANSCRIBE = ["gemini-3.5-flash", "gemini-3.8-flash"]
norm = lambda s: re.sub(r"[^а-яa-z0-9 ]", "", s.lower().replace("ё", "е")).split()

def gen(cl, models, body):
    last = ""
    for m in models:
        for a in range(3):
            try: r = cl.post(f"{B}/models/{m}:generateContent", headers=H, json=body)
            except httpx.HTTPError as e: last = f"{m}: {type(e).__name__}"; time.sleep(3); continue
            if r.status_code == 200: return r.json()
            last = f"{m}: {r.status_code} {r.text[:160]}"
            if r.status_code not in (429, 500, 503): break
            time.sleep(3 * (a + 1))
    raise RuntimeError(last)

def tts_block(cl):
    lines = []
    for model in ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]:
        sims = []
        for t in PH:
            try:
                t0 = time.time()
                d = gen(cl, [model], {"contents": [{"parts": [{"text": t}]}], "generationConfig": {"responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}})
                p = d["candidates"][0]["content"]["parts"][0]["inlineData"]; dt = time.time() - t0
                tr = gen(cl, TRANSCRIBE, {"contents": [{"parts": [{"inlineData": p}, {"text": "Дословно запиши русскую речь из аудио. Числа пиши словами. Только текст."}]}]})
                tr = "".join(x.get("text", "") for x in tr["candidates"][0]["content"]["parts"] if not x.get("thought")).strip()
                s = difflib.SequenceMatcher(None, norm(t), norm(tr)).ratio(); sims.append(s)
                lines.append(f"| {model} | {s:.2f} | {dt:.1f} с | {tr} |")
            except Exception as e:
                lines.append(f"| {model} | ошибка | — | {str(e)[:120]} |")
        if sims: lines.append(f"| **{model}: среднее** | **{sum(sims)/len(sims):.3f}** | | |")
    return ["## Озвучка: синтез → распознавание", "", "| Модель | Совпадение текста | Время | Что распозналось |", "|---|---|---|---|", *lines]

async def live_block():
    import websockets
    url = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    out = ["", "## Живой голос (gemini-3.8-live)", ""]
    try:
        async with websockets.connect(url, additional_headers={"x-goog-api-key": K}, max_size=None, open_timeout=20) as ws:
            await ws.send(json.dumps({"setup": {"model": "models/gemini-3.8-live", "generationConfig": {"responseModalities": ["AUDIO"]},
                                                "outputAudioTranscription": {}, "systemInstruction": {"parts": [{"text": "Отвечай по-русски, коротко."}]}}}))
            await asyncio.wait_for(ws.recv(), 20)
            t0 = time.time()
            await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": "Расскажи в двух предложениях, что ты умеешь."}]}], "turnComplete": True}}))
            text, audio, first = [], 0, None
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 40))
                sc = m.get("serverContent", {})
                for p in sc.get("modelTurn", {}).get("parts", []):
                    if p.get("inlineData"):
                        audio += len(base64.b64decode(p["inlineData"]["data"])); first = first or time.time() - t0
                if sc.get("outputTranscription", {}).get("text"): text.append(sc["outputTranscription"]["text"])
                if sc.get("turnComplete"): break
            said = "".join(text).strip(); cyr = sum(c.isalpha() and "а" <= c.lower() <= "я" for c in said) / max(1, sum(c.isalpha() for c in said))
            out += [f"- Первый звук через: {first:.2f} с" if first else "- Звука нет",
                    f"- Аудио: {audio/48000:.1f} с", f"- Доля кириллицы в ответе: {cyr:.0%}", f"- Ответ: {said}"]
    except Exception as e:
        out.append(f"- Ошибка: {type(e).__name__}: {str(e)[:200]}")
    return out

def main(path):
    with httpx.Client(timeout=180) as cl:
        lines = ["# Проверка русского языка", "", f"Время: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", "", *tts_block(cl)]
    lines += asyncio.run(live_block())
    open(path, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "russian.md")
