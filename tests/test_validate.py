"""Anti-fabrication tests: the validator must structurally reject every way
the LLM could smuggle invented facts into a rendered document."""

from pathlib import Path

import pytest

from app.profile import load_profile
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan
from app.validate import (
    detect_language,
    validate_analysis,
    validate_application,
    validate_letter,
    validate_plan,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"

POSTING = (
    "Wir suchen eine:n Strategy Analyst (m/w/d) für unser Team in Köln. "
    "Sie bringen Erfahrung mit Business Cases und Stakeholder-Management mit."
)


@pytest.fixture
def profile():
    return load_profile(EXAMPLE)


def make_analysis(**overrides) -> JobAnalysis:
    data = {
        "company": "Beispiel Firma",
        "role_title": "Strategy Analyst",
        "language": "de",
        "contact_person": None,
        "top_requirements": ["Business Cases", "Stakeholder-Management"],
        "keywords": ["Strategie"],
        "seniority": "entry",
        "notes": None,
    }
    data.update(overrides)
    return JobAnalysis.model_validate(data)


def make_plan(**overrides) -> TailoringPlan:
    data = {
        "headline_id": "hl-01",
        "stations": [
            {
                "station_id": "example-co",
                "bullets": [
                    {"bullet_id": "exco-01", "rephrased_text": None},
                    {"bullet_id": "exco-02", "rephrased_text": None},
                ],
            }
        ],
        "extracurricular_ids": ["ec-01"],
        "skills_order": ["sk-01", "sk-02"],
        "flags": {"mention_location_note": True},
    }
    data.update(overrides)
    return TailoringPlan.model_validate(data)


def make_slots(**overrides) -> LetterSlots:
    data = {
        "hook": (
            "mit großem Interesse habe ich Ihre Ausschreibung für die Position als "
            "Strategy Analyst gelesen und möchte mich bei Ihnen bewerben."
        ),
        "fit_1": (
            "In Ihrer Ausschreibung heben Sie Business Cases hervor. Diesen Bereich "
            "habe ich während meiner Zeit bei Example Consulting GmbH verantwortet "
            "und dabei 8 Kundenprojekte koordiniert."
        ),
        "fit_2": (
            "Ebenso wichtig ist Ihnen das Stakeholder-Management. Hier bringe ich "
            "Erfahrung aus der Koordination mit Fachbereichen und Kunden mit."
        ),
        "fit_3": None,
        "closing_variant": (
            "Über die Gelegenheit, mein Profil in einem persönlichen Gespräch "
            "näher vorzustellen, freue ich mich sehr."
        ),
    }
    data.update(overrides)
    return LetterSlots.model_validate(data)


# ── happy path ───────────────────────────────────────────────────────────


def test_valid_application_passes(profile):
    report = validate_application(profile, make_analysis(), make_plan(), make_slots(), POSTING)
    assert report.ok, report.errors


# ── ID existence ─────────────────────────────────────────────────────────


def test_invented_bullet_id_rejected(profile):
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {"bullet_id": "exco-01", "rephrased_text": None},
                    {"bullet_id": "exco-99", "rephrased_text": None},
                ],
            }
        ]
    )
    errors = validate_plan(plan, profile, "de")
    assert any("exco-99" in e for e in errors)


def test_bullet_from_wrong_station_rejected(profile):
    # edu-01-a exists in the profile, but not in station example-co
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {"bullet_id": "exco-01", "rephrased_text": None},
                    {"bullet_id": "edu-01-a", "rephrased_text": None},
                ],
            }
        ]
    )
    errors = validate_plan(plan, profile, "de")
    assert any("edu-01-a" in e and "does not exist in this station" in e for e in errors)


def test_unknown_station_headline_skill_extracurricular_rejected(profile):
    plan = make_plan(
        headline_id="hl-99",
        stations=[
            {
                "station_id": "invented-co",
                "bullets": [
                    {"bullet_id": "exco-01", "rephrased_text": None},
                    {"bullet_id": "exco-02", "rephrased_text": None},
                ],
            }
        ],
        extracurricular_ids=["ec-99"],
        skills_order=["sk-01", "sk-99"],
    )
    errors = "\n".join(validate_plan(plan, profile, "de"))
    for marker in ("hl-99", "invented-co", "ec-99", "sk-99"):
        assert marker in errors


def test_bullet_count_bounds(profile):
    # a single bullet is fine (concise stations); zero is not
    single = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [{"bullet_id": "exco-01", "rephrased_text": None}],
            }
        ]
    )
    assert validate_plan(single, profile, "de") == []
    empty = make_plan(stations=[{"station_id": "example-co", "bullets": []}])
    errors = validate_plan(empty, profile, "de")
    assert any("0 bullets" in e for e in errors)


def test_total_bullet_budget_rejected(profile):
    # synthetic profile with enough bullets that 11 valid selections exist
    base = profile.model_dump()
    base["stations"] = [
        {
            "id": f"station-{i}",
            "employer": f"Firma {i}",
            "role_de": "Rolle",
            "role_en": "Role",
            "period": "2024",
            "location": "Köln, DE",
            "bullets": [
                {
                    "id": f"s{i}-b{j}",
                    "text_de": f"Bullet {i}-{j} deutsch",
                    "text_en": f"Bullet {i}-{j} english",
                }
                for j in range(4)
            ],
        }
        for i in range(3)
    ]
    from app.profile import Profile

    big = Profile.model_validate(base)
    plan = make_plan(
        stations=[
            {
                "station_id": f"station-{i}",
                "bullets": [
                    {"bullet_id": f"s{i}-b{j}", "rephrased_text": None}
                    for j in range(4 if i < 2 else 3)  # 4 + 4 + 3 = 11
                ],
            }
            for i in range(3)
        ],
        extracurricular_ids=[],
        skills_order=[],
    )
    errors = validate_plan(plan, big, "de")
    assert any("11 bullets across all stations" in e for e in errors)
    # one bullet fewer is fine
    plan10 = make_plan(
        stations=[
            {
                "station_id": f"station-{i}",
                "bullets": [
                    {"bullet_id": f"s{i}-b{j}", "rephrased_text": None}
                    for j in range(4 if i < 2 else 2)  # 4 + 4 + 2 = 10
                ],
            }
            for i in range(3)
        ],
        extracurricular_ids=[],
        skills_order=[],
    )
    assert validate_plan(plan10, big, "de") == []


# ── bounded rephrasing ───────────────────────────────────────────────────


def test_rephrasing_with_new_number_rejected(profile):
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {
                        "bullet_id": "exco-01",
                        # original says 8 projects / EUR 3.5m — 12 is invented
                        "rephrased_text": "Koordination von 12 Kundenprojekten mit Budget",
                    },
                    {"bullet_id": "exco-02", "rephrased_text": None},
                ],
            }
        ]
    )
    errors = validate_plan(plan, profile, "de")
    assert any("new numbers" in e and "12" in e for e in errors)


def test_rephrasing_too_long_rejected(profile):
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {"bullet_id": "exco-02", "rephrased_text": "Aufbau " * 40},
                    {"bullet_id": "exco-01", "rephrased_text": None},
                ],
            }
        ]
    )
    errors = validate_plan(plan, profile, "de")
    assert any("rephrasing is" in e and "max" in e for e in errors)


def test_rephrasing_headroom_for_short_bullets(profile):
    # exco-02 original is 42 chars; 1.5x would forbid 68 chars, but the
    # absolute headroom (+50) allows a modestly longer rephrasing
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {
                        "bullet_id": "exco-02",
                        "rephrased_text": (
                            "Aufbau eines KPI-Dashboards zur Steuerung der laufenden "
                            "Kundenprojekte im Team"
                        ),
                    },
                    {"bullet_id": "exco-01", "rephrased_text": None},
                ],
            }
        ]
    )
    assert validate_plan(plan, profile, "de") == []


def test_rephrasing_language_mismatch_rejected(profile):
    plan = make_plan(
        stations=[
            {
                "station_id": "example-co",
                "bullets": [
                    {
                        "bullet_id": "exco-01",
                        "rephrased_text": (
                            "I coordinated several of the client projects and was "
                            "responsible for the invoice volume of the team."
                        ),
                    },
                    {"bullet_id": "exco-02", "rephrased_text": None},
                ],
            }
        ]
    )
    errors = validate_plan(plan, profile, "de")
    assert any("looks like 'en'" in e for e in errors)


def test_missing_station_rejected(profile):
    # example profile has station example-co; a plan without it violates
    # the gapless-CV rule
    plan = make_plan(stations=[])
    errors = validate_plan(plan, profile, "de")
    assert any("example-co" in e and "missing" in e for e in errors)


def test_station_coverage_fallback_inserts_default_bullet(profile):
    from app.schemas import TailoringPlan
    from app.tailor import ensure_station_coverage

    empty = TailoringPlan.model_validate({
        "headline_id": "hl-01",
        "stations": [],  # model omitted the station entirely
        "extracurricular_ids": [],
        "skills_order": [],
        "flags": {"mention_location_note": False},
    })
    fixed = ensure_station_coverage(profile, empty)
    assert [s.station_id for s in fixed.stations] == ["example-co"]
    # exco-01 is the default-marked bullet in the example profile
    assert fixed.stations[0].bullets[0].bullet_id == "exco-01"
    assert validate_plan(fixed, profile, "de") == []

    zero_bullets = TailoringPlan.model_validate({
        "headline_id": "hl-01",
        "stations": [{"station_id": "example-co", "bullets": []}],
        "extracurricular_ids": [],
        "skills_order": [],
        "flags": {"mention_location_note": False},
    })
    fixed = ensure_station_coverage(profile, zero_bullets)
    assert fixed.stations[0].bullets[0].bullet_id == "exco-01"


# ── letter slots ─────────────────────────────────────────────────────────


def test_letter_total_body_budget(profile):
    # the user's real case: fits of 516/517 chars, no fit_3 — must be valid
    long_fit = ("In Ihrer Ausschreibung heben Sie die Analyse hervor und ich "
                "habe dazu bei Example Consulting GmbH gearbeitet. ") * 5
    assert len(long_fit[:516]) > 500
    slots = make_slots(fit_1=long_fit[:516], fit_2=long_fit[:517])
    assert validate_letter(slots, profile, POSTING, "de") == []

    # but a body over the calibrated total budget fails, even if every
    # single slot stays under the 700-char outlier guard
    slots = make_slots(
        hook=long_fit[:650], fit_1=long_fit[:650], fit_2=long_fit[:650],
        fit_3=long_fit[:650], closing_variant=long_fit[:400],
    )
    errors = validate_letter(slots, profile, POSTING, "de")
    assert any("body is" in e and "2100" in e for e in errors)


def test_letter_with_invented_number_rejected(profile):
    slots = make_slots(fit_2=make_slots().fit_2 + " Dabei habe ich 777 Projekte geleitet.")
    errors = validate_letter(slots, profile, POSTING, "de")
    assert any("777" in e for e in errors)


def test_letter_with_invented_company_rejected(profile):
    slots = make_slots(fit_2=make_slots().fit_2 + " Zuletzt war ich bei Acme GmbH tätig.")
    errors = validate_letter(slots, profile, POSTING, "de")
    assert any("Acme GmbH" in e for e in errors)


def test_letter_slot_too_long_rejected(profile):
    slots = make_slots(hook="Sehr geehrte Damen und Herren, " * 40)
    errors = validate_letter(slots, profile, POSTING, "de")
    assert any("letter/hook" in e and "chars" in e for e in errors)


def test_letter_language_mismatch_rejected(profile):
    slots = make_slots(
        hook=(
            "I read your posting for the position with great interest and I "
            "would like to apply for the role in your team."
        )
    )
    errors = validate_letter(slots, profile, POSTING, "de")
    assert any("letter/hook" in e and "looks like 'en'" in e for e in errors)


# ── analysis + helpers ───────────────────────────────────────────────────


def test_analysis_bounds():
    analysis = make_analysis(top_requirements=[f"req {i}" for i in range(6)])
    assert any("top_requirements" in e for e in validate_analysis(analysis))


def test_detect_language():
    assert detect_language(
        "Ich habe die Analyse mit dem Team durchgeführt und die Ergebnisse "
        "für die Geschäftsführung aufbereitet."
    ) == "de"
    assert detect_language(
        "I prepared the analysis together with the team and presented the "
        "results to the management board."
    ) == "en"
    assert detect_language("kurz") is None
