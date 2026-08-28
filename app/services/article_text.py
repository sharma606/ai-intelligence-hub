import re
from html.parser import HTMLParser
from typing import NamedTuple


# Chrome we never want in the saved text.
SKIP_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "aside"})

# HTML void tags have no closing tag. HTMLParser still calls handle_starttag
# for them, but it will never call handle_endtag. If we push and never pop,
# later text gets the wrong skip/region.
VOID_TAGS = frozenset({"img", "br", "hr", "meta", "input", "link", "source", "area", "col", "embed", "wbr"})

# Hugging Face wraps sidebar model cards in <article class="overview-card-wrapper">.
# The first <article> on the page is often a card, not the blog post.
SKIP_CLASSES = frozenset({"overview-card-wrapper"})

# The actual post body on HF blog pages.
BLOG_CLASS = "blog-content"


class _OpenTag(NamedTuple):
    # True if this tag (or an ancestor) should be ignored.
    skip: bool
    # Where we currently are: "blog", "article", "body", or "" if none yet.
    region: str


class _ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        # One entry per open tag. End tags have no class names, so we store
        # skip/region here and pop on close.
        self._open: list[_OpenTag] = []
        # Collected separately so we can prefer blog over article over body.
        self.blog_parts: list[str] = []
        self.article_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open.append(self._enter(tag, attrs))
        # Void tags are done immediately. There will be no matching end tag.
        if tag in VOID_TAGS:
            self._close()

    def handle_endtag(self, tag: str) -> None:
        # If a void tag somehow gets an end event, ignore it. We already closed
        # it in handle_starttag, so popping again would drop the parent.
        if tag not in VOID_TAGS:
            self._close()

    def handle_data(self, data: str) -> None:
        # Whitespace-only nodes are junk from the HTML formatting.
        if not data.strip() or not self._open:
            return
        current = self._open[-1]
        if current.skip:
            return
        # Same text can sit in nested regions. We bucket by the current region
        # and pick a winner later in extract_article_text.
        if current.region == "blog":
            self.blog_parts.append(data)
        elif current.region == "article":
            self.article_parts.append(data)
        elif current.region == "body":
            self.body_parts.append(data)

    def _enter(self, tag: str, attrs: list[tuple[str, str | None]]) -> _OpenTag:
        # Inherit skip/region from the parent. Root of the document has neither.
        parent = self._open[-1] if self._open else _OpenTag(skip=False, region="")
        classes = (dict(attrs).get("class") or "").split()

        # Skip if a parent is skipped, this tag is chrome, or it is an HF card.
        if parent.skip or tag in SKIP_TAGS or SKIP_CLASSES.intersection(classes):
            return _OpenTag(skip=True, region=parent.region)

        # blog-content wins. Nested <article> inside the post should stay "blog".
        if BLOG_CLASS in classes:
            return _OpenTag(skip=False, region="blog")
        # Generic <article> is the fallback for normal pages.
        if tag == "article" and parent.region != "blog":
            return _OpenTag(skip=False, region="article")
        # Body is last resort, and only if we have not entered a better region.
        if tag == "body" and not parent.region:
            return _OpenTag(skip=False, region="body")
        # Anything else (<p>, <div>, <b>, ...) keeps the parent's region.
        return _OpenTag(skip=False, region=parent.region)

    def _close(self) -> None:
        if self._open:
            self._open.pop()


def extract_article_text(html: str) -> str:
    parser = _ArticleTextParser()
    parser.feed(html)
    parser.close()
    # Prefer the real post, then a generic article, then the whole body.
    parts = parser.blog_parts or parser.article_parts or parser.body_parts
    # Collapse newlines and extra spaces from the HTML into single spaces.
    return re.sub(r"\s+", " ", " ".join(parts)).strip()
