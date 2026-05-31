import logging

from api.app import app

logger = logging.getLogger("spy_look")


if __name__ == "__main__":
    import os

    import uvicorn

    # 默认绑定 127.0.0.1；局域网暴露可设 SPY_LOOK_HOST=0.0.0.0
    host = (os.environ.get("SPY_LOOK_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("SPY_LOOK_PORT") or "8000")
    reload = (os.environ.get("SPY_LOOK_RELOAD") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info(f"Spy-Look is running on http://{display_host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=reload)
