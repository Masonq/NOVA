# NOVA

ИИ-агент: голос, изображения, видео, музыка, озвучка. Telegram WebApp + сайт + PWA.

- `backend/` — FastAPI, PostgreSQL, Redis-воркер (arq)
- `frontend/` — React/Vite, собранный `dist/` лежит в репозитории
- `deploy/install.sh` — установка и обновление на сервере, отчёт в ветку `reports`
- `tools/russian_check.py` — проверка русского у голосов Gemini (OpenRouter)

Обновление на сервере:

    git -C /opt/nova fetch -q origin main && git -C /opt/nova reset -q --hard origin/main && bash /opt/nova/deploy/install.sh
