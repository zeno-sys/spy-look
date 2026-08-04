from __future__ import annotations

from fastapi import APIRouter

from tools.algorithm_practice.routes.execution import router as execution_router
from tools.algorithm_practice.routes.problems import router as problems_router
from tools.algorithm_practice.routes.tags import router as tags_router

router = APIRouter()
router.include_router(problems_router)
router.include_router(tags_router)
router.include_router(execution_router)
