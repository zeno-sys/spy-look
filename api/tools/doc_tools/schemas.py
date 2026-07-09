from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


_DEFAULT_FONT_SIZES = (18.0, 16.0, 14.0, 13.0, 12.0, 11.0)
_DEFAULT_SPACE_BEFORE = (24.0, 18.0, 14.0, 12.0, 10.0, 8.0)
_DEFAULT_SPACE_AFTER = (18.0, 14.0, 12.0, 10.0, 8.0, 6.0)

NumberingStyleLiteral = Literal[
    "arabic",
    "roman",
    "roman_lower",
    "alpha",
    "alpha_lower",
    "chinese",
]


class HeadingStyleConfigSchema(BaseModel):
    """对应 services.md_to_docx.HeadingStyleConfig，供页面配置。"""

    numbering_enabled: bool = True
    use_word_numbering: bool = True
    max_numbering_level: int = Field(default=6, ge=1, le=6)
    number_separator: str = "."
    number_suffix: str = " "
    trailing_dot_on_top_level: bool = True
    font_name: str = "黑体"
    font_sizes_pt: list[float] = Field(default_factory=lambda: list(_DEFAULT_FONT_SIZES))
    space_before_pt: list[float] = Field(default_factory=lambda: list(_DEFAULT_SPACE_BEFORE))
    space_after_pt: list[float] = Field(default_factory=lambda: list(_DEFAULT_SPACE_AFTER))

    @field_validator("font_sizes_pt", "space_before_pt", "space_after_pt")
    @classmethod
    def _six_levels(cls, value: list[float]) -> list[float]:
        if len(value) != 6:
            raise ValueError("需提供 h1–h6 共 6 个数值")
        return value

    @field_validator("font_name")
    @classmethod
    def _font_name_not_empty(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("标题字体不能为空")
        return name


class MdToDocxRequest(BaseModel):
    markdown_content: str = Field(min_length=1, description="Markdown 正文")
    title: str = Field(default="Document", description="文档标题（同时用于输出文件名）")
    base_path: str | None = Field(
        default=None,
        description="解析相对路径图片时的基准目录（可选）",
    )
    heading_config: HeadingStyleConfigSchema | None = Field(
        default=None,
        description="标题编号与样式配置；省略则使用默认",
    )


class HeadingNumberingConfigSchema(BaseModel):
    """对应 services.md_heading_numbering.HeadingNumberingConfig。"""

    start_level: int = Field(default=1, ge=1, le=6)
    end_level: int = Field(default=6, ge=1, le=6)
    level_separator: str = "."
    number_suffix: str = "."
    heading_template: str = "{number} {title}"
    default_style: NumberingStyleLiteral = "arabic"
    level_styles: dict[int, NumberingStyleLiteral] = Field(default_factory=dict)
    strip_existing_number: bool = True

    @model_validator(mode="after")
    def _end_ge_start(self) -> HeadingNumberingConfigSchema:
        if self.end_level < self.start_level:
            raise ValueError("end_level 不能小于 start_level")
        return self

    @field_validator("level_styles", mode="before")
    @classmethod
    def _coerce_level_keys(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        out: dict[int, object] = {}
        for key, style in value.items():
            try:
                level = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"level_styles 键无效: {key}") from exc
            if 1 <= level <= 6:
                out[level] = style
        return out

    @field_validator("heading_template")
    @classmethod
    def _template_has_placeholders(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("heading_template 不能为空")
        if "{number}" not in text or "{title}" not in text:
            raise ValueError("heading_template 需包含 {number} 与 {title}")
        return text


class MdHeadingNumberingRequest(BaseModel):
    markdown_content: str = Field(min_length=1, description="Markdown 正文")
    config: HeadingNumberingConfigSchema | None = Field(
        default=None,
        description="标题编号配置；省略则使用默认",
    )
