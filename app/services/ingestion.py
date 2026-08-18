from datetime import UTC, datetime
from html.parser import HTMLParser
import logging
import re

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Source
from app.services.relevance import is_relevant


logger = logging.getLogger(__name__)


class _ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.article_depth = 0
        self.body_depth = 0
        self.skip_depth = 0
        self.article_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "article":
            self.article_depth += 1
        elif tag == "body":
            self.body_depth += 1
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "article" and self.article_depth:
            self.article_depth -= 1
        elif tag == "body" and self.body_depth:
            self.body_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth or not data.strip():
            return
        if self.article_depth:
            self.article_parts.append(data)
        elif self.body_depth:
            self.body_parts.append(data)


def extract_article_text(html: str) -> str:
    parser = _ArticleTextParser()
    parser.feed(html)
    parts = parser.article_parts or parser.body_parts
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def fetch_article_page(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=20.0)
    response.raise_for_status()
    return response.text


def parse_published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


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

        published_at = parse_published(entry)
        if not is_relevant(title, published_at):
            continue

        values = {
            "title": title,
            "author": entry.get("author"),
            "published_at": published_at,
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
