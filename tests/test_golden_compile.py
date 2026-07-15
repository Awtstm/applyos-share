"""Golden compile tests: both templates must compile against
profile.example.yaml-derived data, DE and EN, warning-free.

Warnings are treated as failures — a missing vendored font degrades
silently otherwise and PDFs stop being deterministic across machines.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.profile import load_profile
from app.render_data import cv_data, letter_data

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PROFILE = ROOT / "profile" / "profile.example.yaml"
TYPST = shutil.which("typst")

BUILDERS = {"cv": cv_data, "letter": letter_data}


@pytest.mark.parametrize("doc", ["cv", "letter"])
@pytest.mark.parametrize("lang", ["de", "en"])
def test_template_compiles_warning_free(tmp_path: Path, doc: str, lang: str):
    assert TYPST, "typst CLI not found on PATH (version pinned in .typst-version)"
    profile = load_profile(EXAMPLE_PROFILE)
    data = BUILDERS[doc](profile, lang)
    out = tmp_path / f"{doc}-{lang}.pdf"

    result = subprocess.run(
        [
            TYPST,
            "compile",
            "--font-path",
            str(ROOT / "assets" / "fonts"),
            "--ignore-system-fonts",
            "--input",
            "data=" + json.dumps(data, ensure_ascii=False),
            str(ROOT / "templates" / "typst" / f"{doc}.typ"),
            str(out),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"typst compile failed:\n{result.stderr}"
    assert result.stderr.strip() == "", f"typst emitted warnings:\n{result.stderr}"
    assert out.read_bytes()[:5] == b"%PDF-", "output is not a PDF"


def test_letter_rejects_wrong_fit_count(tmp_path: Path):
    """The template itself enforces the 2-3 fit paragraph contract."""
    assert TYPST, "typst CLI not found on PATH"
    profile = load_profile(EXAMPLE_PROFILE)
    data = letter_data(profile, "de")
    data["fits"] = data["fits"][:1]  # only one fit paragraph

    result = subprocess.run(
        [
            TYPST,
            "compile",
            "--font-path",
            str(ROOT / "assets" / "fonts"),
            "--ignore-system-fonts",
            "--input",
            "data=" + json.dumps(data, ensure_ascii=False),
            str(ROOT / "templates" / "typst" / "letter.typ"),
            str(tmp_path / "letter-invalid.pdf"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "2-3 fit paragraphs" in result.stderr
