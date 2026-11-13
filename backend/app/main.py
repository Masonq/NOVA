import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from .config import get_settings
from .db import engine, init_db
from .routes import auth, chat, jobs, me, tg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = FastAPI(title="NOVA", docs_url=None, redoc_url=None, openapi_url=None)
for r in (auth.router, me.router, chat.router, jobs.router, tg.router):
    app.include_router(r)


@app.on_event("startup")
async def _startup():
    await init_db()


@app.get("/api/health")
async def health():
    async with engine.connect() as c:
        await c.execute(text("select 1"))
    return {"ok": True}


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if p.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # hashed names: new deploy = new URL
    elif p.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.get("/{path:path}")
async def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Не найдено"}, status_code=404)
    root = os.path.realpath(get_settings().static_dir)
    f = os.path.realpath(os.path.join(root, path))
    if path and f.startswith(root + os.sep) and os.path.isfile(f):
        nocache = path in ("sw.js", "manifest.webmanifest")
        return FileResponse(f, headers={"Cache-Control": "no-cache" if nocache else "public, max-age=86400"})
    idx = os.path.join(root, "index.html")
    if not os.path.exists(idx):
        return JSONResponse({"detail": "Интерфейс не собран"}, status_code=503)
    return FileResponse(idx, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
