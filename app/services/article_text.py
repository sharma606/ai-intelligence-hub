import re
from html.parser import HTMLParser
from typing import NamedTuple


SKIP_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "aside"})
VOID_TAGS = frozenset({"img", "br", "hr", "meta", "input", "link", "source", "area", "col", "embed", "wbr"})
SKIP_CLASSES = frozenset({"overview-card-wrapper"})
BLOG_CLASS = "blog-content"


class _OpenTag(NamedTuple):
    skip: bool
    region: str


class _ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._open: list[_OpenTag] = []
        self.blog_parts: list[str] = []
        self.article_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open.append(self._enter(tag, attrs))
        if tag in VOID_TAGS:
            self._close()

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID_TAGS:
            self._close()

    def handle_data(self, data: str) -> None:
        if not data.strip() or not self._open:
            return
        current = self._open[-1]
        if current.skip:
            return
        if current.region == "blog":
            self.blog_parts.append(data)
        elif current.region == "article":
            self.article_parts.append(data)
        elif current.region == "body":
            self.body_parts.append(data)

    def _enter(self, tag: str, attrs: list[tuple[str, str | None]]) -> _OpenTag:
        parent = self._open[-1] if self._open else _OpenTag(skip=False, region="")
        classes = (dict(attrs).get("class") or "").split()

        if parent.skip or tag in SKIP_TAGS or SKIP_CLASSES.intersection(classes):
            return _OpenTag(skip=True, region=parent.region)
        if BLOG_CLASS in classes:
            return _OpenTag(skip=False, region="blog")
        if tag == "article" and parent.region != "blog":
            return _OpenTag(skip=False, region="article")
        if tag == "body" and not parent.region:
            return _OpenTag(skip=False, region="body")
        return _OpenTag(skip=False, region=parent.region)

    def _close(self) -> None:
        if self._open:
            self._open.pop()


def extract_article_text(html: str) -> str:
    parser = _ArticleTextParser()
    parser.feed(html)
    parser.close()
    parts = parser.blog_parts or parser.article_parts or parser.body_parts
    return re.sub(r"\s+", " ", " ".join(parts)).strip()
