from __future__ import annotations

from fastapi import APIRouter

from tools.gateway.routes.admin import router as admin_router
from tools.gateway.routes.logs import router as logs_router
from tools.gateway.routes.v1 import router as v1_router

router = APIRouter()
router.include_router(v1_router)
router.include_router(logs_router)
router.include_router(admin_router)
