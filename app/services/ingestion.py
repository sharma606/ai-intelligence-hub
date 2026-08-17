from datetime import UTC, datetime
import logging

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Source


logger = logging.getLogger(__name__)


def fetch_article_page(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=20.0)
    response.raise_for_status()
    return response.text


def parse_published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def entry_content(entry: dict) -> str | None:
    content = entry.get("content")
    if content:
        return content[0].get("value")
    return entry.get("summary")


def fetch_source(session: Session, source: Source) -> dict[str, int]:
    if source.type != "atom":
        raise ValueError(f"Unsupported source type: {source.type}")

    response = httpx.get(source.base_url, follow_redirects=True, timeout=20.0)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError("The source response could not be parsed as an Atom/RSS feed")

    created = updated = 0
    for entry in feed.entries:
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            continue

        values = {
            "title": title,
            "author": entry.get("author"),
            "published_at": parse_published(entry),
            "content": entry_content(entry),
            "document_type": "article",
        }
        document = session.scalar(select(Document).where(Document.url == url))
        if document is None:
            session.add(Document(source_id=source.id, url=url, **values))
            created += 1
        else:
            document.source_id = source.id
            for field, value in values.items():
                setattr(document, field, value)
            updated += 1

    session.commit()
    logger.info(
        "Ingested source_id=%s fetched=%s created=%s updated=%s",
        source.id,
        len(feed.entries),
        created,
        updated,
    )
    return {"fetched": len(feed.entries), "created": created, "updated": updated}
