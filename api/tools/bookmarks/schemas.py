from __future__ import annotations

from pydantic import BaseModel, Field


class CreateGroupRequest(BaseModel):
    name: str
    sort_order: int = 0


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None


class CreateTagRequest(BaseModel):
    name: str
    color: str = "#64748b"


class UpdateTagRequest(BaseModel):
    name: str | None = None
    color: str | None = None


class FetchMetadataRequest(BaseModel):
    url: str


class CreateBookmarkRequest(BaseModel):
    url: str
    title: str = ""
    favicon_url: str = ""
    group_id: int | None = None


class UpdateBookmarkRequest(BaseModel):
    title: str | None = None
    favicon_url: str | None = None
    group_id: int | None = None
    pinned: bool | None = None


class SetBookmarkTagsRequest(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)
