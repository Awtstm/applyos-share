"""Local CRM: applications + status audit trail in SQLite (ADR #4).

The database (default app/crm.db, override via APPLYOS_DB) holds personal
data — companies, statuses, notes — and is gitignored via the *.db pattern,
like profile.yaml. stdlib sqlite3, no ORM.

Every render records a draft row (idempotent upsert keyed on the
application.json path) with the full plan_json, so any past application can
be re-rendered from its stored plan. Status changes are validated against a
fixed transition graph and appended to the events table.
"""

import datetime
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / "crm.db"
SCHEMA_VERSION = 2

# migrations-lite: version N -> statements upgrading to N+1
_MIGRATIONS: dict[int, list[str]] = {
    1: ["ALTER TABLE applications ADD COLUMN match_score INTEGER"],
}

STATUSES = ("draft", "sent", "interview", "offer", "rejected", "withdrawn")
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent", "withdrawn"},
    "sent": {"interview", "rejected", "withdrawn"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": set(),
    "rejected": set(),
    "withdrawn": set(),
}

SETTABLE_FIELDS = ("channel", "posting_url")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  channel TEXT,
  posting_url TEXT,
  language TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  sent_at TEXT,
  app_path TEXT NOT NULL UNIQUE,
  cv_path TEXT,
  letter_path TEXT,
  plan_json TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  match_score INTEGER
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  from_status TEXT,
  to_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class CrmError(Exception):
    pass


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def db_path() -> Path:
    return Path(os.environ.get("APPLYOS_DB", DEFAULT_DB))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open (and on first use create) the CRM database.

    Migrations-lite: user_version gates the schema; an unknown version fails
    loudly instead of silently operating on a foreign layout.
    """
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    elif version < SCHEMA_VERSION:
        for step in range(version, SCHEMA_VERSION):
            for statement in _MIGRATIONS[step]:
                conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    elif version > SCHEMA_VERSION:
        raise CrmError(f"crm.db has schema version {version}, expected {SCHEMA_VERSION}")
    return conn


def _add_event(
    conn: sqlite3.Connection, app_id: int, from_status: str | None, to_status: str
) -> None:
    conn.execute(
        "INSERT INTO events (application_id, from_status, to_status, created_at)"
        " VALUES (?, ?, ?, ?)",
        (app_id, from_status, to_status, _now()),
    )


def record_draft(
    conn: sqlite3.Connection,
    *,
    company: str,
    role: str,
    language: str,
    app_path: str,
    plan_json: str,
    cv_path: str | None = None,
    letter_path: str | None = None,
    posting_url: str | None = None,
    match_score: int | None = None,
) -> tuple[int, bool]:
    """Idempotent draft upsert keyed on app_path.

    Returns (application id, created). A re-render of the same
    application.json refreshes plan_json and the PDF paths but never touches
    status, notes, or already-set posting_url/match_score (None keeps them).
    """
    row = conn.execute(
        "SELECT id FROM applications WHERE app_path = ?", (app_path,)
    ).fetchone()
    if row is not None:
        conn.execute(
            "UPDATE applications SET company = ?, role = ?, language = ?,"
            " plan_json = ?, cv_path = ?, letter_path = ?,"
            " posting_url = COALESCE(?, posting_url),"
            " match_score = COALESCE(?, match_score) WHERE id = ?",
            (company, role, language, plan_json, cv_path, letter_path,
             posting_url, match_score, row["id"]),
        )
        conn.commit()
        return row["id"], False

    cursor = conn.execute(
        "INSERT INTO applications (company, role, language, status, created_at,"
        " app_path, cv_path, letter_path, plan_json, posting_url, match_score)"
        " VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)",
        (company, role, language, _now(), app_path, cv_path, letter_path,
         plan_json, posting_url, match_score),
    )
    app_id = cursor.lastrowid
    _add_event(conn, app_id, None, "draft")
    conn.commit()
    return app_id, True


def get(conn: sqlite3.Connection, app_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if row is None:
        raise CrmError(f"no application with id {app_id}")
    return row


def list_applications(
    conn: sqlite3.Connection, status: str | None = None
) -> list[sqlite3.Row]:
    if status is not None:
        return conn.execute(
            "SELECT * FROM applications WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
    return conn.execute("SELECT * FROM applications ORDER BY id").fetchall()


def set_status(conn: sqlite3.Connection, app_id: int, to_status: str) -> None:
    """Validated status transition; appends to the audit trail."""
    if to_status not in STATUSES:
        raise CrmError(f"unknown status {to_status!r} (valid: {', '.join(STATUSES)})")
    current = get(conn, app_id)["status"]
    if to_status not in TRANSITIONS[current]:
        allowed = ", ".join(sorted(TRANSITIONS[current])) or "keine (terminal)"
        raise CrmError(
            f"transition {current} -> {to_status} not allowed (from {current}: {allowed})"
        )
    if to_status == "sent":
        conn.execute(
            "UPDATE applications SET status = ?, sent_at = ? WHERE id = ?",
            (to_status, _now(), app_id),
        )
    else:
        conn.execute(
            "UPDATE applications SET status = ? WHERE id = ?", (to_status, app_id)
        )
    _add_event(conn, app_id, current, to_status)
    conn.commit()


def add_note(conn: sqlite3.Connection, app_id: int, text: str) -> None:
    existing = get(conn, app_id)["notes"]
    entry = f"[{_now()}] {text}"
    notes = f"{existing}\n{entry}" if existing else entry
    conn.execute("UPDATE applications SET notes = ? WHERE id = ?", (notes, app_id))
    conn.commit()


def set_field(conn: sqlite3.Connection, app_id: int, field: str, value: str) -> None:
    """Set retroactive metadata; deliberately limited to a safe allowlist."""
    if field not in SETTABLE_FIELDS:
        raise CrmError(f"field {field!r} not settable (allowed: {', '.join(SETTABLE_FIELDS)})")
    get(conn, app_id)  # existence check
    conn.execute(f"UPDATE applications SET {field} = ? WHERE id = ?", (value, app_id))  # noqa: S608 — field is allowlisted
    conn.commit()


def delete_application(conn: sqlite3.Connection, app_id: int) -> None:
    """Permanently remove an application including its event history and
    notes. Rendered PDFs and the application.json on disk are NOT touched."""
    get(conn, app_id)  # existence check
    conn.execute("DELETE FROM events WHERE application_id = ?", (app_id,))
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()


def events_for(conn: sqlite3.Connection, app_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM events WHERE application_id = ? ORDER BY id", (app_id,)
    ).fetchall()
