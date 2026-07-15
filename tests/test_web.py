"""Web API tests: routes are thin wrappers — LLM steps are mocked with the
recorded snapshot fixtures, everything else (validator, CRM, render, profile
YAML) runs for real against temp paths."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.web.server as server
from app.ingest import read_source
from app.pipeline import PipelineResult
from app.profile import load_profile
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan
from app.validate import validate_application

TESTS = Path(__file__).resolve().parent
SNAPSHOTS = TESTS / "fixtures" / "snapshots"
POSTING_HTML = TESTS / "fixtures" / "postings" / "example-posting.html"
EXAMPLE_PROFILE = TESTS.parent / "profile" / "profile.example.yaml"
TYPST = shutil.which("typst")


def _snap(name: str) -> dict:
    return json.loads((SNAPSHOTS / f"example-posting.{name}.json").read_text("utf-8"))


@pytest.fixture
def posting() -> str:
    return read_source(str(POSTING_HTML))


@pytest.fixture
def client(tmp_path, monkeypatch, posting) -> TestClient:
    profile_copy = tmp_path / "profile.yaml"
    shutil.copy(EXAMPLE_PROFILE, profile_copy)
    monkeypatch.setenv("APPLYOS_DB", str(tmp_path / "crm.db"))
    monkeypatch.setenv("APPLYOS_PROFILE", str(profile_copy))
    monkeypatch.setenv("APPLYOS_OUTPUT", str(tmp_path / "out"))

    profile = load_profile(EXAMPLE_PROFILE)
    analysis = JobAnalysis.model_validate(_snap("analysis"))
    plan = TailoringPlan.model_validate(_snap("plan"))
    slots = LetterSlots.model_validate(_snap("slots"))
    report = validate_application(profile, analysis, plan, slots, posting)
    assert report.ok, report.errors
    result = PipelineResult(analysis, plan, slots, report)

    monkeypatch.setattr(server, "run_pipeline", lambda *a, **kw: result)
    return TestClient(server.app)


def _create(client, posting) -> dict:
    response = client.post("/api/applications", json={"text": posting})
    assert response.status_code == 200, response.text
    return response.json()


def test_index_and_meta(client):
    assert "<title>ApplyOS</title>" in client.get("/").text
    meta = client.get("/api/meta").json()
    assert meta["max_total_bullets"] == 10
    assert "draft" in meta["transitions"]
    assert meta["transitions"]["offer"] == []


def test_create_application_records_draft(client, posting):
    created = _create(client, posting)
    assert created["report"]["ok"]
    assert created["application"]["plan"]["stations"]

    rows = client.get("/api/applications").json()
    assert len(rows) == 1 and rows[0]["status"] == "draft"

    detail = client.get(f"/api/applications/{created['id']}").json()
    assert detail["application"]["slots"] == created["application"]["slots"]
    assert [e["to_status"] for e in detail["events"]] == ["draft"]


def test_edited_plan_revalidates_and_blocks_render(client, posting):
    created = _create(client, posting)
    app_id = created["id"]
    edited = created["application"]
    edited["plan"]["stations"][0]["bullets"][0]["bullet_id"] = "exco-99"

    response = client.put(f"/api/applications/{app_id}/plan", json=edited)
    assert response.status_code == 200
    report = response.json()["report"]
    assert not report["ok"]
    assert any("exco-99" in e for e in report["errors"])

    render = client.post(f"/api/applications/{app_id}/render")
    assert render.status_code == 409
    assert any("exco-99" in e for e in render.json()["detail"]["errors"])


def test_schema_broken_edit_rejected(client, posting):
    created = _create(client, posting)
    edited = created["application"]
    edited["plan"]["invented_field"] = True
    response = client.put(f"/api/applications/{created['id']}/plan", json=edited)
    assert response.status_code == 422


@pytest.mark.skipif(TYPST is None, reason="typst CLI not on PATH")
def test_render_and_pdf_delivery(client, posting):
    created = _create(client, posting)
    app_id = created["id"]
    response = client.post(f"/api/applications/{app_id}/render")
    assert response.status_code == 200, response.text
    assert Path(response.json()["cv_path"]).exists()

    pdf = client.get(f"/api/applications/{app_id}/pdf/letter")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"


def test_status_transitions_enforced(client, posting):
    created = _create(client, posting)
    app_id = created["id"]
    response = client.post(f"/api/applications/{app_id}/status", json={"to": "offer"})
    assert response.status_code == 409
    assert "not allowed" in response.json()["detail"]

    response = client.post(f"/api/applications/{app_id}/status", json={"to": "sent"})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["sent_at"]


def test_note_endpoint(client, posting):
    created = _create(client, posting)
    response = client.post(
        f"/api/applications/{created['id']}/note", json={"text": "Rückruf vereinbart"}
    )
    assert "Rückruf vereinbart" in response.json()["notes"]


def test_profile_yaml_validation_gate(client, tmp_path):
    original = client.get("/api/profile/yaml").json()["text"]
    assert "Max Mustermann" in original

    broken = original.replace("text_en:", "text_typo:")
    response = client.put("/api/profile/yaml", json={"text": broken})
    assert response.status_code == 422
    assert response.json()["detail"]["errors"]
    # file untouched after a rejected write
    assert client.get("/api/profile/yaml").json()["text"] == original

    response = client.put("/api/profile/yaml", json={"text": original + "\n# geprüft\n"})
    assert response.status_code == 200
    assert "# geprüft" in client.get("/api/profile/yaml").json()["text"]


def test_revise_endpoint_revalidates_and_persists(client, posting, monkeypatch):
    from app.schemas import LetterSlots, Revision

    created = _create(client, posting)
    app_id = created["id"]

    def fake_revise(profile, analysis, plan, slots, instruction, posting_text):
        assert "kürze" in instruction.lower()
        shorter = LetterSlots.model_validate({**slots.model_dump(), "fit_1": slots.fit_1[:100]})
        return Revision(plan=plan, slots=shorter, notes="Muttersprache nicht im Profil belegt.")

    monkeypatch.setattr(server, "revise_application", fake_revise)
    response = client.post(
        f"/api/applications/{app_id}/revise", json={"instruction": "Kürze Fit 1"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["report"]["ok"]
    assert data["notes"] == "Muttersprache nicht im Profil belegt."
    assert len(data["application"]["slots"]["fit_1"]) == 100
    # persisted: subsequent GET returns the revised slots
    detail = client.get(f"/api/applications/{app_id}").json()
    assert len(detail["application"]["slots"]["fit_1"]) == 100


def test_delete_endpoint(client, posting):
    created = _create(client, posting)
    app_id = created["id"]
    assert client.delete(f"/api/applications/{app_id}").json() == {"ok": True}
    assert client.get("/api/applications").json() == []
    assert client.delete(f"/api/applications/{app_id}").status_code == 409


def test_llm_failure_surfaces_as_readable_502(client, posting, monkeypatch):
    from app.llm import LLMError

    def broke(*args, **kwargs):
        raise LLMError("Anthropic API (400): Your credit balance is too low …")

    monkeypatch.setattr(server, "run_pipeline", broke)
    response = client.post("/api/applications", json={"text": posting})
    assert response.status_code == 502
    assert "credit balance" in response.json()["detail"]


def test_server_binds_localhost_only():
    assert server.HOST == "127.0.0.1"
