"""Record pipeline snapshots for the offline snapshot tests (roadmap 2.8).

Runs the live pipeline ONCE on the committed example posting + example
profile and freezes every stage contract as JSON under
tests/fixtures/snapshots/. Re-run deliberately after intentional contract
changes (schemas, validator, prompts, render data):

    uv run python -m tests.record_snapshots

Only committed example data is used — nothing personal ends up in git.
"""

import json
from pathlib import Path

from app.analyze import analyze_posting
from app.ingest import read_source
from app.letter import make_letter_slots
from app.profile import load_profile
from app.render_data import cv_data, letter_data
from app.tailor import make_plan
from app.validate import validate_application

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SNAPSHOTS = FIXTURES / "snapshots"
POSTING = FIXTURES / "postings" / "example-posting.html"
PROFILE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"


def _write(name: str, data: dict) -> None:
    path = SNAPSHOTS / f"example-posting.{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {path}")


def main() -> None:
    profile = load_profile(PROFILE)
    posting = read_source(str(POSTING))

    analysis = analyze_posting(posting)
    plan = make_plan(profile, analysis, posting)
    slots = make_letter_slots(profile, analysis, plan, posting)

    report = validate_application(profile, analysis, plan, slots, posting)
    if not report.ok:
        raise SystemExit("refusing to record an invalid run:\n" + "\n".join(report.errors))

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    _write("analysis", analysis.model_dump())
    _write("plan", plan.model_dump())
    _write("slots", slots.model_dump())
    lang = analysis.language
    _write("cv_data", cv_data(profile, lang, plan))
    _write(
        "letter_data",
        letter_data(
            profile, lang, analysis, slots,
            mention_location_note=plan.flags.mention_location_note,
        ),
    )


if __name__ == "__main__":
    main()
