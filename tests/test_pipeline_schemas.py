"""Schema tests for the pipeline contracts (JobAnalysis, TailoringPlan,
LetterSlots): strictness, required-but-nullable fields, round-trips."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    BulletChoice,
    JobAnalysis,
    LetterSlots,
    PlanFlags,
    StationPlan,
    TailoringPlan,
)

ANALYSIS = {
    "company": "Example Consulting GmbH",
    "role_title": "Strategy Analyst",
    "language": "de",
    "contact_person": None,
    "top_requirements": ["Business Cases", "Stakeholder-Management"],
    "keywords": ["Strategie", "Beratung"],
    "seniority": "entry",
    "notes": None,
}

PLAN = {
    "headline_id": "hl-01",
    "stations": [
        {
            "station_id": "example-co",
            "bullets": [
                {"bullet_id": "exco-01", "rephrased_text": None},
                {"bullet_id": "exco-02", "rephrased_text": "Aufbau eines KPI-Dashboards"},
            ],
        }
    ],
    "extracurricular_ids": ["ec-01"],
    "skills_order": ["sk-01", "sk-02"],
    "flags": {"mention_location_note": True},
}

SLOTS = {
    "hook": "mit großem Interesse ...",
    "fit_1": "In Ihrer Ausschreibung ...",
    "fit_2": "Ebenso wichtig ...",
    "fit_3": None,
    "closing_variant": "Ein Einstieg ist ab sofort möglich.",
}


def test_job_analysis_parses():
    analysis = JobAnalysis.model_validate(ANALYSIS)
    assert analysis.language == "de"
    assert analysis.contact_person is None


def test_job_analysis_rejects_unknown_language():
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**ANALYSIS, "language": "fr"})


def test_extra_fields_rejected_everywhere():
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**ANALYSIS, "salary": "100k"})
    with pytest.raises(ValidationError):
        TailoringPlan.model_validate({**PLAN, "new_experience": "invented"})
    with pytest.raises(ValidationError):
        LetterSlots.model_validate({**SLOTS, "ps": "erfunden"})


def test_nullable_fields_are_required():
    # required-but-nullable: omitting the key must fail, null must pass
    missing = {k: v for k, v in ANALYSIS.items() if k != "contact_person"}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(missing)
    with pytest.raises(ValidationError):
        BulletChoice.model_validate({"bullet_id": "exco-01"})
    assert BulletChoice.model_validate(
        {"bullet_id": "exco-01", "rephrased_text": None}
    ).rephrased_text is None


def test_plan_round_trips_through_json():
    plan = TailoringPlan.model_validate(PLAN)
    assert TailoringPlan.model_validate_json(plan.model_dump_json()) == plan
    assert plan.stations[0].bullets[1].rephrased_text == "Aufbau eines KPI-Dashboards"


def test_letter_slots_fits_helper():
    slots = LetterSlots.model_validate(SLOTS)
    assert slots.fits() == [SLOTS["fit_1"], SLOTS["fit_2"]]
    three = LetterSlots.model_validate({**SLOTS, "fit_3": "Drittens ..."})
    assert len(three.fits()) == 3


def test_empty_ids_rejected():
    with pytest.raises(ValidationError):
        StationPlan.model_validate({"station_id": "", "bullets": []})
    with pytest.raises(ValidationError):
        TailoringPlan.model_validate({**PLAN, "headline_id": ""})


def test_plan_flags_required():
    with pytest.raises(ValidationError):
        PlanFlags.model_validate({})
