from datetime import UTC
from time import struct_time

import httpx

from app.services import ingestion
from app.services.ingestion import entry_content, parse_published


def test_entry_content_prefers_full_content():
    entry = {"content": [{"value": "full article"}], "summary": "summary"}
    assert entry_content(entry) == "full article"


def test_entry_content_falls_back_to_summary():
    assert entry_content({"summary": "feed summary"}) == "feed summary"


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
