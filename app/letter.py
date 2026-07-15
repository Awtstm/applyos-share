"""LLM call 3: profile + analysis + plan → LetterSlots (variable letter body).

Only the four body slots are generated; greeting, closing formula and the
location note are fixed fragments from profile.yaml (letter_fixed). Register
rules (DE: Sie-Form, formal / EN) live in app/prompts/letter.md. Slots are
validated against profile + posting before rendering (no new numbers or
employers).
"""

from app.llm import call_structured, load_prompt
from app.profile import Profile
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan
from app.tailor import pool_system_block


def make_letter_slots(
    profile: Profile,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    posting_text: str,
) -> LetterSlots:
    system = [pool_system_block(profile), load_prompt("letter")]
    user = (
        "## Job-Analyse\n\n"
        + analysis.model_dump_json(indent=2)
        + "\n\n## Tailoring-Plan (ausgewählte Belege)\n\n"
        + plan.model_dump_json(indent=2)
        + "\n\n## Posting-Text\n\n"
        + posting_text
    )
    return call_structured("letter", system, user, LetterSlots)
