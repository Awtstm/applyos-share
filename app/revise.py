"""Revise step: user instruction → reworked plan + letter slots.

The review chat ("Überarbeitung anweisen") and `applyos revise` both call
this. The revision runs under the identical fact bounds as the original
pipeline — the prompt states them, the station fallback normalizes the
plan, and the caller pushes the result through app/validate.py like any
other LLM output. Instructions demanding unbacked content are implemented
within the evidence or flagged in Revision.notes.
"""

from app.llm import call_structured, load_prompt
from app.profile import Profile
from app.schemas import JobAnalysis, LetterSlots, Revision, TailoringPlan
from app.tailor import ensure_station_coverage, pool_system_block


def revise_application(
    profile: Profile,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    instruction: str,
    posting_text: str,
) -> Revision:
    system = [pool_system_block(profile), load_prompt("revise")]
    user = (
        "## Job-Analyse\n\n"
        + analysis.model_dump_json(indent=2)
        + "\n\n## Aktueller Plan\n\n"
        + plan.model_dump_json(indent=2)
        + "\n\n## Aktuelle Anschreiben-Slots\n\n"
        + slots.model_dump_json(indent=2)
        + "\n\n## Posting-Text\n\n"
        + posting_text
        + "\n\n## Überarbeitungs-Anweisung\n\n"
        + instruction
    )
    revision = call_structured("revise", system, user, Revision)
    return revision.model_copy(
        update={"plan": ensure_station_coverage(profile, revision.plan)}
    )
