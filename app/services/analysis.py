import os

from openai import OpenAI

from app.schemas import AnalysisResult


class AnalysisError(Exception):
    pass


def analyze_text(article_text: str) -> AnalysisResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AnalysisError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "Analyze this AI industry article. Return a concise summary, explain why it matters, "
                        "choose a few useful topics, and rate importance from 1 to 5. Use only information "
                        "supported by the article."
                    ),
                },
                {"role": "user", "content": article_text},
            ],
            text_format=AnalysisResult,
        )
    except Exception as exc:
        raise AnalysisError(f"LLM analysis failed: {exc}") from exc

    if response.output_parsed is None:
        raise AnalysisError("LLM returned no structured analysis")
    return response.output_parsed
