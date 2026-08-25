import os

from google import genai
from google.genai import types

from app.schemas import AnalysisResult


class AnalysisError(Exception):
    pass


def analyze_text(article_text: str) -> AnalysisResult:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AnalysisError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=article_text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Analyze this AI industry article. Return a concise summary, explain why it matters, "
                    "choose a few useful topics, and rate importance from 1 to 5. Use only information "
                    "supported by the article."
                ),
                response_mime_type="application/json",
                response_schema=AnalysisResult,
            ),
        )
    except Exception as exc:
        raise AnalysisError(f"LLM analysis failed: {exc}") from exc

    parsed = response.parsed
    if parsed is None:
        raise AnalysisError("LLM returned no structured analysis")
    if isinstance(parsed, AnalysisResult):
        return parsed
    return AnalysisResult.model_validate(parsed)
