from __future__ import annotations

from fastapi import APIRouter

from tools.auth.routes import router as auth_routes

router = APIRouter()
router.include_router(auth_routes)
