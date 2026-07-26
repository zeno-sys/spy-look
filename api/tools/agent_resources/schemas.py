from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSkillRequest(BaseModel):
    name: str
    description: str
    changelog: str = "初始版本"


class UpdateSkillMdRequest(BaseModel):
    content: str
    changelog: str


class RestoreVersionRequest(BaseModel):
    changelog: str = ""


class GithubImportRequest(BaseModel):
    url: str
    changelog: str = "从 GitHub 导入"


class SetSkillTagsRequest(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)


class CreateTagRequest(BaseModel):
    name: str
    color: str = "#64748b"


class UpdateTagRequest(BaseModel):
    name: str | None = None
    color: str | None = None
