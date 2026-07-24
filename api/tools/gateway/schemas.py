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


class TokenSpeedTestRequest(BaseModel):
    mode: str
    upstream_id: int | None = None
    uri: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout: float = 120.0
    max_tokens: int = 256

    @model_validator(mode="after")
    def validate_mode_fields(self) -> TokenSpeedTestRequest:
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


class EmbeddingCapabilityProbeRequest(BaseModel):
    mode: str
    upstream_id: int | None = None
    uri: str | None = None
    api_key: str | None = None
    model: str | None = None
    text_a: str = ""
    text_b: str = ""
    timeout: float = 120.0

    @model_validator(mode="after")
    def validate_mode_fields(self) -> EmbeddingCapabilityProbeRequest:
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
        if not (self.text_a or "").strip():
            raise ValueError("text_a is required")
        if not (self.text_b or "").strip():
            raise ValueError("text_b is required")
        return self


class RerankCapabilityProbeRequest(BaseModel):
    mode: str
    upstream_id: int | None = None
    uri: str | None = None
    api_key: str | None = None
    model: str | None = None
    query: str = ""
    documents: list[str] = []
    timeout: float = 120.0

    @model_validator(mode="after")
    def validate_mode_fields(self) -> RerankCapabilityProbeRequest:
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
        if not (self.query or "").strip():
            raise ValueError("query is required")
        cleaned = [str(d).strip() for d in (self.documents or []) if str(d).strip()]
        if len(cleaned) < 2:
            raise ValueError("at least 2 non-empty documents are required")
        object.__setattr__(self, "documents", cleaned)
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
