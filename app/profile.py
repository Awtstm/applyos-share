"""Profile schema and loader.

profile/profile.yaml is the single source of truth for all CV/letter content
(see CLAUDE.md rule 2). These pydantic models define its schema;
profile/profile.example.yaml must always validate against them.

The tailoring pipeline may only reference IDs that exist here - the
Phase 2 validator uses bullet_ids() / skill_ids() / headline_ids().
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictModel(BaseModel):
    # extra="forbid" turns YAML typos into validation errors
    model_config = ConfigDict(extra="forbid")


class Bullet(_StrictModel):
    """One selectable content unit: stable ID, DE + EN variant, tags."""

    id: str = Field(min_length=1)
    text_de: str = Field(min_length=1)
    text_en: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    # rendered in the untailored default CV; the full pool stays
    # available for tailoring
    default: bool = False


class Basics(_StrictModel):
    name: str
    email: str
    phone: str
    location: str
    address: str | None = None  # street address for the letter sender block
    linkedin: str | None = None
    nationality: str | None = None
    birthdate: str | None = None


class Station(_StrictModel):
    id: str = Field(min_length=1)
    employer: str
    role_de: str
    role_en: str
    period: str
    location: str
    fixed: bool = False  # fixed: always rendered with default bullets
    bullets: list[Bullet] = Field(min_length=1)


class Education(_StrictModel):
    id: str = Field(min_length=1)
    institution: str
    degree_de: str
    degree_en: str
    period: str
    location: str
    details: list[Bullet] = Field(default_factory=list)


class Skill(_StrictModel):
    id: str = Field(min_length=1)
    label_de: str
    label_en: str
    tags: list[str] = Field(default_factory=list)


class Language(_StrictModel):
    label_de: str
    label_en: str


class LetterFixed(_StrictModel):
    sender_block: bool = True
    greeting_de: str
    greeting_de_unknown: str
    greeting_en: str
    greeting_en_unknown: str
    closing_de: str
    closing_en: str
    availability_de: str
    availability_en: str
    # reusable closing fragment: current residence + on-site willingness
    location_note_de: str
    location_note_en: str


class Profile(_StrictModel):
    basics: Basics
    headline_pool: list[Bullet] = Field(min_length=1)
    stations: list[Station] = Field(min_length=1)
    education: list[Education] = Field(default_factory=list)
    extracurricular: list[Bullet] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    letter_fixed: LetterFixed

    @model_validator(mode="after")
    def _ids_globally_unique(self) -> Self:
        seen: set[str] = set()
        for entity_id in self._all_ids():
            if entity_id in seen:
                raise ValueError(f"duplicate id in profile: {entity_id!r}")
            seen.add(entity_id)
        return self

    def _all_ids(self) -> Iterator[str]:
        for headline in self.headline_pool:
            yield headline.id
        for station in self.stations:
            yield station.id
            for bullet in station.bullets:
                yield bullet.id
        for education in self.education:
            yield education.id
            for detail in education.details:
                yield detail.id
        for extra in self.extracurricular:
            yield extra.id
        for skill in self.skills:
            yield skill.id

    def bullet_ids(self) -> set[str]:
        """IDs a tailoring plan may select (station bullets, education
        details, extracurricular entries)."""
        station_ids = {b.id for st in self.stations for b in st.bullets}
        detail_ids = {d.id for edu in self.education for d in edu.details}
        extra_ids = {e.id for e in self.extracurricular}
        return station_ids | detail_ids | extra_ids

    def skill_ids(self) -> set[str]:
        return {skill.id for skill in self.skills}

    def headline_ids(self) -> set[str]:
        return {headline.id for headline in self.headline_pool}


def load_profile(path: str | Path) -> Profile:
    """Load and validate a profile YAML file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Profile.model_validate(raw)
