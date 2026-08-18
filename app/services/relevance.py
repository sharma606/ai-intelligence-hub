from datetime import UTC, datetime, timedelta
import re


AI_KEYWORDS = {
    # Models and research
    "ai",
    "agent",
    "benchmark",
    "deep learning",
    "evaluation",
    "fine tuning",
    "foundation model",
    "generative",
    "llm",
    "machine learning",
    "multimodal",
    "model",
    "neural",
    "open source",
    "open weight",
    "reinforcement learning",
    "robotics",
    "synthetic data",
    # Agents, products, and applications
    "copilot",
    "computer vision",
    "enterprise ai",
    "knowledge base",
    "retrieval",
    "tool use",
    "workflow",
    # Infrastructure
    "accelerator",
    "cloud",
    "cuda",
    "data center",
    "datacenter",
    "deployment",
    "edge computing",
    "gpu",
    "inference",
    "latency",
    "mlops",
    "quantization",
    "serving",
    "throughput",
    "tpu",
    # Industry and market signals
    "acquisition",
    "capex",
    "earnings",
    "energy",
    "funding",
    "investment",
    "ipo",
    "partnership",
    "revenue",
    "semiconductor",
    "supply chain",
}


def _contains_keyword(text: str, keyword: str) -> bool:
    pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
    return re.search(pattern, text) is not None


def is_relevant(
    title: str,
    published_at: datetime | None,
    *,
    now: datetime | None = None,
    max_age_days: int = 30,
) -> bool:
    """Apply the project's lightweight title and recency filter."""
    title_text = title.casefold()
    has_ai_keyword = any(_contains_keyword(title_text, keyword) for keyword in AI_KEYWORDS)
    if not has_ai_keyword:
        return False

    if published_at is None:
        return True

    current_time = now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    return published_at >= current_time - timedelta(days=max_age_days)
