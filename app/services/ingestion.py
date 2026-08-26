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
    SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "aside"}
    VOID_TAGS = {"img", "br", "hr", "meta", "input", "link", "source", "area", "col", "embed", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_stack: list[bool] = []
        self.region_stack: list[str] = []
        self.blog_parts: list[str] = []
        self.article_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        parent_skip = bool(self.skip_stack and self.skip_stack[-1])
        skip = parent_skip or tag in self.SKIP_TAGS or "overview-card-wrapper" in classes
        self.skip_stack.append(skip)

        region = self.region_stack[-1] if self.region_stack else ""
        if not skip:
            if "blog-content" in classes:
                region = "blog"
            elif tag == "article" and region != "blog":
                region = "article"
            elif tag == "body" and not region:
                region = "body"
        self.region_stack.append(region)

        if tag in self.VOID_TAGS:
            self._pop_element()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_TAGS:
            return
        self._pop_element()

    def _pop_element(self) -> None:
        if self.skip_stack:
            self.skip_stack.pop()
        if self.region_stack:
            self.region_stack.pop()

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if self.skip_stack and self.skip_stack[-1]:
            return
        region = self.region_stack[-1] if self.region_stack else ""
        if region == "blog":
            self.blog_parts.append(data)
        elif region == "article":
            self.article_parts.append(data)
        elif region == "body":
            self.body_parts.append(data)


def extract_article_text(html: str) -> str:
    parser = _ArticleTextParser()
    parser.feed(html)
    parts = parser.blog_parts or parser.article_parts or parser.body_parts
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
