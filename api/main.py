from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import UI_DIR
from db.engine import init_db
from db.upstreams import get_default_upstream_row
from errors import openai_error_response
from tools.gateway.router import router as gateway_tool_router
from tools.gateway.services.upstream_client import UpstreamClient, upstream_runtime_from_row


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from db.engine import async_session_factory, async_engine
    async with async_session_factory(async_engine) as session:
        row = await get_default_upstream_row(session)
        cfg = upstream_runtime_from_row(row) if row else None

    app.state.upstream_client = UpstreamClient(cfg) if cfg else None
    app.state._log_tasks: set[asyncio.Task] = set()
    try:
        yield
    finally:
        client = getattr(app.state, "upstream_client", None)
        if client is not None:
            await client.close()
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
    import logging
    import os

    import uvicorn

    host = (os.environ.get("SPY_LOOK_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("SPY_LOOK_PORT") or "8000")
    reload = (os.environ.get("SPY_LOOK_RELOAD") or "").strip().lower() in ("1", "true", "yes", "on")

    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("spy_look")
    logger.info(f"Spy-Look is running on http://{display_host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=reload)
