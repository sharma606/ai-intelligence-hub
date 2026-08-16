from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    content: str | None
    document_type: str
    created_at: datetime
    updated_at: datetime


class FetchResult(BaseModel):
    source_id: int
    fetched: int
    created: int
    updated: int
