"""Shared pipeline orchestration + rendering — the one implementation the
CLI and the web UI both call (no logic duplication, CLI keeps working).

run_pipeline() chains the three LLM steps and the validator; the
application.json helpers define the editable review artifact; and
render_application() compiles both PDFs and records/refreshes the CRM
draft. Presentation (argparse/FastAPI) lives in app/cli.py and
app/web/server.py.
"""

import datetime
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app import crm
from app.analyze import analyze_posting
from app.letter import make_letter_slots
from app.match import evaluate_match
from app.profile import Profile
from app.render_data import cv_data, letter_data
from app.revise import revise_application
from app.schemas import (
    LETTER_BODY_MAX_CHARS,
    MAX_TOTAL_BULLETS,
    JobAnalysis,
    LetterSlots,
    ProfileMatch,
    TailoringPlan,
)
from app.tailor import make_plan
from app.validate import ValidationReport, validate_application

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "typst"
FONTS = ROOT / "assets" / "fonts"

_EN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class PipelineError(Exception):
    pass


@dataclass
class PipelineResult:
    analysis: JobAnalysis
    plan: TailoringPlan
    slots: LetterSlots
    report: ValidationReport
    match: ProfileMatch | None = None
    auto_note: str | None = None  # e.g. "automatisch gekürzt" — shown in review


def run_pipeline(
    profile: Profile, posting_text: str, lang: str | None = None
) -> PipelineResult:
    """The four LLM calls + validation; pure orchestration, no I/O.

    If the letter overruns its total body budget, ONE automatic revise pass
    shortens it (visible via auto_note); a second overrun surfaces as a
    normal validation error.
    """
    analysis = analyze_posting(posting_text, lang)
    match = evaluate_match(profile, analysis, posting_text)
    plan = make_plan(profile, analysis, posting_text)
    slots = make_letter_slots(profile, analysis, plan, posting_text)

    plan, slots, auto_note = _auto_fix_budgets(profile, analysis, plan, slots, posting_text)
    report = validate_application(profile, analysis, plan, slots, posting_text)
    return PipelineResult(analysis, plan, slots, report, match, auto_note)


def _total_bullets(plan: TailoringPlan) -> int:
    return sum(len(sp.bullets) for sp in plan.stations)


def _auto_fix_budgets(
    profile: Profile,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    posting_text: str,
) -> tuple[TailoringPlan, LetterSlots, str | None]:
    """One combined automatic revise pass when the bullet and/or letter
    budget is overrun; a persisting overrun becomes a validation error."""
    bullets_before = _total_bullets(plan)
    body_before = slots.body_chars()
    instructions = []
    if bullets_before > MAX_TOTAL_BULLETS:
        instructions.append(
            f"Reduziere die Bullet-Auswahl im Plan auf maximal {MAX_TOTAL_BULLETS} "
            f"Bullets insgesamt (aktuell {bullets_before}): wähle die für die "
            "Anforderungen entbehrlichsten Bullets ab; jede Station behält "
            "mindestens einen Bullet."
        )
    if body_before > LETTER_BODY_MAX_CHARS:
        instructions.append(
            f"Kürze das Anschreiben auf insgesamt deutlich unter "
            f"{LETTER_BODY_MAX_CHARS} Zeichen (aktuell {body_before}; Ziel ~1800). "
            "Erhalte die Kernaussagen und Belege; straffe Formulierungen, statt "
            "Inhalte zu streichen. fit_3 nur behalten, wenn er eine eigenständige "
            "zentrale Anforderung trägt."
        )
    if not instructions:
        return plan, slots, None

    revision = revise_application(
        profile, analysis, plan, slots, " ".join(instructions), posting_text
    )
    plan, slots = revision.plan, revision.slots
    notes = []
    if bullets_before > MAX_TOTAL_BULLETS:
        notes.append(f"Automatisch reduziert: {bullets_before} → {_total_bullets(plan)} Bullets.")
    if body_before > LETTER_BODY_MAX_CHARS:
        notes.append(
            f"Automatisch gekürzt: Anschreiben-Body war {body_before} Zeichen, "
            f"nach Kürzungs-Durchlauf {slots.body_chars()}."
        )
    if revision.notes:
        notes.append(revision.notes)
    return plan, slots, " ".join(notes)


# ── application.json (the editable review artifact) ─────────────────────


def application_dict(
    posting_text: str,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    match: ProfileMatch | None = None,
) -> dict:
    data = {
        "posting_text": posting_text,
        "analysis": analysis.model_dump(),
        "plan": plan.model_dump(),
        "slots": slots.model_dump(),
    }
    if match is not None:
        data["match"] = match.model_dump()
    return data


def parse_application(
    data: dict,
) -> tuple[str, JobAnalysis, TailoringPlan, LetterSlots, ProfileMatch | None]:
    match = data.get("match")
    return (
        data["posting_text"],
        JobAnalysis.model_validate(data["analysis"]),
        TailoringPlan.model_validate(data["plan"]),
        LetterSlots.model_validate(data["slots"]),
        ProfileMatch.model_validate(match) if match else None,
    )


def load_application(
    path: Path,
) -> tuple[str, JobAnalysis, TailoringPlan, LetterSlots, ProfileMatch | None]:
    return parse_application(json.loads(path.read_text(encoding="utf-8")))


def sanitize_name(text: str) -> str:
    """Readable file-system name: spaces → underscores, special characters
    removed, case preserved (no lowercase slug; umlauts stay)."""
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^\w-]", "", text)
    text = re.sub(r"_+-_+", "_", text)  # " - " separators; in-word hyphens stay
    return re.sub(r"_{2,}", "_", text).strip("_") or "Unbenannt"


def application_dir(out_root: Path, analysis: JobAnalysis) -> Path:
    return out_root / f"{sanitize_name(analysis.company)}_{sanitize_name(analysis.role_title)}"


def pdf_filenames(profile: Profile, analysis: JobAnalysis) -> tuple[str, str]:
    """Language-dependent PDF names, surname from the profile:
    DE Lebenslauf_/Anschreiben_, EN CV_/CoverLetter_<Nachname>_<Firma>.pdf."""
    surname = sanitize_name(profile.basics.name.split()[-1])
    company = sanitize_name(analysis.company)
    if analysis.language == "de":
        return f"Lebenslauf_{surname}_{company}.pdf", f"Anschreiben_{surname}_{company}.pdf"
    return f"CV_{surname}_{company}.pdf", f"CoverLetter_{surname}_{company}.pdf"


def save_application(
    out_root: Path,
    posting_text: str,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    match: ProfileMatch | None = None,
) -> Path:
    out_dir = application_dir(out_root, analysis)
    out_dir.mkdir(parents=True, exist_ok=True)
    app_path = out_dir / "application.json"
    app_path.write_text(
        json.dumps(
            application_dict(posting_text, analysis, plan, slots, match),
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return app_path


# ── rendering ────────────────────────────────────────────────────────────


def letter_date(lang: str, today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    if lang == "de":
        return f"{today.day:02d}.{today.month:02d}.{today.year}"
    return f"{today.day} {_EN_MONTHS[today.month - 1]} {today.year}"


def _typst() -> str:
    binary = shutil.which("typst") or "/opt/homebrew/bin/typst"
    if not Path(binary).exists():
        raise PipelineError("typst CLI not found (version pinned in .typst-version)")
    return binary


def _compile(template: str, data: dict, out_path: Path) -> None:
    result = subprocess.run(
        [
            _typst(), "compile",
            "--root", str(ROOT),
            "--font-path", str(FONTS),
            "--ignore-system-fonts",
            "--input", "data=" + json.dumps(data, ensure_ascii=False),
            str(TEMPLATES / template),
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PipelineError(f"typst compile failed for {template}:\n{result.stderr}")


def _page_count(pdf_path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(pdf_path).pages)


def render_application(
    profile: Profile,
    posting_text: str,
    analysis: JobAnalysis,
    plan: TailoringPlan,
    slots: LetterSlots,
    out_dir: Path,
    posting_url: str | None = None,
    match: ProfileMatch | None = None,
) -> tuple[Path, Path, int]:
    """Validate, render both PDFs, and record/refresh the CRM draft row.

    Returns (cv_path, letter_path, crm application id). Human review happens
    before this call (CLI review printout / web review view); a failed
    validation always blocks rendering, and a letter that overflows one page
    fails structurally even if the char budget let it through.
    """
    report = validate_application(profile, analysis, plan, slots, posting_text)
    if not report.ok:
        raise PipelineError(
            "Validierung fehlgeschlagen:\n" + "\n".join(f"- {e}" for e in report.errors)
        )
    lang = analysis.language
    out_dir.mkdir(parents=True, exist_ok=True)
    cv_name, letter_name = pdf_filenames(profile, analysis)
    cv_path = out_dir / cv_name
    letter_path = out_dir / letter_name
    _compile("cv.typ", cv_data(profile, lang, plan), cv_path)
    _compile(
        "letter.typ",
        letter_data(
            profile, lang, analysis, slots,
            mention_location_note=plan.flags.mention_location_note,
            date=letter_date(lang),
        ),
        letter_path,
    )
    letter_pages = _page_count(letter_path)
    if letter_pages > 1:
        raise PipelineError(
            f"Anschreiben ist {letter_pages} Seiten lang (max 1) — Body kürzen "
            f"(aktuell {slots.body_chars()} Zeichen)"
        )

    conn = crm.connect()
    try:
        app_id, created = crm.record_draft(
            conn,
            company=analysis.company,
            role=analysis.role_title,
            language=lang,
            app_path=str(out_dir / "application.json"),
            plan_json=json.dumps(
                application_dict(posting_text, analysis, plan, slots, match),
                ensure_ascii=False,
            ),
            cv_path=str(cv_path),
            letter_path=str(letter_path),
            posting_url=posting_url,
            match_score=match.score if match else None,
        )
    finally:
        conn.close()
    print(f"CRM: Bewerbung #{app_id} {'erfasst' if created else 'aktualisiert'} (draft)")
    return cv_path, letter_path, app_id
