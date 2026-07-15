"""Validator: structural anti-fabrication guarantees (CLAUDE.md rules 1+2).

Pure, deterministic functions — no LLM involved. Every LLM output passes
through here before anything is rendered:

1. ID existence — every referenced ID must exist in the profile pools, and
   bullets must belong to the station they are planned for. An ID the LLM
   invented can therefore never reach a PDF.
2. Bounded rephrasing — rephrased text may not exceed REPHRASE_MAX_RATIO of
   the original, and every number in it must already appear in the original.
3. Letter slots — numbers and company names must come from the profile or
   the posting text; per-slot length bounds.
4. Language — a cheap stopword heuristic checks that generated text matches
   the language of the posting analysis.

Errors are collected into a ValidationReport (not raised one-by-one) so the
CLI can show every violation at once; any error means: no render.
"""

import re
from dataclasses import dataclass, field

from app.profile import Profile
from app.schemas import (
    LETTER_BODY_MAX_CHARS,
    MAX_BULLETS_PER_STATION,
    MAX_KEYWORDS,
    MAX_SLOT_CHARS,
    MAX_TOP_REQUIREMENTS,
    MAX_TOTAL_BULLETS,
    MIN_BULLETS_PER_STATION,
    REPHRASE_HEADROOM_CHARS,
    REPHRASE_MAX_RATIO,
    JobAnalysis,
    LetterSlots,
    TailoringPlan,
)

# ── helpers ──────────────────────────────────────────────────────────────

_DE_STOPWORDS = frozenset([
    "und", "der", "die", "das", "mit", "für", "nicht", "eine", "einem", "einer",
    "im", "von", "zu", "bei", "auf", "als", "den", "dem", "sich", "ist", "sind",
    "habe", "ich", "mich", "mein", "meine", "sehr", "sowie", "durch", "über", "nach",
])
_EN_STOPWORDS = frozenset([
    "the", "and", "with", "for", "of", "to", "in", "is", "are", "that", "on",
    "as", "at", "my", "have", "has", "this", "from", "which", "would", "your",
    "their", "during", "about", "into", "been", "was", "were", "i",
])

# company-ish token: "Acme GmbH", "Foo Bar Inc." — used to spot invented employers
_COMPANY_RE = re.compile(r"\b[\wÄÖÜäöüß&.-]+ (?:GmbH|AG|SE|KG|e\.V\.|Inc\.?|Ltd\.?|LLC|B\.V\.)")

_MIN_CHARS_FOR_LANG_CHECK = 40


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def detect_language(text: str) -> str | None:
    """Cheap DE/EN stopword vote; None if the text is too short to judge."""
    if len(text) < _MIN_CHARS_FOR_LANG_CHECK:
        return None
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in _DE_STOPWORDS for w in words)
    en = sum(w in _EN_STOPWORDS for w in words)
    if de == en:
        return None
    return "de" if de > en else "en"


def _profile_corpus(profile: Profile) -> str:
    """All profile text in one string — the source pool for numbers/names."""
    return profile.model_dump_json()


# ── report ───────────────────────────────────────────────────────────────


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, message: str) -> None:
        self.errors.append(message)


# ── analysis ─────────────────────────────────────────────────────────────


def validate_analysis(analysis: JobAnalysis) -> list[str]:
    errors: list[str] = []
    if len(analysis.top_requirements) > MAX_TOP_REQUIREMENTS:
        errors.append(
            f"analysis: {len(analysis.top_requirements)} top_requirements "
            f"(max {MAX_TOP_REQUIREMENTS})"
        )
    if len(analysis.keywords) > MAX_KEYWORDS:
        errors.append(f"analysis: {len(analysis.keywords)} keywords (max {MAX_KEYWORDS})")
    return errors


# ── plan ─────────────────────────────────────────────────────────────────


def _validate_rephrasing(
    label: str, original: str, rephrased: str, language: str, errors: list[str]
) -> None:
    max_len = max(REPHRASE_MAX_RATIO * len(original), len(original) + REPHRASE_HEADROOM_CHARS)
    if len(rephrased) > max_len:
        errors.append(
            f"{label}: rephrasing is {len(rephrased)} chars, original {len(original)} "
            f"(max {int(max_len)})"
        )
    new_numbers = _numbers(rephrased) - _numbers(original)
    if new_numbers:
        errors.append(f"{label}: rephrasing introduces new numbers {sorted(new_numbers)}")
    detected = detect_language(rephrased)
    if detected is not None and detected != language:
        errors.append(f"{label}: rephrasing looks like '{detected}', expected '{language}'")


def validate_plan(plan: TailoringPlan, profile: Profile, language: str) -> list[str]:
    errors: list[str] = []

    if plan.headline_id not in profile.headline_ids():
        errors.append(f"plan: unknown headline_id {plan.headline_id!r}")

    total_bullets = sum(len(sp.bullets) for sp in plan.stations)
    if total_bullets > MAX_TOTAL_BULLETS:
        errors.append(
            f"plan: {total_bullets} bullets across all stations "
            f"(max {MAX_TOTAL_BULLETS} for a one-page CV)"
        )

    stations_by_id = {station.id: station for station in profile.stations}
    seen_stations: set[str] = set()
    for station_plan in plan.stations:
        sid = station_plan.station_id
        if sid in seen_stations:
            errors.append(f"plan: station {sid!r} planned twice")
        seen_stations.add(sid)
        station = stations_by_id.get(sid)
        if station is None:
            errors.append(f"plan: unknown station_id {sid!r}")
            continue

        pool = {bullet.id: bullet for bullet in station.bullets}
        count = len(station_plan.bullets)
        if not MIN_BULLETS_PER_STATION <= count <= MAX_BULLETS_PER_STATION:
            errors.append(
                f"plan/{sid}: {count} bullets "
                f"(need {MIN_BULLETS_PER_STATION}-{MAX_BULLETS_PER_STATION})"
            )
        seen_bullets: set[str] = set()
        for choice in station_plan.bullets:
            bid = choice.bullet_id
            if bid in seen_bullets:
                errors.append(f"plan/{sid}: bullet {bid!r} selected twice")
            seen_bullets.add(bid)
            bullet = pool.get(bid)
            if bullet is None:
                errors.append(f"plan/{sid}: bullet {bid!r} does not exist in this station")
                continue
            if choice.rephrased_text is not None:
                original = bullet.text_de if language == "de" else bullet.text_en
                _validate_rephrasing(
                    f"plan/{sid}/{bid}", original, choice.rephrased_text, language, errors
                )

    # gapless CV (DACH convention): every profile station must be planned
    for station in profile.stations:
        if station.id not in seen_stations:
            errors.append(
                f"plan: station {station.id!r} missing "
                "(every station needs at least one bullet)"
            )

    extracurricular_ids = {entry.id for entry in profile.extracurricular}
    for entry_id in plan.extracurricular_ids:
        if entry_id not in extracurricular_ids:
            errors.append(f"plan: unknown extracurricular id {entry_id!r}")

    skill_ids = profile.skill_ids()
    seen_skills: set[str] = set()
    for skill_id in plan.skills_order:
        if skill_id in seen_skills:
            errors.append(f"plan: skill {skill_id!r} listed twice")
        seen_skills.add(skill_id)
        if skill_id not in skill_ids:
            errors.append(f"plan: unknown skill id {skill_id!r}")

    return errors


# ── letter ───────────────────────────────────────────────────────────────


def validate_letter(
    slots: LetterSlots, profile: Profile, posting_text: str, language: str
) -> list[str]:
    errors: list[str] = []
    source = _profile_corpus(profile) + "\n" + posting_text
    source_numbers = _numbers(source)

    # one-page guarantee: total body budget (calibrated against the rendered
    # PDF) instead of rigid per-slot limits; per-slot caps are outlier guards
    body = slots.body_chars()
    if body > LETTER_BODY_MAX_CHARS:
        errors.append(
            f"letter: body is {body} chars total (max {LETTER_BODY_MAX_CHARS} "
            "for a one-page letter)"
        )

    named_slots = [
        ("hook", slots.hook, MAX_SLOT_CHARS["hook"]),
        ("fit_1", slots.fit_1, MAX_SLOT_CHARS["fit"]),
        ("fit_2", slots.fit_2, MAX_SLOT_CHARS["fit"]),
        ("fit_3", slots.fit_3, MAX_SLOT_CHARS["fit"]),
        ("closing_variant", slots.closing_variant, MAX_SLOT_CHARS["closing_variant"]),
    ]
    for name, text, max_chars in named_slots:
        if text is None:
            continue
        if len(text) > max_chars:
            errors.append(f"letter/{name}: {len(text)} chars (max {max_chars})")
        new_numbers = _numbers(text) - source_numbers
        if new_numbers:
            errors.append(
                f"letter/{name}: numbers {sorted(new_numbers)} appear neither in the "
                "profile nor in the posting"
            )
        for company in _COMPANY_RE.findall(text):
            if company not in source:
                errors.append(
                    f"letter/{name}: company {company!r} appears neither in the "
                    "profile nor in the posting"
                )
        detected = detect_language(text)
        if detected is not None and detected != language:
            errors.append(f"letter/{name}: looks like '{detected}', expected '{language}'")

    return errors


# ── aggregate ────────────────────────────────────────────────────────────


def validate_application(
    profile: Profile,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    posting_text: str,
) -> ValidationReport:
    report = ValidationReport()
    report.errors.extend(validate_analysis(analysis))
    report.errors.extend(validate_plan(plan, profile, analysis.language))
    report.errors.extend(validate_letter(slots, profile, posting_text, analysis.language))
    return report
