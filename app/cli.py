"""applyos CLI: presentation layer over app/pipeline.py and app/crm.py.

    applyos tailor <url|file|->   run ingest → analyze → plan → letter →
                                  validate; print everything for review and
                                  save an editable application.json
    applyos render <application.json>
                                  re-validate, render both PDFs, and record
                                  (or refresh) the CRM draft row
    applyos list | sent | status | note | set | history
                                  local CRM: track every application from
                                  draft to offer/rejected/withdrawn
    applyos serve [--port]        local web UI (binds 127.0.0.1 only)

Human review before render (CLAUDE.md rule 3): `tailor` never renders on its
own — it stops at the printed plan + application.json. Rendering happens via
the separate `render` command (after optional hand-edits) or via
`tailor --render`, which asks for confirmation first. A failed validation
always blocks rendering (enforced in app/pipeline.py).
"""

import argparse
import json
import sys
from pathlib import Path

from app import crm
from app.crm import CrmError
from app.ingest import IngestError, read_source
from app.llm import LLMError
from app.pipeline import (
    PipelineError as CliError,  # noqa: N814 — historic name, tests rely on it
)
from app.pipeline import (
    application_dict,
    load_application,
    render_application,
    run_pipeline,
    save_application,
)
from app.profile import Profile, load_profile
from app.revise import revise_application
from app.schemas import JobAnalysis, LetterSlots, TailoringPlan
from app.validate import ValidationReport, validate_application

# ── review printout ──────────────────────────────────────────────────────


def print_review(
    profile: Profile,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    report: ValidationReport,
) -> None:
    print("== Analyse ==")
    print(f"  Firma:    {analysis.company}")
    print(f"  Rolle:    {analysis.role_title}  ({analysis.seniority})")
    print(f"  Sprache:  {analysis.language}")
    print(f"  Kontakt:  {analysis.contact_person or '—'}")
    print(f"  Anforderungen: {', '.join(analysis.top_requirements)}")
    if analysis.notes:
        print(f"  Notizen:  {analysis.notes}")

    lang = analysis.language
    stations_by_id = {station.id: station for station in profile.stations}
    headline = next((h for h in profile.headline_pool if h.id == plan.headline_id), None)
    print("\n== CV-Plan ==")
    if headline:
        print(f"  Headline [{plan.headline_id}]: "
              f"{headline.text_de if lang == 'de' else headline.text_en}")
    for station_plan in plan.stations:
        station = stations_by_id.get(station_plan.station_id)
        label = station.employer if station else station_plan.station_id
        print(f"  {label}:")
        pool = {b.id: b for b in station.bullets} if station else {}
        for choice in station_plan.bullets:
            bullet = pool.get(choice.bullet_id)
            if choice.rephrased_text:
                text, marker = choice.rephrased_text, "✎"
            elif bullet:
                text, marker = (bullet.text_de if lang == "de" else bullet.text_en), "•"
            else:
                text, marker = "(unbekannte ID)", "?"
            print(f"    {marker} [{choice.bullet_id}] {text}")
    print(f"  Engagement: {', '.join(plan.extracurricular_ids) or '—'}")
    print(f"  Skills: {', '.join(plan.skills_order)}")
    print(f"  Standort-Baustein im Anschreiben: "
          f"{'ja' if plan.flags.mention_location_note else 'nein'}")

    print("\n== Anschreiben ==")
    for name, text in [("hook", slots.hook), ("fit_1", slots.fit_1), ("fit_2", slots.fit_2),
                       ("fit_3", slots.fit_3), ("closing", slots.closing_variant)]:
        if text:
            print(f"  {name}: {text}")

    print()
    if report.ok:
        print("✓ Validierung bestanden.")
    else:
        print("✗ Validierung fehlgeschlagen:")
        for error in report.errors:
            print(f"  - {error}")


# ── pipeline commands ────────────────────────────────────────────────────


def cmd_tailor(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    posting = read_source(args.source)
    lang = None if args.lang == "auto" else args.lang

    result = run_pipeline(profile, posting, lang)
    if result.auto_note:
        print(f"⚠ {result.auto_note}\n")
    if result.match:
        print(f"== Profil-Match: {result.match.score}/100 ==")
        for strength in result.match.strengths:
            print(f"  + {strength}")
        for gap in result.match.gaps:
            print(f"  - {gap}")
        print()
    print_review(profile, result.analysis, result.plan, result.slots, result.report)

    app_path = save_application(
        Path(args.out), posting, result.analysis, result.plan, result.slots, result.match
    )
    print(f"\nGespeichert: {app_path}")
    print(f"Review/Edit, dann: applyos render {app_path}")

    if not result.report.ok:
        return 1
    if args.render:
        answer = input("Plan ok — jetzt rendern? [y/N] ").strip().lower()
        if answer == "y":
            url = args.source if args.source.startswith(("http://", "https://")) else None
            cv_path, letter_path, _ = render_application(
                profile, posting, result.analysis, result.plan, result.slots,
                app_path.parent, posting_url=url, match=result.match,
            )
            print(f"OK: {cv_path}\nOK: {letter_path}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    app_path = Path(args.application)
    posting, analysis, plan, slots, match = load_application(app_path)
    cv_path, letter_path, _ = render_application(
        profile, posting, analysis, plan, slots, app_path.parent, match=match
    )
    print(f"OK: {cv_path}\nOK: {letter_path}")
    return 0


def cmd_revise(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    app_path = Path(args.application)
    posting, analysis, plan, slots, match = load_application(app_path)

    revision = revise_application(profile, analysis, plan, slots, args.instruction, posting)
    report = validate_application(profile, analysis, revision.plan, revision.slots, posting)
    print_review(profile, analysis, revision.plan, revision.slots, report)
    if revision.notes:
        print(f"\nHinweis der Überarbeitung: {revision.notes}")

    app_path.write_text(
        json.dumps(
            application_dict(posting, analysis, revision.plan, revision.slots, match),
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nGespeichert: {app_path}")
    print(f"Review/Edit, dann: applyos render {app_path}")
    return 0 if report.ok else 1


# ── CRM commands ─────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    conn = crm.connect()
    try:
        rows = crm.list_applications(conn, args.status)
    finally:
        conn.close()
    if not rows:
        print("Keine Bewerbungen" + (f" mit Status {args.status!r}" if args.status else "") + ".")
        return 0
    print(f"{'ID':>3}  {'Status':<10} {'Firma':<28} {'Rolle':<28} "
          f"{'Match':<5} {'erstellt':<10} gesendet")
    for row in rows:
        sent = (row["sent_at"] or "—")[:10]
        score = str(row["match_score"]) if row["match_score"] is not None else "—"
        print(
            f"{row['id']:>3}  {row['status']:<10} {row['company'][:28]:<28} "
            f"{row['role'][:28]:<28} {score:<5} {row['created_at'][:10]:<10} {sent}"
        )
    return 0


def _change_status(app_id: int, to_status: str) -> int:
    conn = crm.connect()
    try:
        crm.set_status(conn, app_id, to_status)
        row = crm.get(conn, app_id)
    finally:
        conn.close()
    print(f"#{app_id} {row['company']} — Status: {to_status}")
    return 0


def cmd_sent(args: argparse.Namespace) -> int:
    return _change_status(args.id, "sent")


def cmd_status(args: argparse.Namespace) -> int:
    return _change_status(args.id, args.to)


def cmd_note(args: argparse.Namespace) -> int:
    conn = crm.connect()
    try:
        crm.add_note(conn, args.id, args.text)
    finally:
        conn.close()
    print(f"Notiz zu #{args.id} gespeichert.")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    conn = crm.connect()
    try:
        crm.set_field(conn, args.id, args.field, args.value)
    finally:
        conn.close()
    print(f"#{args.id}: {args.field} = {args.value}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    conn = crm.connect()
    try:
        row = crm.get(conn, args.id)
        if not args.yes:
            answer = input(
                f"Bewerbung #{args.id} ({row['company']} — {row['role']}) inkl. "
                "Status-Historie und Notizen endgültig aus dem CRM löschen? "
                "PDFs und application.json bleiben liegen. [y/N] "
            ).strip().lower()
            if answer != "y":
                print("Abgebrochen.")
                return 0
        crm.delete_application(conn, args.id)
    finally:
        conn.close()
    print(f"#{args.id} gelöscht (Dateien in output/ unangetastet).")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    conn = crm.connect()
    try:
        row = crm.get(conn, args.id)
        events = crm.events_for(conn, args.id)
    finally:
        conn.close()
    print(f"#{row['id']} {row['company']} — {row['role']}")
    for event in events:
        source = event["from_status"] or "·"
        print(f"  {event['created_at']}  {source} -> {event['to_status']}")
    if row["notes"]:
        print("Notizen:")
        for line in row["notes"].splitlines():
            print(f"  {line}")
    return 0


# ── web ──────────────────────────────────────────────────────────────────


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from app.web.server import HOST, app

    print(f"ApplyOS Web-UI: http://{HOST}:{args.port}")
    print("Nur lokal erreichbar (127.0.0.1), keine Authentifizierung — nicht exponieren.")
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="applyos", description="Tailoring pipeline + CRM")
    sub = parser.add_subparsers(dest="command", required=True)

    tailor = sub.add_parser("tailor", help="posting → reviewed plan (+ optional render)")
    tailor.add_argument("source", help="posting URL, file path, or '-' for stdin paste")
    tailor.add_argument("--lang", choices=["auto", "de", "en"], default="auto")
    tailor.add_argument("--profile", default="profile/profile.yaml")
    tailor.add_argument("--out", default="output")
    tailor.add_argument("--render", action="store_true",
                        help="ask for confirmation and render after a valid plan")
    tailor.set_defaults(func=cmd_tailor)

    render = sub.add_parser("render", help="render PDFs from a reviewed application.json")
    render.add_argument("application", help="path to application.json")
    render.add_argument("--profile", default="profile/profile.yaml")
    render.set_defaults(func=cmd_render)

    revise = sub.add_parser("revise", help="rework plan + letter per instruction (LLM)")
    revise.add_argument("application", help="path to application.json")
    revise.add_argument("instruction", help="e.g. 'Kürze Fit 1 und erwähne …'")
    revise.add_argument("--profile", default="profile/profile.yaml")
    revise.set_defaults(func=cmd_revise)

    list_cmd = sub.add_parser("list", help="list tracked applications")
    list_cmd.add_argument("--status", choices=crm.STATUSES, default=None)
    list_cmd.set_defaults(func=cmd_list)

    sent = sub.add_parser("sent", help="mark an application as sent")
    sent.add_argument("id", type=int)
    sent.set_defaults(func=cmd_sent)

    status = sub.add_parser("status", help="validated status transition")
    status.add_argument("id", type=int)
    status.add_argument("to", choices=[s for s in crm.STATUSES if s != "draft"])
    status.set_defaults(func=cmd_status)

    note = sub.add_parser("note", help="append a timestamped note")
    note.add_argument("id", type=int)
    note.add_argument("text")
    note.set_defaults(func=cmd_note)

    set_cmd = sub.add_parser("set", help="set metadata retroactively")
    set_cmd.add_argument("id", type=int)
    set_cmd.add_argument("field", choices=crm.SETTABLE_FIELDS)
    set_cmd.add_argument("value")
    set_cmd.set_defaults(func=cmd_set)

    history = sub.add_parser("history", help="show status events and notes")
    history.add_argument("id", type=int)
    history.set_defaults(func=cmd_history)

    delete = sub.add_parser("delete", help="remove an application from the CRM (files stay)")
    delete.add_argument("id", type=int)
    delete.add_argument("--yes", action="store_true", help="skip confirmation")
    delete.set_defaults(func=cmd_delete)

    serve = sub.add_parser("serve", help="local web UI (127.0.0.1 only)")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (CliError, CrmError, IngestError, LLMError) as exc:
        print(f"applyos: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
