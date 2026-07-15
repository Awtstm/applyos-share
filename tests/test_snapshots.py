"""Snapshot tests (roadmap 2.8) — fully offline.

The snapshots under tests/fixtures/snapshots/ are one recorded, validated
live run (example profile + example posting; see tests/record_snapshots.py).
These tests pin the pipeline contracts:

1. recorded stage outputs still parse against the current schemas,
2. the recorded application still passes the current validator,
3. the deterministic render transformation (plan/slots → template data)
   reproduces the recorded template data exactly.

A failure here means a contract changed — either fix the regression or
consciously re-record via `uv run python -m tests.record_snapshots`.
"""

import json
from pathlib import Path

import pytest

from app.ingest import read_source
from app.profile import load_profile
from app.render_data import cv_data, letter_data
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan
from app.validate import validate_application

SNAPSHOTS = Path(__file__).resolve().parent / "fixtures" / "snapshots"
POSTING = Path(__file__).resolve().parent / "fixtures" / "postings" / "example-posting.html"
PROFILE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"

pytestmark = pytest.mark.skipif(
    not SNAPSHOTS.exists(), reason="no snapshots recorded yet (tests/record_snapshots.py)"
)


def _load(name: str) -> dict:
    return json.loads(
        (SNAPSHOTS / f"example-posting.{name}.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def recorded():
    return {
        "analysis": JobAnalysis.model_validate(_load("analysis")),
        "plan": TailoringPlan.model_validate(_load("plan")),
        "slots": LetterSlots.model_validate(_load("slots")),
    }


def test_recorded_application_still_validates(recorded):
    profile = load_profile(PROFILE)
    posting = read_source(str(POSTING))
    report = validate_application(
        profile, recorded["analysis"], recorded["plan"], recorded["slots"], posting
    )
    assert report.ok, report.errors


def test_cv_render_data_matches_snapshot(recorded):
    profile = load_profile(PROFILE)
    lang = recorded["analysis"].language
    assert cv_data(profile, lang, recorded["plan"]) == _load("cv_data")


def test_letter_render_data_matches_snapshot(recorded):
    profile = load_profile(PROFILE)
    lang = recorded["analysis"].language
    generated = letter_data(
        profile,
        lang,
        recorded["analysis"],
        recorded["slots"],
        mention_location_note=recorded["plan"].flags.mention_location_note,
    )
    assert generated == _load("letter_data")
