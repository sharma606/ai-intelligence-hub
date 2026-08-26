from datetime import UTC, datetime
from time import struct_time

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.main import analyze_document, fetch_document_content
from app.models import Document, Source
from app.services import ingestion
from app.services.ingestion import extract_article_text, fetch_source, parse_published
from app.services.cache import AnalysisCache, analysis_cache_key
from app.services.relevance import is_relevant
from app.schemas import AnalysisResult


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, name: str, value: str, ex: int | None = None) -> None:
        self.data[name] = value
        self.ttls[name] = ex


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


def test_extract_article_text_prefers_blog_content_over_card_articles():
    html = """
    <body>
      <nav>Home</nav>
      <article class="overview-card-wrapper">CohereLabs/cohere-transcribe-03-2026 Automatic Speech Recognition</article>
      <div class="blog-content prose">The actual post about ASR benchmarks.</div>
    </body>
    """
    text = extract_article_text(html)
    assert "actual post about ASR benchmarks" in text
    assert "CohereLabs" not in text
    assert "Home" not in text


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


def test_analysis_is_saved_on_document(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        source = Source(id=1, name="Test feed", type="atom", base_url="https://example.com/feed.xml")
        document = Document(
            source_id=1,
            title="AI article",
            url="https://example.com/article",
            article_text="Article text",
            document_type="article",
        )
        session.add_all([source, document])
        session.commit()
        monkeypatch.setattr("app.main.get_analysis_cache", lambda: AnalysisCache(None))
        monkeypatch.setattr(
            "app.main.analyze_text",
            lambda text: AnalysisResult(
                summary="Short summary",
                why_it_matters="Useful context",
                topics=["inference"],
                importance=4,
            ),
        )

        result = analyze_document(document.id, session)

        assert result.summary == "Short summary"
        assert result.topics == ["inference"]
        assert result.importance == 4
        assert result.analyzed_at is not None


def _analysis_document(session: Session) -> Document:
    source = Source(id=1, name="Test feed", type="atom", base_url="https://example.com/feed.xml")
    document = Document(
        source_id=1,
        title="AI article",
        url="https://example.com/article",
        article_text="Article text",
        document_type="article",
    )
    session.add_all([source, document])
    session.commit()
    return document


def test_analysis_cache_miss_calls_llm_and_stores_result(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fake_redis = FakeRedis()
    calls: list[str] = []

    monkeypatch.setattr("app.main.get_analysis_cache", lambda: AnalysisCache(fake_redis))
    monkeypatch.setattr(
        "app.main.analyze_text",
        lambda text: calls.append(text) or AnalysisResult(
            summary="Short summary",
            why_it_matters="Useful context",
            topics=["inference"],
            importance=4,
        ),
    )

    with Session(engine) as session:
        document = _analysis_document(session)
        result = analyze_document(document.id, session)

        assert len(calls) == 1
        assert result.summary == "Short summary"
        cache_key = analysis_cache_key(document.id, "Article text")
        cached = fake_redis.get(cache_key)
        assert cached is not None
        assert "Short summary" in cached
        assert fake_redis.ttls[cache_key] == 86400


def test_analysis_cache_hit_skips_llm(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fake_redis = FakeRedis()
    calls: list[str] = []
    cached_result = AnalysisResult(
        summary="Cached summary",
        why_it_matters="Cached context",
        topics=["agents"],
        importance=5,
    )

    monkeypatch.setattr("app.main.get_analysis_cache", lambda: AnalysisCache(fake_redis))
    monkeypatch.setattr(
        "app.main.analyze_text",
        lambda text: calls.append(text) or cached_result,
    )

    with Session(engine) as session:
        document = _analysis_document(session)
        analyze_document(document.id, session)
        result = analyze_document(document.id, session)

        assert len(calls) == 1
        assert result.summary == "Cached summary"
        assert result.topics == ["agents"]
        assert result.importance == 5


def test_analysis_cache_misses_when_article_text_changes(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fake_redis = FakeRedis()
    calls: list[str] = []

    monkeypatch.setattr("app.main.get_analysis_cache", lambda: AnalysisCache(fake_redis))
    monkeypatch.setattr(
        "app.main.analyze_text",
        lambda text: calls.append(text) or AnalysisResult(
            summary=f"Summary for {text}",
            why_it_matters="Useful context",
            topics=["inference"],
            importance=3,
        ),
    )

    with Session(engine) as session:
        document = _analysis_document(session)
        analyze_document(document.id, session)
        document.article_text = "Updated article text"
        session.commit()
        result = analyze_document(document.id, session)

        assert calls == ["Article text", "Updated article text"]
        assert result.summary == "Summary for Updated article text"
