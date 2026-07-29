from __future__ import annotations

from fastapi import APIRouter

from tools.bookmarks.routes.bookmarks import router as bookmarks_router
from tools.bookmarks.routes.groups import router as groups_router
from tools.bookmarks.routes.tags import router as tags_router

router = APIRouter()
router.include_router(groups_router)
router.include_router(tags_router)
router.include_router(bookmarks_router)
