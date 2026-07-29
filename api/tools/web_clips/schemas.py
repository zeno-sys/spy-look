from __future__ import annotations

from pydantic import BaseModel


class ClipUrlRequest(BaseModel):
    url: str
    bookmark_id: int | None = None
