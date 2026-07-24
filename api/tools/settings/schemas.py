from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LlmSettings(BaseModel):
    """全局可用大模型连接配置。"""

    mode: Literal["upstream", "custom"] = "custom"
    upstream_id: int | None = None
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    # 对应 SDK 的 extra_body：写入后会合并进 chat completions 请求体
    extra_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extra_params", mode="before")
    @classmethod
    def _coerce_extra_params(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("extra_params must be a JSON object")
        return value

    @model_validator(mode="after")
    def _validate_mode(self) -> LlmSettings:
        # 允许完全未配置的空状态；仅在字段已填写时做一致性校验
        if self.mode == "upstream" and self.upstream_id is not None and int(self.upstream_id) < 1:
            raise ValueError("upstream_id 无效")
        return self


class LlmSettingsPatch(BaseModel):
    mode: Literal["upstream", "custom"] | None = None
    upstream_id: int | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    extra_params: dict[str, Any] | None = None

    @field_validator("extra_params", mode="before")
    @classmethod
    def _coerce_extra_params(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("extra_params must be a JSON object")
        return value


class AppSettings(BaseModel):
    llm: LlmSettings = Field(default_factory=LlmSettings)


class AppSettingsPatch(BaseModel):
    llm: LlmSettingsPatch | None = None


class LlmConnectivityTestRequest(BaseModel):
    """连通性测试：可传当前表单值（未保存也可测）。"""

    mode: Literal["upstream", "custom"] = "custom"
    upstream_id: int | None = None
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    extra_params: dict[str, Any] = Field(default_factory=dict)
    # 留空时使用已保存的密钥（custom 模式）
    use_saved_api_key: bool = False

    @field_validator("extra_params", mode="before")
    @classmethod
    def _coerce_extra_params(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("extra_params must be a JSON object")
        return value


class GenerateProbeTextsRequest(BaseModel):
    """基于全局大模型生成能力测试占位文本。"""

    kind: Literal["embedding", "rerank"]
    document_count: int = Field(default=3, ge=2, le=8)
