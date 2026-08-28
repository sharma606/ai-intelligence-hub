from app.services.article_text import extract_article_text


def test_extract_prefers_article_and_skips_scripts():
    # Nav text sits in <body> but outside <article>, so it should be dropped
    # once we have an article. Script contents should never be kept.
    html = "<body>Navigation<script>ignore()</script><article>Hello <b>world</b></article></body>"
    assert extract_article_text(html) == "Hello world"


def test_extract_prefers_blog_content_over_sidebar_cards():
    # This is the Hugging Face layout we hit in prod: a sidebar model card
    # uses <article>, and the real post is a div.blog-content.
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


def test_extract_keeps_text_after_void_tags():
    # <img> has no </img>. If we leave it on the stack, "world" can get lost
    # or attributed to the wrong region.
    html = '<body><article>Hello <img src="x.jpg"> world</article></body>'
    assert extract_article_text(html) == "Hello world"


def test_extract_falls_back_to_body_when_there_is_no_article():
    # Pages without <article> or blog-content should still return something.
    html = "<body><p>Just a page</p></body>"
    assert extract_article_text(html) == "Just a page"
