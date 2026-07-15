"""Schema tests: profile.example.yaml is the authoritative schema reference
and must always validate; structural violations must fail loudly."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.profile import Profile, load_profile

EXAMPLE = Path(__file__).resolve().parent.parent / "profile" / "profile.example.yaml"


def example_data() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_example_profile_validates():
    profile = load_profile(EXAMPLE)
    assert profile.basics.name == "Max Mustermann"
    assert profile.stations[0].bullets[0].id == "exco-01"


def test_id_helpers_cover_all_pools():
    profile = load_profile(EXAMPLE)
    assert profile.bullet_ids() == {"exco-01", "exco-02", "edu-01-a", "ec-01"}
    assert profile.skill_ids() == {"sk-01", "sk-02"}
    assert profile.headline_ids() == {"hl-01"}


def test_duplicate_ids_rejected():
    data = example_data()
    data["skills"][1]["id"] = data["stations"][0]["bullets"][0]["id"]
    with pytest.raises(ValidationError, match="duplicate id"):
        Profile.model_validate(data)


def test_unknown_keys_rejected():
    data = example_data()
    data["stations"][0]["rolle"] = "typo for role_de"
    with pytest.raises(ValidationError):
        Profile.model_validate(data)


def test_bullet_requires_both_languages():
    data = example_data()
    del data["stations"][0]["bullets"][0]["text_en"]
    with pytest.raises(ValidationError):
        Profile.model_validate(data)


def test_station_requires_at_least_one_bullet():
    data = example_data()
    data["stations"][0]["bullets"] = []
    with pytest.raises(ValidationError):
        Profile.model_validate(data)
