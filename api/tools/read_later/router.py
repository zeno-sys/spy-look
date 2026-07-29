from __future__ import annotations

from fastapi import APIRouter

from tools.read_later.routes.items import router as items_router

router = APIRouter()
router.include_router(items_router)
