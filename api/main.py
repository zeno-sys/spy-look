from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import UI_DIR
from db.engine import init_db
from errors import openai_error_response
from tools.gateway.router import router as gateway_tool_router
from tools.video_tools.router import router as video_tools_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from tools.video_tools.services.config_loader import ensure_config

    ensure_config()

    app.state._log_tasks: set[asyncio.Task] = set()
    try:
        yield
    finally:
        tasks = getattr(app.state, "_log_tasks", set())
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                pass


app = FastAPI(title="Spy-Look", description="个人工具合集", version="0.2.0", lifespan=lifespan)

if UI_DIR.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")

app.include_router(gateway_tool_router)
app.include_router(video_tools_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str = ""):
    if UI_DIR.exists() and (UI_DIR / "index.html").exists():
        from fastapi.responses import FileResponse
        if full_path in ("", "index.html"):
            return FileResponse(UI_DIR / "index.html")
        candidate = UI_DIR / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(UI_DIR / "index.html")
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return openai_error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
        error_type="invalid_request_error",
    )


if __name__ == "__main__":
    import uvicorn
    host = "0.0.0.0"
    port = 8000
    reload = True
    uvicorn.run("main:app", host=host, port=port, reload=reload)


