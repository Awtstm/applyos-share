"""CRM tests: schema, idempotent draft upsert, validated status machine,
notes, settable fields, audit trail — all against a temp database."""

import pytest

from app.crm import (
    SCHEMA_VERSION,
    CrmError,
    add_note,
    connect,
    events_for,
    get,
    list_applications,
    record_draft,
    set_field,
    set_status,
)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "crm.db")
    yield connection
    connection.close()


def draft(conn, app_path="output/acme-analyst/application.json", **overrides):
    kwargs = {
        "company": "Acme GmbH",
        "role": "Analyst",
        "language": "de",
        "app_path": app_path,
        "plan_json": '{"plan": true}',
        "cv_path": "output/acme-analyst/cv.pdf",
        "letter_path": "output/acme-analyst/letter.pdf",
    }
    kwargs.update(overrides)
    return record_draft(conn, **kwargs)


def test_schema_created_with_version(conn):
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"applications", "events"} <= tables


def test_record_draft_creates_row_and_event(conn):
    app_id, created = draft(conn)
    assert created
    row = get(conn, app_id)
    assert row["status"] == "draft"
    assert row["plan_json"] == '{"plan": true}'
    events = events_for(conn, app_id)
    assert [(e["from_status"], e["to_status"]) for e in events] == [(None, "draft")]


def test_record_draft_upserts_on_same_app_path(conn):
    app_id, _ = draft(conn)
    set_field(conn, app_id, "posting_url", "https://example.com/job")
    same_id, created = draft(conn, plan_json='{"plan": 2}', posting_url=None)
    assert (same_id, created) == (app_id, False)
    row = get(conn, app_id)
    assert row["plan_json"] == '{"plan": 2}'
    assert row["posting_url"] == "https://example.com/job"  # None must not clobber
    assert len(list_applications(conn)) == 1


def test_valid_status_chain_with_audit_trail(conn):
    app_id, _ = draft(conn)
    for status in ("sent", "interview", "offer"):
        set_status(conn, app_id, status)
    row = get(conn, app_id)
    assert row["status"] == "offer"
    assert row["sent_at"] is not None
    chain = [(e["from_status"], e["to_status"]) for e in events_for(conn, app_id)]
    assert chain == [
        (None, "draft"), ("draft", "sent"), ("sent", "interview"), ("interview", "offer"),
    ]


@pytest.mark.parametrize(
    ("chain", "invalid"),
    [
        ([], "offer"),                      # draft -> offer skips sent/interview
        ([], "interview"),                  # draft -> interview skips sent
        (["sent"], "offer"),                # sent -> offer skips interview
        (["sent", "rejected"], "sent"),     # rejected is terminal
        (["withdrawn"], "sent"),            # withdrawn is terminal
    ],
)
def test_invalid_transitions_rejected(conn, chain, invalid):
    app_id, _ = draft(conn)
    for status in chain:
        set_status(conn, app_id, status)
    before = get(conn, app_id)["status"]
    with pytest.raises(CrmError, match="not allowed"):
        set_status(conn, app_id, invalid)
    assert get(conn, app_id)["status"] == before  # unchanged, no event written
    assert len(events_for(conn, app_id)) == 1 + len(chain)


def test_unknown_status_rejected(conn):
    app_id, _ = draft(conn)
    with pytest.raises(CrmError, match="unknown status"):
        set_status(conn, app_id, "ghosted")


def test_notes_append_with_timestamp(conn):
    app_id, _ = draft(conn)
    add_note(conn, app_id, "Rückfrage per Mail gestellt")
    add_note(conn, app_id, "Antwort erhalten")
    notes = get(conn, app_id)["notes"]
    assert "Rückfrage per Mail gestellt" in notes
    assert notes.count("\n") == 1 and notes.startswith("[")


def test_set_field_allowlist(conn):
    app_id, _ = draft(conn)
    set_field(conn, app_id, "channel", "LinkedIn")
    assert get(conn, app_id)["channel"] == "LinkedIn"
    with pytest.raises(CrmError, match="not settable"):
        set_field(conn, app_id, "status", "offer")


def test_list_filters_by_status(conn):
    first, _ = draft(conn)
    draft(conn, app_path="output/other/application.json", company="Other AG")
    set_status(conn, first, "sent")
    assert [r["id"] for r in list_applications(conn, status="sent")] == [first]
    assert len(list_applications(conn)) == 2


def test_missing_application_fails_loudly(conn):
    with pytest.raises(CrmError, match="no application"):
        get(conn, 99)


def test_delete_removes_row_and_events(conn):
    from app.crm import delete_application

    app_id, _ = draft(conn)
    set_status(conn, app_id, "sent")
    add_note(conn, app_id, "wird gelöscht")
    delete_application(conn, app_id)
    assert list_applications(conn) == []
    assert conn.execute(
        "SELECT COUNT(*) FROM events WHERE application_id = ?", (app_id,)
    ).fetchone()[0] == 0
    with pytest.raises(CrmError):
        delete_application(conn, app_id)


def test_match_score_upsert_keeps_existing_on_none(conn):
    app_id, _ = draft(conn, match_score=82)
    assert get(conn, app_id)["match_score"] == 82
    draft(conn, match_score=None)  # re-render without match must not clear it
    assert get(conn, app_id)["match_score"] == 82
    draft(conn, match_score=55)
    assert get(conn, app_id)["match_score"] == 55


def test_migration_v1_to_v2(tmp_path):
    import sqlite3

    # hand-build a v1 database (no match_score column)
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE applications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          company TEXT NOT NULL, role TEXT NOT NULL, channel TEXT,
          posting_url TEXT, language TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
          sent_at TEXT, app_path TEXT NOT NULL UNIQUE, cv_path TEXT,
          letter_path TEXT, plan_json TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          application_id INTEGER NOT NULL REFERENCES applications(id),
          from_status TEXT, to_status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO applications (company, role, language, created_at,
          app_path, plan_json) VALUES ('Alt AG', 'Rolle', 'de', '2026-07-09',
          'output/alt/application.json', '{}');
    """)
    old.execute("PRAGMA user_version = 1")
    old.commit()
    old.close()

    migrated = connect(path)
    assert migrated.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    row = migrated.execute("SELECT * FROM applications").fetchone()
    assert row["company"] == "Alt AG" and row["match_score"] is None
    migrated.close()
