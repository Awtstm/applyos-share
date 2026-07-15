"""CLI + render-integration tests: plan/slots-driven template data and the
`applyos render` path end-to-end (offline; typst required for the PDF step)."""

import json
import shutil
from pathlib import Path

import pytest

from app.cli import main
from app.pipeline import (
    application_dir,
    letter_date,
    pdf_filenames,
    render_application,
    sanitize_name,
)
from app.profile import load_profile
from app.render_data import cv_data, letter_data
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan

EXAMPLE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"
TYPST = shutil.which("typst")

ANALYSIS = JobAnalysis.model_validate({
    "company": "Beispiel Firma GmbH",
    "role_title": "Strategy Analyst",
    "language": "de",
    "contact_person": "Erika Beispiel",
    "top_requirements": ["Business Cases"],
    "keywords": ["Strategie"],
    "seniority": "entry",
    "notes": None,
})

PLAN = TailoringPlan.model_validate({
    "headline_id": "hl-01",
    "stations": [
        {
            "station_id": "example-co",
            "bullets": [
                {"bullet_id": "exco-02", "rephrased_text": "Aufbau eines KPI-Dashboards"},
                {"bullet_id": "exco-01", "rephrased_text": None},
            ],
        }
    ],
    "extracurricular_ids": [],
    "skills_order": ["sk-02", "sk-01"],
    "flags": {"mention_location_note": False},
})

SLOTS = LetterSlots.model_validate({
    "hook": "mit großem Interesse habe ich Ihre Ausschreibung als Strategy Analyst gelesen.",
    "fit_1": "In Ihrer Ausschreibung heben Sie Business Cases hervor; diesen Bereich habe "
             "ich bei Example Consulting GmbH mit 8 Kundenprojekten verantwortet.",
    "fit_2": "Ebenso bringe ich Erfahrung im Aufbau von Dashboards zur Projektsteuerung mit.",
    "fit_3": None,
    "closing_variant": "Über ein persönliches Gespräch freue ich mich sehr.",
})

POSTING = "Wir suchen einen Strategy Analyst mit Erfahrung in Business Cases."


@pytest.fixture
def profile():
    return load_profile(EXAMPLE)


def test_cv_data_resolves_plan(profile):
    data = cv_data(profile, "de", PLAN)
    bullets = data["stations"][0]["bullets"]
    # plan order, rephrased text first, original second
    assert bullets[0] == "Aufbau eines KPI-Dashboards"
    assert bullets[1].startswith("Koordination von 8 Kundenprojekten")
    assert data["extracurricular"] == []
    assert data["skills"][0] == "Stakeholder-Management"  # sk-02 first per plan


def test_cv_data_without_plan_unchanged(profile):
    data = cv_data(profile, "de")
    assert len(data["stations"][0]["bullets"]) == 1  # only default-marked exco-01


def test_stations_sorted_by_end_date(profile):
    # profile order deliberately scrambled: the CV must sort by period end,
    # newest first, with open-ended periods on top
    base = profile.model_dump()
    periods = [
        ("mid", "09/2023 – 03/2024"),
        ("old", "08/2022 – 02/2023"),
        ("current", "05/2026 – heute"),
        ("recent", "03/2024 – 09/2024"),
    ]
    base["stations"] = [
        {
            "id": sid,
            "employer": sid,
            "role_de": "Rolle",
            "role_en": "Role",
            "period": period,
            "location": "Köln, DE",
            "bullets": [
                {"id": f"{sid}-b", "text_de": "Text", "text_en": "Text", "default": True}
            ],
        }
        for sid, period in periods
    ]
    from app.profile import Profile

    scrambled = Profile.model_validate(base)
    order = [s["employer"] for s in cv_data(scrambled, "de")["stations"]]
    assert order == ["current", "recent", "mid", "old"]

    plan = TailoringPlan.model_validate({
        "headline_id": "hl-01",
        "stations": [
            {"station_id": sid, "bullets": [{"bullet_id": f"{sid}-b", "rephrased_text": None}]}
            for sid, _ in periods  # plan in scrambled order
        ],
        "extracurricular_ids": [],
        "skills_order": [],
        "flags": {"mention_location_note": False},
    })
    order = [s["employer"] for s in cv_data(scrambled, "de", plan)["stations"]]
    assert order == ["current", "recent", "mid", "old"]


def test_letter_data_uses_analysis_and_slots(profile):
    data = letter_data(profile, "de", ANALYSIS, SLOTS,
                       mention_location_note=False, date="08.07.2026")
    assert data["recipient"] == ["Beispiel Firma GmbH", "Erika Beispiel"]
    assert "Erika Beispiel" in data["greeting"]
    assert data["subject"] == "Bewerbung als Strategy Analyst"
    assert data["date"] == "08.07.2026"
    assert data["hook"] == SLOTS.hook
    assert data["fits"] == [SLOTS.fit_1, SLOTS.fit_2]
    # flags.mention_location_note=False → closing without the fixed fragment
    assert data["closing"] == SLOTS.closing_variant
    assert "Utrecht ansässig" not in data["closing"]


def test_letter_hook_capitalized_for_english_only(profile):
    english = ANALYSIS.model_copy(update={"language": "en"})
    lower_hook = SLOTS.model_copy(update={"hook": "what draws me to this role is the team."})
    data = letter_data(profile, "en", english, lower_hook)
    assert data["hook"].startswith("What draws me")
    # DE keeps lowercase after the salutation comma (German convention)
    data = letter_data(profile, "de", ANALYSIS, SLOTS)
    assert data["hook"][0].islower()


def test_letter_data_location_note_prepended(profile):
    data = letter_data(profile, "de", ANALYSIS, SLOTS, mention_location_note=True)
    assert data["closing"].endswith(SLOTS.closing_variant)
    assert data["closing"] != SLOTS.closing_variant


def test_output_naming_and_letter_date(profile):
    import datetime
    from pathlib import Path as P

    # readable names: case preserved, spaces -> underscores, specials removed
    assert sanitize_name("Müller & Söhne KG") == "Müller_Söhne_KG"
    assert sanitize_name("  Strategy / Analyst (m/w/d) ") == "Strategy_Analyst_mwd"
    assert application_dir(P("out"), ANALYSIS) == P("out/Beispiel_Firma_GmbH_Strategy_Analyst")

    # language-dependent PDF names, surname from the profile (not hardcoded)
    assert pdf_filenames(profile, ANALYSIS) == (
        "Lebenslauf_Mustermann_Beispiel_Firma_GmbH.pdf",
        "Anschreiben_Mustermann_Beispiel_Firma_GmbH.pdf",
    )
    english = ANALYSIS.model_copy(update={"language": "en"})
    assert pdf_filenames(profile, english) == (
        "CV_Mustermann_Beispiel_Firma_GmbH.pdf",
        "CoverLetter_Mustermann_Beispiel_Firma_GmbH.pdf",
    )

    day = datetime.date(2026, 7, 8)
    assert letter_date("de", day) == "08.07.2026"
    assert letter_date("en", day) == "8 July 2026"


def test_cli_tailor_rejects_bad_source(capsys):
    # example profile: the test must not depend on a personal profile.yaml
    assert main(["tailor", "does-not-exist.txt", "--profile", str(EXAMPLE)]) == 1
    assert "neither" in capsys.readouterr().err


@pytest.mark.skipif(TYPST is None, reason="typst CLI not on PATH")
def test_cli_render_from_application_json(tmp_path, profile, capsys, monkeypatch):
    monkeypatch.setenv("APPLYOS_DB", str(tmp_path / "crm.db"))
    app_path = tmp_path / "application.json"
    app_path.write_text(json.dumps({
        "posting_text": POSTING,
        "analysis": ANALYSIS.model_dump(),
        "plan": PLAN.model_dump(),
        "slots": SLOTS.model_dump(),
    }, ensure_ascii=False), encoding="utf-8")

    assert main(["render", str(app_path), "--profile", str(EXAMPLE)]) == 0
    cv_pdf = tmp_path / "Lebenslauf_Mustermann_Beispiel_Firma_GmbH.pdf"
    letter_pdf = tmp_path / "Anschreiben_Mustermann_Beispiel_Firma_GmbH.pdf"
    assert cv_pdf.read_bytes()[:5] == b"%PDF-"
    assert letter_pdf.read_bytes()[:5] == b"%PDF-"

    # render auto-creates the CRM draft (idempotent on re-render)
    from app import crm

    conn = crm.connect()
    rows = crm.list_applications(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "draft"
    assert row["company"] == "Beispiel Firma GmbH"
    assert row["cv_path"] == str(cv_pdf)
    assert json.loads(row["plan_json"])["plan"] == PLAN.model_dump()
    conn.close()

    assert main(["render", str(app_path), "--profile", str(EXAMPLE)]) == 0
    conn = crm.connect()
    assert len(crm.list_applications(conn)) == 1  # upsert, no duplicate
    conn.close()

    assert main(["list"]) == 0
    assert "Beispiel Firma GmbH" in capsys.readouterr().out


@pytest.mark.skipif(TYPST is None, reason="typst CLI not on PATH")
def test_render_application_blocks_invalid_plan(tmp_path, profile):
    from app.cli import CliError

    bad_plan = PLAN.model_copy(deep=True)
    bad_plan.stations[0].bullets[0].bullet_id = "invented-99"
    with pytest.raises(CliError, match="invented-99"):
        render_application(profile, POSTING, ANALYSIS, bad_plan, SLOTS, tmp_path)
    assert not (tmp_path / "cv.pdf").exists()
