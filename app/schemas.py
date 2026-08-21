from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    base_url: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    title: str
    url: str
    author: str | None
    published_at: datetime | None
    article_html: str | None
    article_text: str | None
    summary: str | None
    why_it_matters: str | None
    topics: list[str] | None
    importance: int | None
    analyzed_at: datetime | None
    document_type: str
    created_at: datetime
    updated_at: datetime


class FetchResult(BaseModel):
    source_id: int
    fetched: int
    created: int
    updated: int


class AnalysisResult(BaseModel):
    summary: str
    why_it_matters: str
    topics: list[str]
    importance: int = Field(ge=1, le=5)
