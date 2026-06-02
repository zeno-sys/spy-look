from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


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


class ModelCapabilityProbeRequest(BaseModel):
    mode: str
    upstream_id: int | None = None
    uri: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout: float = 120.0
    max_tokens: int = 256

    @model_validator(mode="after")
    def validate_mode_fields(self) -> ModelCapabilityProbeRequest:
        mode = (self.mode or "").strip().lower()
        if mode not in ("upstream", "custom"):
            raise ValueError("mode must be upstream or custom")
        object.__setattr__(self, "mode", mode)
        if mode == "upstream":
            if self.upstream_id is None:
                raise ValueError("upstream_id is required for upstream mode")
            if not (self.model or "").strip():
                raise ValueError("model is required")
        else:
            if not (self.uri or "").strip():
                raise ValueError("uri is required for custom mode")
            if not (self.api_key or "").strip():
                raise ValueError("api_key is required for custom mode")
            if not (self.model or "").strip():
                raise ValueError("model is required")
        return self


class ModelCapabilityProbeModelsCustomRequest(BaseModel):
    uri: str
    api_key: str

    @model_validator(mode="after")
    def validate_non_empty(self) -> ModelCapabilityProbeModelsCustomRequest:
        if not (self.uri or "").strip():
            raise ValueError("uri is required")
        if not (self.api_key or "").strip():
            raise ValueError("api_key is required")
        return self
