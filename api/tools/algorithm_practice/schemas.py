from __future__ import annotations

from pydantic import BaseModel, Field


# --- Problems ---

class CreateProblemRequest(BaseModel):
    title: str
    description: str = ""
    tag_ids: list[int] = Field(default_factory=list)


class UpdateProblemRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    solution_code: str | None = None
    thought: str | None = None


class SetProblemTagsRequest(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)


# --- Tags ---

class CreateTagRequest(BaseModel):
    name: str
    color: str = "#64748b"


class UpdateTagRequest(BaseModel):
    name: str | None = None
    color: str | None = None


# --- Execution ---

class ExecuteCodeRequest(BaseModel):
    code: str
    stdin: str = ""


class SyntaxCheckRequest(BaseModel):
    code: str = ""
