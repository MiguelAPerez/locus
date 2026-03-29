from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import json
import time
import os

from . import db, spaces
from .routes.auth import router as auth_router
from .routes.spaces import router as spaces_router
from .routes.collections import router as collections_router
from .routes.settings import router as settings_router, record_request

app = FastAPI(title="Locus", description="Semantic dataspace manager", version="1.0.0")
app.include_router(auth_router)
app.include_router(spaces_router)
app.include_router(collections_router)
app.include_router(settings_router)


@app.on_event("startup")
def startup():
    db.init_db()
    spaces.migrate_flat_spaces()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)

    if request.url.path == "/logs":
        return response

    detail = None
    if response.status_code >= 400:
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            detail = json.loads(body).get("detail")
        except Exception:
            detail = body.decode("utf-8", errors="replace")[:300]
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    record_request(request.method, str(request.url.path), response.status_code, ms, detail)
    return response


_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/static", StaticFiles(directory=_static), name="static")

    @app.get("/")
    def ui():
        return FileResponse(os.path.join(_static, "index.html"))
