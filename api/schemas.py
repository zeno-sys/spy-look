from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OpenAIErrorBody(BaseModel):
    message: str
    type: str = "gateway_error"
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIErrorBody


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int | None = None
    owned_by: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[dict[str, Any]]
