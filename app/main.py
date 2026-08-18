from contextlib import asynccontextmanager
import logging

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_session
from app.models import Document, Source
from app.schemas import DocumentRead, FetchResult, SourceRead
from app.seed import ensure_initial_source
from app.services.ingestion import extract_article_text, fetch_article_page, fetch_source


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_initial_source(session)
    yield


app = FastAPI(title="AI Intelligence Hub", lifespan=lifespan)
logger = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)):
    return session.scalars(select(Source).order_by(Source.id)).all()


@app.post("/sources/{source_id}/fetch", response_model=FetchResult)
def ingest_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        result = fetch_source(session, source)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Source fetch failed: {exc}") from exc
    return FetchResult(source_id=source.id, **result)


@app.get("/documents", response_model=list[DocumentRead])
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    statement = (
        select(Document)
        .order_by(Document.published_at.desc().nullslast(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return session.scalars(statement).all()


@app.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, session: Session = Depends(get_session)):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.post("/documents/{document_id}/fetch-content", response_model=DocumentRead)
def fetch_document_content(document_id: int, session: Session = Depends(get_session)):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        document.article_html = fetch_article_page(document.url)
        document.article_text = extract_article_text(document.article_html)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Article fetch failed: {exc}") from exc
    session.commit()
    session.refresh(document)
    return document
