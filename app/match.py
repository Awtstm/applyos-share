"""Match step: honest posting-vs-profile fit assessment (ProfileMatch).

Separate small LLM call after analyze — analyze itself never sees the
profile, the match needs both sides. Calibration rules (score anchors,
concrete-evidence strengths, unsoftened gaps) live in app/prompts/match.md.
"""

from app.llm import call_structured, load_prompt
from app.profile import Profile
from app.schemas import JobAnalysis, ProfileMatch
from app.tailor import pool_system_block


def evaluate_match(
    profile: Profile, analysis: JobAnalysis, posting_text: str
) -> ProfileMatch:
    system = [pool_system_block(profile), load_prompt("match")]
    user = (
        "## Job-Analyse\n\n"
        + analysis.model_dump_json(indent=2)
        + "\n\n## Posting-Text\n\n"
        + posting_text
    )
    match = call_structured("match", system, user, ProfileMatch)
    return match.model_copy(update={"score": max(0, min(100, match.score))})
