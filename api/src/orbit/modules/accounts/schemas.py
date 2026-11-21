from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, field_validator

from orbit.modules.accounts.hobbies import MAX_HOBBIES, Hobby
from orbit.modules.accounts.models import MAX_CHILDHOOD_CITIES
from orbit.modules.accounts.roots import normalise_city, tidy

City = Annotated[str, AfterValidator(tidy), Field(min_length=1, max_length=120)]
SchoolName = Annotated[str, AfterValidator(tidy), Field(min_length=1, max_length=200)]


class Me(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None
    hobbies: list[Hobby]
    # False until sign-up (with the 18+ check) is done: there is no Orbit profile yet.
    onboarded: bool
    consented: bool


DisplayName = Annotated[str, AfterValidator(tidy), Field(min_length=1, max_length=40)]


def _unique(v: list[str]) -> list[str]:
    return list(dict.fromkeys(v))


Hobbies = Annotated[list[Hobby], AfterValidator(_unique), Field(max_length=MAX_HOBBIES)]


class SignUp(BaseModel):
    """Sign-up (task 2.6 + profile). Only the birth year is stored; the full date gives an
    exact 18+ check."""

    name: DisplayName
    date_of_birth: date
    hobbies: Hobbies = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    name: DisplayName | None = None
    hobbies: Hobbies | None = None


class School(BaseModel):
    name: SchoolName
    city: City


class Roots(BaseModel):
    """All optional. PUT replaces everything; send empty values to clear."""

    birth_city: City | None = None
    school: School | None = None
    childhood_cities: list[City] = Field(default_factory=list, max_length=MAX_CHILDHOOD_CITIES)

    @field_validator("birth_city", mode="before")
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("childhood_cities", mode="before")
    @classmethod
    def _drop_blank_and_duplicates(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        seen: set[str] = set()
        out = []
        for city in v:
            if not isinstance(city, str) or not city.strip():
                continue
            key = normalise_city(city)
            if key not in seen:
                seen.add(key)
                out.append(city)
        return out
