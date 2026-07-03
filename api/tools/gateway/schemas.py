from __future__ import annotations

from pydantic import BaseModel, model_validator


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


class LogReplayRequest(BaseModel):
    upstream_id: int
    model: str

    @model_validator(mode="after")
    def validate_non_empty(self) -> LogReplayRequest:
        if self.upstream_id < 1:
            raise ValueError("upstream_id is required")
        if not (self.model or "").strip():
            raise ValueError("model is required")
        return self
