from datetime import UTC, datetime, timedelta


AI_KEYWORDS = {
    "ai",
    "agent",
    "deep learning",
    "generative",
    "llm",
    "machine learning",
    "model",
    "neural",
    "robotics",
}


def is_relevant(
    title: str,
    published_at: datetime | None,
    *,
    now: datetime | None = None,
    max_age_days: int = 30,
) -> bool:
    """Apply the project's lightweight title and recency filter."""
    title_text = title.casefold()
    has_ai_keyword = any(keyword in title_text for keyword in AI_KEYWORDS)
    if not has_ai_keyword:
        return False

    if published_at is None:
        return True

    current_time = now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    return published_at >= current_time - timedelta(days=max_age_days)
