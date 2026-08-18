from datetime import UTC, datetime
from time import struct_time

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.main import fetch_document_content
from app.models import Document, Source
from app.services import ingestion
from app.services.ingestion import extract_article_text, fetch_source, parse_published
from app.services.relevance import is_relevant


def test_relevance_requires_ai_keyword():
    assert is_relevant("AI model release", None)
    assert is_relevant("New GPU inference platform", None)
    assert is_relevant("AI company reports new revenue", None)
    assert not is_relevant("Company holiday schedule", None)


def test_relevance_does_not_match_ai_inside_another_word():
    assert not is_relevant("Sailing schedule", None)


def test_relevance_rejects_old_documents():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    old_date = datetime(2026, 7, 1, tzinfo=UTC)
    assert not is_relevant("New AI model", old_date, now=now)


def test_parse_published_returns_utc_datetime():
    entry = {"published_parsed": struct_time((2026, 8, 14, 0, 0, 0, 0, 0, 0))}
    result = parse_published(entry)
    assert result.year == 2026
    assert result.tzinfo == UTC


def test_fetch_article_page_returns_html(monkeypatch):
    class MockResponse:
        text = "<html><article>Hello</article></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: MockResponse())
    assert ingestion.fetch_article_page("https://example.com/article") == "<html><article>Hello</article></html>"


def test_extract_article_text_prefers_article_and_ignores_scripts():
    html = "<body>Navigation<script>ignore()</script><article>Hello <b>world</b></article></body>"
    assert extract_article_text(html) == "Hello world"


def test_repeated_ingestion_updates_by_url_without_duplicates(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    feed_versions = [
        b"""<rss><channel><item><title>AI first title</title><link>https://example.com/article</link><description>First feed text</description></item></channel></rss>""",
        b"""<rss><channel><item><title>AI updated title</title><link>https://example.com/article</link><description>Updated feed text</description></item></channel></rss>""",
    ]

    class MockResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    with Session(engine) as session:
        source = Source(name="Test feed", type="atom", base_url="https://example.com/feed.xml")
        session.add(source)
        session.commit()
        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: MockResponse(feed_versions.pop(0)))

        first = fetch_source(session, source)
        second = fetch_source(session, source)

        documents = session.scalars(select(Document)).all()
        assert first == {"fetched": 1, "created": 1, "updated": 0}
        assert second == {"fetched": 1, "created": 0, "updated": 1}
        assert len(documents) == 1
        assert documents[0].title == "AI updated title"


def test_article_html_is_stored_on_document(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        document = Document(
            source_id=1,
            title="Test article",
            url="https://example.com/article",
            document_type="article",
        )
        source = Source(id=1, name="Test feed", type="atom", base_url="https://example.com/feed.xml")
        session.add_all([source, document])
        session.commit()
        monkeypatch.setattr("app.main.fetch_article_page", lambda url: "<html><article>Page</article></html>")

        result = fetch_document_content(document.id, session)

        assert result.article_html == "<html><article>Page</article></html>"
        assert result.article_text == "Page"
