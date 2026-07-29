from __future__ import annotations

from pydantic import BaseModel


class CreateItemRequest(BaseModel):
    url: str
    title: str = ""
    summary: str = ""
    bookmark_id: int | None = None


class UpdateItemRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    bookmark_id: int | None | str = None  # str for null sentinel
