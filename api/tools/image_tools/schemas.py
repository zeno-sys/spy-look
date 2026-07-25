from __future__ import annotations

from pydantic import BaseModel, Field


class OcrItem(BaseModel):
    id: int
    text: str
    score: float
    points: list[list[float]]
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    color: str


class OcrResponse(BaseModel):
    width: int
    height: int
    image_data_uri: str
    items: list[OcrItem] = Field(default_factory=list)
    full_text: str = ""
    count: int = 0


class FormulaResponse(BaseModel):
    width: int
    height: int
    image_data_uri: str
    latex: str = ""


class LayoutItem(BaseModel):
    id: int
    label: str
    label_zh: str
    category_id: int
    model_order: int = -1
    reading_order: int | None = None
    score: float
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    cx: float
    cy: float
    color: str


class LayoutLegendItem(BaseModel):
    label: str
    label_zh: str
    color: str


class LayoutResponse(BaseModel):
    width: int
    height: int
    image_data_uri: str
    items: list[LayoutItem] = Field(default_factory=list)
    legend: list[LayoutLegendItem] = Field(default_factory=list)
    ordered_count: int = 0
    count: int = 0
