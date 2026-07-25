from __future__ import annotations

from fastapi import APIRouter

from tools.image_tools.routes.admin import router as admin_router

router = APIRouter()
router.include_router(admin_router)
