"""FastAPI app: thin HTTP wrappers around app/pipeline.py and app/crm.py.

Routes contain no business logic — they parse the request, call the same
functions the CLI uses, and shape the response. The CLI keeps working in
parallel (shared crm.db, shared application.json artifacts).

Security model: the app serves personal data without authentication, so it
binds to 127.0.0.1 only (HOST below; `applyos serve` has no --host flag).

Handlers are sync `def` on purpose: uvicorn runs them in a threadpool, so a
30–60s pipeline call does not block the event loop.
"""

import json
import os
import tempfile
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from app import crm
from app.crm import CrmError
from app.ingest import IngestError, normalize_text, read_source
from app.llm import LLMError
from app.pipeline import (
    PipelineError,
    application_dict,
    load_application,
    parse_application,
    render_application,
    run_pipeline,
    save_application,
)
from app.profile import load_profile
from app.revise import revise_application
from app.schemas import (
    LETTER_BODY_MAX_CHARS,
    MAX_SLOT_CHARS,
    MAX_TOTAL_BULLETS,
)
from app.validate import validate_application

HOST = "127.0.0.1"  # personal data, no auth — localhost only, never 0.0.0.0
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="ApplyOS", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def profile_path() -> Path:
    return Path(os.environ.get("APPLYOS_PROFILE", "profile/profile.yaml"))


def output_root() -> Path:
    return Path(os.environ.get("APPLYOS_OUTPUT", "output"))


# ── request bodies ───────────────────────────────────────────────────────


class NewApplication(BaseModel):
    text: str | None = None
    url: str | None = None
    lang: str | None = None  # None/auto | de | en


class ApplicationUpdate(BaseModel):
    posting_text: str
    analysis: dict
    plan: dict
    slots: dict
    match: dict | None = None  # display-only, preserved across edits


class StatusChange(BaseModel):
    to: str


class ReviseIn(BaseModel):
    instruction: str


class NoteIn(BaseModel):
    text: str


class YamlIn(BaseModel):
    text: str


# ── error mapping ────────────────────────────────────────────────────────


@app.exception_handler(CrmError)
def _crm_error(_request, exc: CrmError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(IngestError)
def _ingest_error(_request, exc: IngestError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PipelineError)
def _pipeline_error(_request, exc: PipelineError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(LLMError)
def _llm_error(_request, exc: LLMError):
    """Upstream API failures (e.g. exhausted credits) as readable 502s."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})


# ── shell + meta ─────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta() -> dict:
    return {
        "max_total_bullets": MAX_TOTAL_BULLETS,
        "max_slot_chars": MAX_SLOT_CHARS,
        "letter_body_max": LETTER_BODY_MAX_CHARS,
        "statuses": list(crm.STATUSES),
        "transitions": {k: sorted(v) for k, v in crm.TRANSITIONS.items()},
    }


@app.get("/api/profile/pool")
def profile_pool() -> dict:
    profile = load_profile(profile_path())
    return profile.model_dump(
        include={"headline_pool", "stations", "extracurricular", "skills"}
    )


# ── applications ─────────────────────────────────────────────────────────


def _report_dict(report) -> dict:
    return {"ok": report.ok, "errors": report.errors}


def _row_dict(row) -> dict:
    return dict(row)


def _get_row(app_id: int):
    conn = crm.connect()
    try:
        return crm.get(conn, app_id)
    finally:
        conn.close()


@app.post("/api/applications")
def create_application(body: NewApplication) -> dict:
    profile = load_profile(profile_path())
    if body.url:
        posting = read_source(body.url)
    elif body.text and body.text.strip():
        posting = normalize_text(body.text)
    else:
        raise HTTPException(status_code=400, detail="text oder url erforderlich")

    lang = body.lang if body.lang in ("de", "en") else None
    result = run_pipeline(profile, posting, lang)
    app_path = save_application(
        output_root(), posting, result.analysis, result.plan, result.slots, result.match
    )

    payload = application_dict(
        posting, result.analysis, result.plan, result.slots, result.match
    )
    conn = crm.connect()
    try:
        app_id, _ = crm.record_draft(
            conn,
            company=result.analysis.company,
            role=result.analysis.role_title,
            language=result.analysis.language,
            app_path=str(app_path),
            plan_json=json.dumps(payload, ensure_ascii=False),
            posting_url=body.url,
            match_score=result.match.score if result.match else None,
        )
    finally:
        conn.close()

    return {
        "id": app_id,
        "application": payload,
        "report": _report_dict(result.report),
        "notes": result.auto_note,
    }


@app.get("/api/applications")
def list_applications(status: str | None = None) -> list[dict]:
    conn = crm.connect()
    try:
        return [_row_dict(row) for row in crm.list_applications(conn, status)]
    finally:
        conn.close()


@app.get("/api/applications/{app_id}")
def get_application(app_id: int) -> dict:
    conn = crm.connect()
    try:
        row = crm.get(conn, app_id)
        events = [_row_dict(e) for e in crm.events_for(conn, app_id)]
    finally:
        conn.close()
    data = _row_dict(row)
    data["application"] = json.loads(data.pop("plan_json"))
    data["events"] = events
    return data


@app.put("/api/applications/{app_id}/plan")
def update_plan(app_id: int, body: ApplicationUpdate) -> dict:
    row = _get_row(app_id)
    profile = load_profile(profile_path())
    try:
        posting, analysis, plan, slots, match = parse_application(body.model_dump())
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                               for e in exc.errors()]},
        ) from exc

    report = validate_application(profile, analysis, plan, slots, posting)

    # the edited artifact is saved even when invalid (it IS the review copy);
    # rendering stays blocked until the report is clean
    app_path = Path(row["app_path"])
    app_path.parent.mkdir(parents=True, exist_ok=True)
    payload = application_dict(posting, analysis, plan, slots, match)
    app_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    conn = crm.connect()
    try:
        crm.record_draft(
            conn,
            company=analysis.company,
            role=analysis.role_title,
            language=analysis.language,
            app_path=str(app_path),
            plan_json=json.dumps(payload, ensure_ascii=False),
            cv_path=row["cv_path"],
            letter_path=row["letter_path"],
            match_score=match.score if match else None,
        )
    finally:
        conn.close()
    return {"report": _report_dict(report)}


@app.post("/api/applications/{app_id}/revise")
def revise(app_id: int, body: ReviseIn) -> dict:
    """Instruction-driven rework — same fact bounds, same validator."""
    row = _get_row(app_id)
    profile = load_profile(profile_path())
    app_path = Path(row["app_path"])
    posting, analysis, plan, slots, match = load_application(app_path)

    revision = revise_application(
        profile, analysis, plan, slots, body.instruction, posting
    )
    report = validate_application(profile, analysis, revision.plan, revision.slots, posting)

    payload = application_dict(posting, analysis, revision.plan, revision.slots, match)
    app_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    conn = crm.connect()
    try:
        crm.record_draft(
            conn,
            company=analysis.company,
            role=analysis.role_title,
            language=analysis.language,
            app_path=str(app_path),
            plan_json=json.dumps(payload, ensure_ascii=False),
            cv_path=row["cv_path"],
            letter_path=row["letter_path"],
        )
    finally:
        conn.close()
    return {
        "application": payload,
        "report": _report_dict(report),
        "notes": revision.notes,
    }


@app.post("/api/applications/{app_id}/render")
def render(app_id: int) -> dict:
    row = _get_row(app_id)
    profile = load_profile(profile_path())
    app_path = Path(row["app_path"])
    posting, analysis, plan, slots, match = load_application(app_path)

    report = validate_application(profile, analysis, plan, slots, posting)
    if not report.ok:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Validierung fehlgeschlagen", "errors": report.errors},
        )
    # render_application re-validates (double floor), checks the letter page
    # count, and refreshes the draft
    cv_path, letter_path, _ = render_application(
        profile, posting, analysis, plan, slots, app_path.parent,
        posting_url=row["posting_url"], match=match,
    )
    return {"cv_path": str(cv_path), "letter_path": str(letter_path)}


@app.delete("/api/applications/{app_id}")
def delete_application(app_id: int) -> dict:
    """Remove the CRM row + events; PDFs and application.json stay on disk."""
    conn = crm.connect()
    try:
        crm.delete_application(conn, app_id)
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/applications/{app_id}/status")
def change_status(app_id: int, body: StatusChange) -> dict:
    conn = crm.connect()
    try:
        crm.set_status(conn, app_id, body.to)
        row = crm.get(conn, app_id)
    finally:
        conn.close()
    return _row_dict(row)


@app.post("/api/applications/{app_id}/note")
def add_note(app_id: int, body: NoteIn) -> dict:
    conn = crm.connect()
    try:
        crm.add_note(conn, app_id, body.text)
        row = crm.get(conn, app_id)
    finally:
        conn.close()
    return _row_dict(row)


@app.get("/api/applications/{app_id}/pdf/{doc}")
def get_pdf(app_id: int, doc: str) -> FileResponse:
    if doc not in ("cv", "letter"):
        raise HTTPException(status_code=404, detail="doc must be cv or letter")
    row = _get_row(app_id)
    path = row["cv_path"] if doc == "cv" else row["letter_path"]
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="noch nicht gerendert")
    return FileResponse(path, media_type="application/pdf")


# ── profile ──────────────────────────────────────────────────────────────


@app.get("/api/profile/yaml")
def get_profile_yaml() -> dict:
    return {"text": profile_path().read_text(encoding="utf-8")}


@app.put("/api/profile/yaml")
def put_profile_yaml(body: YamlIn) -> dict:
    # validate against a temp file first; the real file is only written
    # when the schema accepts the content
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(body.text)
        tmp = Path(handle.name)
    try:
        load_profile(tmp)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail={"errors": [f"YAML: {exc}"]}) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                               for e in exc.errors()]},
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)
    profile_path().write_text(body.text, encoding="utf-8")
    return {"ok": True}
