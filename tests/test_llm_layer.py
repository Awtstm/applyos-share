"""Offline tests for the LLM layer: config resolution, prompt files, and the
profile-pool serialization. No API calls."""

from pathlib import Path

from app.config import DEFAULT_MODELS, load_dotenv, model_for
from app.llm import load_prompt
from app.profile import load_profile
from app.tailor import profile_pool_json

EXAMPLE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"


def test_model_for_defaults_and_override(monkeypatch):
    monkeypatch.delenv("APPLYOS_MODEL_PLAN", raising=False)
    assert model_for("plan") == DEFAULT_MODELS["plan"] == "claude-sonnet-5"
    assert DEFAULT_MODELS["analyze"] == "claude-haiku-4-5"
    monkeypatch.setenv("APPLYOS_MODEL_PLAN", "claude-opus-4-8")
    assert model_for("plan") == "claude-opus-4-8"


def test_load_dotenv_respects_existing_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        '# comment\nANTHROPIC_API_KEY="sk-from-file"\nAPPLYOS_MODEL_ANALYZE=file-model\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    monkeypatch.delenv("APPLYOS_MODEL_ANALYZE", raising=False)
    load_dotenv(env)
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-from-env"  # env wins
    assert os.environ["APPLYOS_MODEL_ANALYZE"] == "file-model"  # file fills gap


def test_prompts_exist_and_state_the_contract():
    analyze = load_prompt("analyze")
    plan = load_prompt("plan")
    letter = load_prompt("letter")
    match = load_prompt("match")
    revise = load_prompt("revise")
    assert "contact_person" in analyze
    # match prompt must demand honest calibration with score anchors
    assert "nicht** das Ziel" in match and "30–49" in match
    # revise prompt must restate the fact bounds and the notes contract
    assert "Bullet-IDs aus dem Profil-Pool" in revise and "notes" in revise
    # the plan prompt must communicate ID-only selection and rephrase bounds
    assert "bullet_id" in plan and "kürzer" in plan
    # the letter prompt must communicate register rules and the fact base
    assert "Sie-Form" in letter and "Validator" in letter


def test_clamp_analysis_trims_overlong_lists():
    from app.analyze import clamp_analysis
    from app.schemas import MAX_KEYWORDS, JobAnalysis

    analysis = JobAnalysis.model_validate({
        "company": "X", "role_title": "Y", "language": "de", "contact_person": None,
        "top_requirements": [f"r{i}" for i in range(9)],
        "keywords": [f"k{i}" for i in range(20)],
        "seniority": "entry", "notes": None,
    })
    clamped = clamp_analysis(analysis)
    assert len(clamped.keywords) == MAX_KEYWORDS
    assert len(clamped.top_requirements) == 5
    assert clamped.keywords[0] == "k0"  # priority order preserved


def test_profile_pool_excludes_personal_frame():
    pool = profile_pool_json(load_profile(EXAMPLE))
    assert "headline_pool" in pool and "stations" in pool and "skills" in pool
    # basics/letter_fixed contain nothing selectable — keep them out
    assert "max@example.com" not in pool
    assert "letter_fixed" not in pool


def test_pool_system_block_carries_match_relevant_basics():
    from app.tailor import pool_system_block

    block = pool_system_block(load_profile(EXAMPLE))
    # location, nationality, languages, on-site willingness: first-order
    # match criteria (location must never be guessed from station cities)
    assert "Utrecht, NL" in block
    assert "German" in block  # nationality
    assert "Muttersprache" in block  # languages list
    assert "Standort" in block  # on-site willingness fragment
    # contact data has no business in any prompt
    assert "max@example.com" not in block
    assert "+49 170" not in block
