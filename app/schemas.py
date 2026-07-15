"""Pipeline schemas: the JSON contracts of the three LLM calls.

JobAnalysis (call 1), TailoringPlan (call 2), LetterSlots (call 3) — Pydantic
v2, flat, extra="forbid". These models are passed to the Anthropic structured
outputs API (client.messages.parse), which guarantees schema-valid responses.

Deliberately NOT encoded here: numeric bounds (item counts, text lengths) and
any coupling to the profile. Structured outputs does not enforce maxItems /
maxLength server-side, and a hard client-side parse failure is worse than a
reviewable error report — so all bounds live in app/validate.py, which checks
every plan against profile.yaml before anything is rendered (CLAUDE.md rules
1+2: the LLM only selects existing bullet IDs, it never invents facts). The
shared limits are defined as constants below so validator and prompts agree.

All fields the LLM must produce are required; "optional" information is
modeled as required-but-nullable (str | None), the shape structured outputs
handles best.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Shared bounds — enforced by app/validate.py, referenced in app/prompts/*.md.
MAX_TOP_REQUIREMENTS = 5
MAX_KEYWORDS = 15
# 1, not 2: deliberately concise stations (e.g. FQC) carry a single bullet
# in the user's one-page CV design
MIN_BULLETS_PER_STATION = 1
# hard one-page guarantee: matches the user's curated default selection
MAX_TOTAL_BULLETS = 10
MAX_BULLETS_PER_STATION = 4
REPHRASE_MAX_RATIO = 1.5  # rephrased_text length vs. original bullet text
REPHRASE_HEADROOM_CHARS = 50  # absolute grace so short bullets aren't over-constrained
MIN_LETTER_FITS = 2  # letter.typ asserts 2-3 fit paragraphs
# letter length is governed by a TOTAL body budget, not rigid per-slot caps.
# Calibrated against rendered PDFs (2026-07-10, worst case: 3 fits +
# location note + contact line): the page tips at ~2250 body chars — 2100
# leaves a safety margin. Per-slot caps remain only as outlier guards.
LETTER_BODY_MAX_CHARS = 2100
MAX_SLOT_CHARS = {
    "hook": 700,
    "fit": 700,
    "closing_variant": 700,
}


class _StrictModel(BaseModel):
    # extra="forbid" turns hallucinated fields into validation errors
    model_config = ConfigDict(extra="forbid")


class JobAnalysis(_StrictModel):
    """LLM call 1: what the posting is about, in extractable facts only."""

    company: str = Field(min_length=1)
    role_title: str = Field(min_length=1)
    language: Literal["de", "en"]
    contact_person: str | None  # only if the posting names one; drives greeting
    top_requirements: list[str]  # max MAX_TOP_REQUIREMENTS (validator)
    keywords: list[str]  # max MAX_KEYWORDS (validator)
    seniority: str
    notes: str | None


class BulletChoice(_StrictModel):
    """One selected profile bullet, optionally lightly rephrased."""

    bullet_id: str = Field(min_length=1)
    # None = use the profile text verbatim. If set: bounded rephrasing only —
    # validator enforces length ratio and that no new numbers appear.
    rephrased_text: str | None


class StationPlan(_StrictModel):
    station_id: str = Field(min_length=1)
    bullets: list[BulletChoice]  # MIN..MAX_BULLETS_PER_STATION (validator)


class PlanFlags(_StrictModel):
    # include the fixed location/relocation fragment in the letter closing
    mention_location_note: bool


class TailoringPlan(_StrictModel):
    """LLM call 2: pure selection from the profile pools — IDs, no facts."""

    headline_id: str = Field(min_length=1)
    stations: list[StationPlan]
    extracurricular_ids: list[str]
    skills_order: list[str]
    flags: PlanFlags


class ProfileMatch(_StrictModel):
    """Honest posting-vs-profile fit assessment — decision support in the
    review step, not a feel-good feature. Calibration rules live in
    app/prompts/match.md; the score is clamped to 0-100 in app/match.py."""

    score: int
    strengths: list[str]  # 2-4, each tied to concrete profile content
    gaps: list[str]  # 1-3, honest, most important first


class LetterSlots(_StrictModel):
    """LLM call 3: the variable letter body; the frame is letter.typ."""

    hook: str = Field(min_length=1)
    fit_1: str = Field(min_length=1)
    fit_2: str = Field(min_length=1)
    fit_3: str | None  # optional third fit paragraph (letter.typ allows 2-3)
    closing_variant: str = Field(min_length=1)

    def fits(self) -> list[str]:
        return [f for f in (self.fit_1, self.fit_2, self.fit_3) if f]

    def body_chars(self) -> int:
        return len(self.hook) + sum(len(f) for f in self.fits()) + len(self.closing_variant)


class Revision(_StrictModel):
    """LLM revise call: user instruction → reworked plan + slots. Same fact
    bounds as the original pipeline; whatever the instruction demanded that
    is not backed by the profile lands in notes instead of the documents."""

    plan: TailoringPlan
    slots: LetterSlots
    notes: str | None  # what could not be implemented within the fact bounds
