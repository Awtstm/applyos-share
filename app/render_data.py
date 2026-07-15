"""Default render data: derive template data.json content from the profile
with zero LLM involvement (Phase 1 acceptance criterion).

The dict shapes produced here are the render contract of the Typst
templates. Phase 2 keeps the shapes and only replaces the selection
defaults (bullets marked default in the profile) with plan/slots-driven
content. The CV headline is fixed (both degrees); recipient contact
person comes from tailoring.
"""

import argparse
import json
import re

from app.profile import Bullet, Profile, Station, load_profile
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan


def _pick(lang: str, de: str, en: str) -> str:
    return de if lang == "de" else en


def _fmt_period(period: str) -> str:
    """Normalize ISO-style YYYY-MM dates to MM/YYYY; leave everything else
    (already MM/YYYY, year-only ranges, "heute"/"today") untouched."""
    return re.sub(r"\b(\d{4})-(\d{2})\b", r"\2/\1", period)


# German remnants in fields the profile stores only once (employer,
# location, institution, period). Ordered: specific before generic.
_EN_FIXES = (
    ("(Projekt bei BITBW)", "(project at BITBW)"),
    ("Universität Utrecht", "Utrecht University"),
    ("Köln, DE", "Cologne, Germany"),
    (", DE", ", Germany"),
    ("heute", "present"),
)


def _en(text: str, lang: str) -> str:
    if lang != "en":
        return text
    for de, en in _EN_FIXES:
        text = text.replace(de, en)
    return text


# open-ended periods ("05/2026 – heute") sort before everything else
_OPEN_END_WORDS = ("heute", "present", "today", "aktuell")


def _period_end_key(period: str) -> tuple[int, int]:
    """(year, month) of a period's end date, for strict reverse-chronological
    station order. Understands MM/YYYY, YYYY-MM, bare years, and open ends."""
    if any(word in period.lower() for word in _OPEN_END_WORDS):
        return (9999, 12)
    dates = [(int(y), int(m)) for m, y in re.findall(r"(\d{2})/(\d{4})", period)]
    dates += [(int(y), int(m)) for y, m in re.findall(r"(\d{4})-(\d{2})", period)]
    if not dates:
        dates = [(int(y), 12) for y in re.findall(r"\b(\d{4})\b", period)]
    return max(dates, default=(0, 0))


def _station_entry(station: Station, lang: str, bullets: list[str]) -> dict:
    return {
        "role": _pick(lang, station.role_de, station.role_en),
        "employer": _en(station.employer, lang),
        "location": _en(station.location, lang),
        "period": _en(_fmt_period(station.period), lang),
        "bullets": bullets,
    }


def _planned_stations(profile: Profile, lang: str, plan: TailoringPlan) -> list[dict]:
    """Resolve a validated plan: bullet IDs → texts (rephrased if provided).

    Assumes the plan passed app/validate.py — unknown IDs raise KeyError here.
    """
    stations_by_id = {station.id: station for station in profile.stations}
    ordered = sorted(
        plan.stations,
        key=lambda sp: _period_end_key(stations_by_id[sp.station_id].period),
        reverse=True,
    )
    entries = []
    for station_plan in ordered:
        station = stations_by_id[station_plan.station_id]
        pool: dict[str, Bullet] = {bullet.id: bullet for bullet in station.bullets}
        bullets = [
            choice.rephrased_text
            or _pick(lang, pool[choice.bullet_id].text_de, pool[choice.bullet_id].text_en)
            for choice in station_plan.bullets
        ]
        entries.append(_station_entry(station, lang, bullets))
    return entries


def cv_data(profile: Profile, lang: str, plan: TailoringPlan | None = None) -> dict:
    """Template data for cv.typ; without a plan, the profile's default
    selection is rendered (Phase 1 behavior, golden tests)."""
    basics = profile.basics
    contact = [basics.location, basics.phone, basics.email]
    if basics.linkedin:
        contact.append(basics.linkedin)
    # fixed headline: both degrees (user decision; headline_pool stays
    # reserved for the letter/tailoring, unused in the CV)
    headline = " · ".join(
        _pick(lang, edu.degree_de, edu.degree_en) for edu in profile.education
    )

    if plan is None:
        stations = [
            _station_entry(
                st, lang, [_pick(lang, b.text_de, b.text_en) for b in st.bullets if b.default]
            )
            for st in sorted(
                profile.stations, key=lambda s: _period_end_key(s.period), reverse=True
            )
        ]
        extracurricular = [
            _pick(lang, e.text_de, e.text_en) for e in profile.extracurricular
        ]
        skills = [_pick(lang, sk.label_de, sk.label_en) for sk in profile.skills]
    else:
        stations = _planned_stations(profile, lang, plan)
        extras_by_id = {entry.id: entry for entry in profile.extracurricular}
        extracurricular = [
            _pick(lang, extras_by_id[eid].text_de, extras_by_id[eid].text_en)
            for eid in plan.extracurricular_ids
        ]
        skills_by_id = {sk.id: sk for sk in profile.skills}
        skills = [
            _pick(lang, skills_by_id[sid].label_de, skills_by_id[sid].label_en)
            for sid in plan.skills_order
        ]

    return {
        "lang": lang,
        "name": basics.name,
        "headline": headline,
        "contact": contact,
        "stations": stations,
        "education": [
            {
                "degree": _pick(lang, edu.degree_de, edu.degree_en),
                "institution": _en(edu.institution, lang),
                "location": _en(edu.location, lang),
                "period": edu.period,
                "details": [
                    _pick(lang, d.text_de, d.text_en)
                    for d in edu.details
                    if d.default
                ],
            }
            for edu in profile.education
        ],
        "extracurricular": extracurricular,
        "skills": skills,
        "languages": [_pick(lang, la.label_de, la.label_en) for la in profile.languages],
    }


# Phase 1 placeholder slots mirroring references/Anschreiben_Beispiel.docx
# (local style reference, gitignored).
# Phase 2 fills these from LetterSlots (hook, 2-3 fits, closing) instead.
_LETTER_SLOTS = {
    "de": {
        "subject": "Bewerbung als [Positionsbezeichnung]",
        "company": "[Firmenname]",
        # from tailoring when the posting names one; None = line omitted,
        # greeting falls back to the "unknown" variant
        "contact_person": None,
        "date": "[Datum]",
        "hook": (
            "mit großem Interesse habe ich Ihre Ausschreibung für die Position als "
            "[Positionsbezeichnung] gelesen. Die Verbindung aus [zentraler Aufgabe der Rolle] "
            "und [zweitem Aspekt] entspricht genau dem, worauf ich meine bisherige Laufbahn "
            "ausgerichtet habe - und weshalb mich gerade diese Stelle bei [Firmenname] reizt."
        ),
        "fits": [
            (
                "In Ihrer Ausschreibung heben Sie [gewünschten Skill 1] hervor. Diesen Bereich "
                "habe ich während [konkreter Station] unmittelbar verantwortet: [belegtes, "
                "idealerweise quantifiziertes Ergebnis]."
            ),
            (
                "Ebenso wichtig ist Ihnen [gewünschter Skill 2]. Hier bringe ich [zweite Station "
                "oder Kompetenzfeld] mit: [konkretes Beispiel mit Bezug zur Rolle]."
            ),
        ],
        "closing": (
            "Ein Einstieg ist für mich ab [Einstiegsdatum] möglich. Über die Gelegenheit, mein "
            "Profil in einem persönlichen Gespräch näher vorzustellen, freue ich mich sehr."
        ),
    },
    "en": {
        "subject": "Application for [Position Title]",
        "company": "[Company Name]",
        "contact_person": None,
        "date": "[Date]",
        "hook": (
            "I read your posting for the position of [Position Title] with great interest. "
            "The combination of [core responsibility] and [second aspect] matches exactly "
            "what I have built my career towards - and why this role at [Company Name] "
            "appeals to me."
        ),
        "fits": [
            (
                "Your posting highlights [desired skill 1]. I owned this area during "
                "[specific station]: [evidenced, ideally quantified result]."
            ),
            (
                "Equally important to you is [desired skill 2]. Here I bring [second station "
                "or competence area]: [concrete example tied to the role]."
            ),
        ],
        "closing": (
            "I am available to start from [start date]. I would welcome the opportunity "
            "to present my profile in a personal conversation."
        ),
    },
}


def letter_data(
    profile: Profile,
    lang: str,
    analysis: JobAnalysis | None = None,
    slots: LetterSlots | None = None,
    mention_location_note: bool = True,
    date: str | None = None,
) -> dict:
    """Template data for letter.typ; without analysis/slots the Phase 1
    placeholder body is rendered (golden tests)."""
    basics = profile.basics
    fixed = profile.letter_fixed
    defaults = _LETTER_SLOTS[lang]
    contact = f"{basics.phone} · {basics.email}"
    if basics.linkedin:
        contact += f" · {basics.linkedin}"

    if analysis is not None:
        company = analysis.company
        person = analysis.contact_person
        subject = _pick(
            lang,
            f"Bewerbung als {analysis.role_title}",
            f"Application for {analysis.role_title}",
        )
    else:
        company = defaults["company"]
        person = defaults["contact_person"]
        subject = defaults["subject"]

    recipient = [company] + ([person] if person else [])
    if person:
        greeting = _pick(lang, fixed.greeting_de, fixed.greeting_en).replace(
            "{name}", person
        )
    else:
        greeting = _pick(lang, fixed.greeting_de_unknown, fixed.greeting_en_unknown)

    hook = slots.hook if slots else defaults["hook"]
    # EN: the sentence after the salutation starts uppercase (deterministic —
    # always correct in English); DE keeps lowercase-after-comma per prompt,
    # which cannot be automated (noun/Sie starts are correctly capitalized)
    if lang == "en" and hook:
        hook = hook[0].upper() + hook[1:]
    fits = slots.fits() if slots else defaults["fits"]
    closing_variant = slots.closing_variant if slots else defaults["closing"]
    location_note = _pick(lang, fixed.location_note_de, fixed.location_note_en)
    closing = f"{location_note} {closing_variant}" if mention_location_note else closing_variant

    return {
        "lang": lang,
        "sender": {
            "name": basics.name,
            "address": basics.address or basics.location,
            "contact": contact,
        },
        "recipient": recipient,
        "city": basics.location.split(",")[0],
        "date": date or defaults["date"],
        "subject": subject,
        "greeting": greeting,
        "hook": hook,
        "fits": fits,
        "closing": closing,
        "closing_formula": _pick(lang, fixed.closing_de, fixed.closing_en),
        "signature_name": basics.name,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Print template data.json to stdout")
    parser.add_argument("doc", choices=["cv", "letter"])
    parser.add_argument("--lang", default="de", choices=["de", "en"])
    parser.add_argument("--profile", default="profile/profile.example.yaml")
    args = parser.parse_args()
    profile = load_profile(args.profile)
    builder = cv_data if args.doc == "cv" else letter_data
    print(json.dumps(builder(profile, args.lang), ensure_ascii=False))


if __name__ == "__main__":
    main()
