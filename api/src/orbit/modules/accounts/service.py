"""Accounts: profile creation behind the age gate, consent, and roots."""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.auth import Identity
from orbit.modules.accounts.models import User, UserRoot, auth_user
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
        onboarded=profile is not None,
        consented=bool(profile and profile.consented_at),
    )


async def get_profile(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def pass_age_gate(
    session: AsyncSession, identity: Identity, date_of_birth: date, *, today: date | None = None
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
        name=display_name(identity)[:80],
        avatar_url=identity.picture,
        birth_year=date_of_birth.year,
        is_adult=True,
    )
    session.add(profile)
    await session.commit()
    return profile


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
