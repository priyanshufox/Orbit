"""Accounts: profile creation behind the age gate, consent, and roots."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.auth import Identity
from orbit.modules.accounts.models import User, UserRoot, auth_user
from orbit.modules.accounts.roots import normalise_city, normalise_school
from orbit.modules.accounts.schemas import Me, Roots, School

ADULT_AGE = 18
MAX_AGE = 120


class Under18Error(Exception):
    """The identity was deleted; nothing about this person is kept."""


class InvalidBirthDateError(Exception):
    pass


def age_on(date_of_birth: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def display_name(identity: Identity) -> str:
    return (identity.name or "").strip() or identity.email.split("@")[0]


def to_me(identity: Identity, profile: User | None) -> Me:
    return Me(
        id=identity.user_id,
        email=profile.email if profile else identity.email,
        name=profile.name if profile else display_name(identity),
        avatar_url=profile.avatar_url if profile else identity.picture,
        hobbies=list(profile.hobbies) if profile else [],
        onboarded=profile is not None,
        consented=bool(profile and profile.consented_at),
    )


async def get_profile(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def sign_up(
    session: AsyncSession,
    identity: Identity,
    date_of_birth: date,
    *,
    name: str | None = None,
    hobbies: list[str] | None = None,
    today: date | None = None,
) -> User:
    """Create the Orbit profile for an adult. For a minor, delete the sign-in identity instead
    (sessions and linked accounts cascade) and store nothing, per the DPDP-driven 18+ policy."""
    today = today or datetime.now(UTC).date()
    age = age_on(date_of_birth, today)
    if age < 0 or age > MAX_AGE:
        raise InvalidBirthDateError
    if age < ADULT_AGE:
        await session.execute(delete(auth_user).where(auth_user.c.id == identity.user_id))
        await session.commit()
        raise Under18Error

    existing = await get_profile(session, identity.user_id)
    if existing:
        return existing
    profile = User(
        id=identity.user_id,
        email=identity.email,
        name=(name or display_name(identity))[:80],
        hobbies=list(hobbies or []),
        avatar_url=identity.picture,
        birth_year=date_of_birth.year,
        is_adult=True,
    )
    session.add(profile)
    await session.commit()
    return profile


async def update_profile(
    session: AsyncSession, profile: User, *, name: str | None, hobbies: list[str] | None
) -> User:
    if name is not None:
        profile.name = name
    if hobbies is not None:
        profile.hobbies = list(hobbies)
    await session.commit()
    return profile


async def hobbies_for(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, frozenset[str]]:
    return {
        u.id: frozenset(u.hobbies or [])
        for u in (await public_profiles(session, user_ids)).values()
    }


async def give_consent(session: AsyncSession, profile: User) -> User:
    if profile.consented_at is None:
        profile.consented_at = datetime.now(UTC)
        await session.commit()
    return profile


async def get_roots(session: AsyncSession, user_id: UUID) -> Roots:
    rows = (
        await session.scalars(
            select(UserRoot).where(UserRoot.user_id == user_id).order_by(UserRoot.slot)
        )
    ).all()
    roots = Roots()
    for row in rows:
        if row.kind == "birth":
            roots.birth_city = row.city
        elif row.kind == "school" and row.school:
            roots.school = School(name=row.school, city=row.city)
        elif row.kind == "childhood":
            roots.childhood_cities.append(row.city)
    return roots


async def replace_roots(session: AsyncSession, user_id: UUID, roots: Roots) -> Roots:
    await session.execute(delete(UserRoot).where(UserRoot.user_id == user_id))
    rows = []
    if roots.birth_city:
        rows.append(UserRoot(user_id=user_id, kind="birth", slot=0, city=roots.birth_city))
    if roots.school:
        rows.append(
            UserRoot(
                user_id=user_id,
                kind="school",
                slot=0,
                city=roots.school.city,
                school=roots.school.name,
            )
        )
    rows += [
        UserRoot(user_id=user_id, kind="childhood", slot=i, city=city)
        for i, city in enumerate(roots.childhood_cities, start=1)
    ]
    session.add_all(rows)
    await session.commit()
    return await get_roots(session, user_id)


async def public_profiles(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, User]:
    """Name and avatar for other modules' views. Never exposes roots or birth year."""
    if not user_ids:
        return {}
    rows = (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
    return {u.id: u for u in rows}


@dataclass(frozen=True)
class NormalisedRoots:
    """Roots in matching form, for scoring. Never shown to anyone."""

    birth_city: str | None
    school: tuple[str, str] | None
    childhood: frozenset[str]


async def normalised_roots(
    session: AsyncSession, user_ids: list[UUID]
) -> dict[UUID, NormalisedRoots]:
    out: dict[UUID, NormalisedRoots] = {}
    for user_id in user_ids:
        r = await get_roots(session, user_id)
        out[user_id] = NormalisedRoots(
            birth_city=normalise_city(r.birth_city) if r.birth_city else None,
            school=(normalise_school(r.school.name), normalise_city(r.school.city))
            if r.school
            else None,
            childhood=frozenset(normalise_city(c) for c in r.childhood_cities),
        )
    return out


async def delete_identity(session: AsyncSession, user_id: UUID) -> None:
    """Delete the sign-in identity; the profile, roots, snapshots, sessions and every room
    membership (with its answers, reactions, follows and scores) cascade."""
    await session.execute(delete(auth_user).where(auth_user.c.id == user_id))
    await session.commit()
