"""LLM call 2: profile pool + JobAnalysis → TailoringPlan (ID selection).

The model only ever sees the pools it may select from and returns IDs plus
optional bounded rephrasings — never free-form CV content (ADR #2). The
plan is validated against the profile in app/validate.py before rendering.
"""

import json

from app.llm import call_structured, load_prompt
from app.profile import Profile
from app.schemas import BulletChoice, JobAnalysis, StationPlan, TailoringPlan

# What the plan step may select from. basics/letter_fixed stay out of the
# prompt — they contain nothing selectable.
_POOL_FIELDS = {"headline_pool", "stations", "extracurricular", "skills"}


def profile_pool_json(profile: Profile) -> str:
    pool = profile.model_dump(include=_POOL_FIELDS)
    return json.dumps(pool, ensure_ascii=False, indent=2)


def pool_system_block(profile: Profile) -> str:
    """Byte-identical across match/plan/letter/revise and placed FIRST in
    the system blocks, so the cached pool prefix is shared between steps.

    Includes the match-relevant basics (location, nationality, languages,
    on-site willingness) — first-order criteria for location/work-permit/
    language matching; contact data stays out (no use in any prompt)."""
    basics = profile.basics
    facts = {
        "wohnort": basics.location,
        "nationalitaet": basics.nationality,
        "sprachen": [
            {"de": lang.label_de, "en": lang.label_en} for lang in profile.languages
        ],
        "standort_bereitschaft": profile.letter_fixed.location_note_de,
    }
    return (
        "## Bewerber-Basics (Standort, Nationalität, Sprachen)\n\n"
        + json.dumps(facts, ensure_ascii=False, indent=2)
        + "\n\n## Profil-Pool (JSON)\n\n"
        + profile_pool_json(profile)
    )


def ensure_station_coverage(profile: Profile, plan: TailoringPlan) -> TailoringPlan:
    """Deterministic fallback for the gapless-CV rule (DACH convention):
    a station the model omitted or emptied gets its default bullet (first
    default-marked, else first in the pool) instead of a validation error."""
    planned = {sp.station_id: sp for sp in plan.stations}
    stations = []
    for station in profile.stations:
        entry = planned.get(station.id)
        if entry is None or not entry.bullets:
            fallback = next((b for b in station.bullets if b.default), station.bullets[0])
            entry = StationPlan(
                station_id=station.id,
                bullets=[BulletChoice(bullet_id=fallback.id, rephrased_text=None)],
            )
        stations.append(entry)
    return plan.model_copy(update={"stations": stations})


def make_plan(profile: Profile, analysis: JobAnalysis, posting_text: str) -> TailoringPlan:
    system = [pool_system_block(profile), load_prompt("plan")]
    user = (
        "## Job-Analyse\n\n"
        + analysis.model_dump_json(indent=2)
        + "\n\n## Posting-Text\n\n"
        + posting_text
    )
    plan = call_structured("plan", system, user, TailoringPlan)
    return ensure_station_coverage(profile, plan)
