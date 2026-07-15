"""LLM call 1: posting text → JobAnalysis (extraction only, no invention)."""

from app.llm import call_structured, load_prompt
from app.schemas import MAX_KEYWORDS, MAX_TOP_REQUIREMENTS, JobAnalysis


def clamp_analysis(analysis: JobAnalysis) -> JobAnalysis:
    """Trim over-long lists to their bounds. The prompt orders both lists by
    priority, so cutting the tail keeps the most important entries — cheaper
    and more deterministic than failing validation over an extraction step."""
    return analysis.model_copy(
        update={
            "top_requirements": analysis.top_requirements[:MAX_TOP_REQUIREMENTS],
            "keywords": analysis.keywords[:MAX_KEYWORDS],
        }
    )


def analyze_posting(posting_text: str, lang: str | None = None) -> JobAnalysis:
    """Analyze a posting; lang ("de"/"en") overrides the detected language."""
    analysis = call_structured("analyze", [load_prompt("analyze")], posting_text, JobAnalysis)
    if lang in ("de", "en") and lang != analysis.language:
        analysis = analysis.model_copy(update={"language": lang})
    return clamp_analysis(analysis)
