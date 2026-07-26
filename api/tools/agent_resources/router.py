from __future__ import annotations

from fastapi import APIRouter

from tools.agent_resources.routes.skills import router as skills_router

router = APIRouter()
router.include_router(skills_router)
