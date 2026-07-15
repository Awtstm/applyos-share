"""Pipeline orchestration tests (offline, LLM steps mocked): the automatic
letter-shortening retry fires exactly once and stays visible."""

import json
from pathlib import Path

import pytest

import app.pipeline as pipeline
from app.ingest import read_source
from app.profile import load_profile
from app.schemas import JobAnalysis, LetterSlots, Revision, TailoringPlan

TESTS = Path(__file__).resolve().parent
EXAMPLE = TESTS.parent / "profile" / "profile.example.yaml"
SNAPSHOTS = TESTS / "fixtures" / "snapshots"

FILLER = (
    "Dieser Absatz dient der Längenprüfung des Anschreibens und enthält "
    "bewusst weder Kennziffern noch Firmennamen, nur neutralen Fließtext. "
)


def _slot_text(n: int) -> str:
    return (FILLER * 10)[:n]


def _snap(name: str):
    return json.loads((SNAPSHOTS / f"example-posting.{name}.json").read_text("utf-8"))


@pytest.fixture
def wired(monkeypatch):
    profile = load_profile(EXAMPLE)
    posting = read_source(str(TESTS / "fixtures" / "postings" / "example-posting.html"))
    analysis = JobAnalysis.model_validate(_snap("analysis"))
    plan = TailoringPlan.model_validate(_snap("plan"))
    slim = LetterSlots.model_validate(_snap("slots"))
    fat = LetterSlots.model_validate({
        "hook": _slot_text(600), "fit_1": _slot_text(600), "fit_2": _slot_text(600),
        "fit_3": _slot_text(600), "closing_variant": _slot_text(400),
    })
    assert fat.body_chars() > 2100

    monkeypatch.setattr(pipeline, "analyze_posting", lambda *a, **k: analysis)
    monkeypatch.setattr(pipeline, "evaluate_match", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "make_plan", lambda *a, **k: plan)
    monkeypatch.setattr(pipeline, "make_letter_slots", lambda *a, **k: fat)
    return {"profile": profile, "posting": posting, "plan": plan,
            "slim": slim, "fat": fat}


def test_budget_overrun_triggers_single_auto_revise(wired, monkeypatch):
    seen = {}

    def fake_revise(profile, analysis, plan, slots, instruction, posting_text):
        seen["count"] = seen.get("count", 0) + 1
        seen["instruction"] = instruction
        return Revision(plan=plan, slots=wired["slim"], notes=None)

    monkeypatch.setattr(pipeline, "revise_application", fake_revise)
    result = pipeline.run_pipeline(wired["profile"], wired["posting"])
    assert seen["count"] == 1
    assert "2100" in seen["instruction"] and "Kürze" in seen["instruction"]
    assert result.report.ok, result.report.errors
    assert "Automatisch gekürzt" in result.auto_note
    assert str(wired["fat"].body_chars()) in result.auto_note


def test_failed_auto_revise_surfaces_validation_error(wired, monkeypatch):
    # the retry runs once; if the letter is still over budget, the normal
    # validation error surfaces — no second automatic attempt
    calls = {"count": 0}

    def stubborn_revise(profile, analysis, plan, slots, instruction, posting_text):
        calls["count"] += 1
        return Revision(plan=plan, slots=wired["fat"], notes=None)

    monkeypatch.setattr(pipeline, "revise_application", stubborn_revise)
    result = pipeline.run_pipeline(wired["profile"], wired["posting"])
    assert calls["count"] == 1
    assert not result.report.ok
    assert any("body is" in e for e in result.report.errors)
    assert result.auto_note is not None  # the attempt stays visible


def test_bullet_overrun_triggers_auto_revise(wired, monkeypatch):
    fat_plan = TailoringPlan.model_validate({
        "headline_id": "hl-01",
        "stations": [{
            "station_id": "example-co",
            "bullets": [{"bullet_id": f"b{i}", "rephrased_text": None} for i in range(11)],
        }],
        "extracurricular_ids": [], "skills_order": [],
        "flags": {"mention_location_note": False},
    })
    monkeypatch.setattr(pipeline, "make_plan", lambda *a, **k: fat_plan)
    monkeypatch.setattr(pipeline, "make_letter_slots", lambda *a, **k: wired["slim"])
    seen = {}

    def fake_revise(profile, analysis, plan, slots, instruction, posting_text):
        seen["count"] = seen.get("count", 0) + 1
        seen["instruction"] = instruction
        return Revision(plan=wired["plan"], slots=slots, notes=None)

    monkeypatch.setattr(pipeline, "revise_application", fake_revise)
    result = pipeline.run_pipeline(wired["profile"], wired["posting"])
    assert seen["count"] == 1
    assert "entbehrlichsten" in seen["instruction"] and "10" in seen["instruction"]
    after = sum(len(sp.bullets) for sp in wired["plan"].stations)
    assert f"Automatisch reduziert: 11 → {after} Bullets." in result.auto_note
    assert result.report.ok, result.report.errors


def test_double_overrun_is_one_combined_revise(wired, monkeypatch):
    fat_plan = TailoringPlan.model_validate({
        "headline_id": "hl-01",
        "stations": [{
            "station_id": "example-co",
            "bullets": [{"bullet_id": f"b{i}", "rephrased_text": None} for i in range(12)],
        }],
        "extracurricular_ids": [], "skills_order": [],
        "flags": {"mention_location_note": False},
    })
    monkeypatch.setattr(pipeline, "make_plan", lambda *a, **k: fat_plan)
    calls = {"count": 0}

    def fake_revise(profile, analysis, plan, slots, instruction, posting_text):
        calls["count"] += 1
        assert "entbehrlichsten" in instruction and "Kürze" in instruction
        return Revision(plan=wired["plan"], slots=wired["slim"], notes="fit_3 entfernt.")

    monkeypatch.setattr(pipeline, "revise_application", fake_revise)
    result = pipeline.run_pipeline(wired["profile"], wired["posting"])
    assert calls["count"] == 1  # both overruns -> ONE combined pass
    assert "Automatisch reduziert" in result.auto_note
    assert "Automatisch gekürzt" in result.auto_note
    assert "fit_3 entfernt." in result.auto_note
    assert result.report.ok


def test_no_retry_when_budget_holds(wired, monkeypatch):
    monkeypatch.setattr(pipeline, "make_letter_slots", lambda *a, **k: wired["slim"])
    monkeypatch.setattr(
        pipeline, "revise_application",
        lambda *a, **k: pytest.fail("revise must not run when the budget holds"),
    )
    result = pipeline.run_pipeline(wired["profile"], wired["posting"])
    assert result.report.ok and result.auto_note is None
