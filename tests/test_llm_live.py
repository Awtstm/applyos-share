"""Live pipeline tests against the Anthropic API (roadmap 2.3–2.5 fixtures).

Excluded from the default run (see pyproject addopts); execute with:

    uv run pytest -m llm

Runs the full analyze → plan → letter → validate chain for every posting
fixture in tests/fixtures/postings/ (*.txt / *.html — see the README there;
the real 2 DE + 2 EN postings are provided locally by the user).
"""

import os
from pathlib import Path

import pytest

from app.analyze import analyze_posting
from app.ingest import read_source
from app.letter import make_letter_slots
from app.profile import load_profile
from app.tailor import make_plan
from app.validate import validate_application

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "postings"
EXAMPLE_PROFILE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"

POSTINGS = sorted([*FIXTURES.glob("*.txt"), *FIXTURES.glob("*.html")])

def _api_key_configured() -> bool:
    """A real key, not the .env.example placeholder — live tests must skip
    cleanly on machines without a configured Anthropic account."""
    from app.config import load_dotenv

    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key.startswith("sk-ant-") and "..." not in key


pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(not _api_key_configured(), reason="no ANTHROPIC_API_KEY configured"),
]


REAL_PROFILE = Path(__file__).resolve().parent.parent / "profile" / "profile.yaml"
MCKINSEY = FIXTURES / "en-01-mckinsey-knowledge-analyst-energy.txt"
DRIVE = FIXTURES / "de-01-drive-consulting-associate.txt"


@pytest.mark.skipif(
    not (REAL_PROFILE.exists() and MCKINSEY.exists() and DRIVE.exists()),
    reason="needs real profile + both calibration fixtures (local only)",
)
def test_match_score_calibrates_honestly():
    """The match score is decision support: a role whose core requirement
    (oil & gas experience) is missing from the profile must score clearly
    below a role that fits."""
    from app.analyze import analyze_posting
    from app.match import evaluate_match

    profile = load_profile(REAL_PROFILE)

    def match_for(path):
        posting = read_source(str(path))
        analysis = analyze_posting(posting)
        return evaluate_match(profile, analysis, posting)

    mckinsey = match_for(MCKINSEY)
    drive = match_for(DRIVE)

    assert drive.score >= 70, (drive.score, drive.gaps)
    assert mckinsey.score <= 60, (mckinsey.score, mckinsey.gaps)
    assert drive.score - mckinsey.score >= 15
    # the missing core requirement must be named in the gaps
    gaps_text = " ".join(mckinsey.gaps).lower()
    assert any(term in gaps_text for term in ("oil", "gas", "energy", "öl", "energie"))
    assert 1 <= len(mckinsey.gaps) <= 3 and 2 <= len(drive.strengths) <= 4


@pytest.mark.parametrize("posting_path", POSTINGS, ids=lambda p: p.name)
def test_full_pipeline_produces_valid_application(posting_path):
    profile = load_profile(EXAMPLE_PROFILE)
    posting = read_source(str(posting_path))

    analysis = analyze_posting(posting)
    assert analysis.language in ("de", "en")

    plan = make_plan(profile, analysis, posting)
    slots = make_letter_slots(profile, analysis, plan, posting)

    report = validate_application(profile, analysis, plan, slots, posting)
    assert report.ok, report.errors
