from __future__ import annotations

from fastapi import APIRouter

from tools.web_clips.routes.clips import router as clips_router

router = APIRouter()
router.include_router(clips_router)
