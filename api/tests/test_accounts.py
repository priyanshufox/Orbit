"""Phase 2 API: token verification (2.4), profile creation (2.5), age gate (2.6), consent (2.7),
roots (2.8)."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx2 import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.accounts.models import User, UserRoot
from orbit.modules.accounts.roots import normalise_city, normalise_school, tidy
from orbit.modules.accounts.service import age_on
from tests.conftest import TokenFactory, make_identity

ADULT_DOB = "1999-05-20"


async def signed_in(
    db: AsyncSession, make_token: TokenFactory, name: str = "Diya"
) -> tuple[UUID, dict]:
    email = f"{uuid4().hex[:8]}@orbit.test"
    user_id = await make_identity(db, email, name)
    token = make_token(user_id, email, name=name, picture="https://img.test/a.png")
    return user_id, {"Authorization": f"Bearer {token}"}


async def onboarded(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> tuple[UUID, dict]:
    user_id, headers = await signed_in(db, make_token)
    res = await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": ADULT_DOB}, headers=headers
    )
    assert res.status_code == 200, res.text
    return user_id, headers


# --- 2.4 token verification ------------------------------------------------------------------


async def test_missing_token_is_401(client: AsyncClient) -> None:
    res = await client.get("/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "bad",
    [
        {"exp": 1},  # expired
        {"iss": "http://evil.test"},
        {"aud": "http://other.test"},
        {"sub": "not-a-uuid"},
    ],
    ids=["expired", "wrong-issuer", "wrong-audience", "bad-subject"],
)
async def test_bad_tokens_are_401(client: AsyncClient, make_token: TokenFactory, bad: dict) -> None:
    token = make_token(uuid4(), "x@orbit.test", **bad)
    res = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid_token"


async def test_token_signed_by_another_key_is_401(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    token = make_token(uuid4(), "x@orbit.test", key=Ed25519PrivateKey.generate())
    res = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# --- 2.5 / 2.6 profile and age gate ----------------------------------------------------------


async def test_me_before_age_gate(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    user_id, headers = await signed_in(db, make_token)
    res = await client.get("/me", headers=headers)
    assert res.status_code == 200
    assert res.json() | {"email": None} == {
        "id": str(user_id),
        "email": None,
        "name": "Diya",
        "avatar_url": "https://img.test/a.png",
        "hobbies": [],
        "onboarded": False,
        "consented": False,
    }


async def test_adult_gets_profile_and_only_birth_year_is_stored(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    user_id, headers = await signed_in(db, make_token)
    res = await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": ADULT_DOB}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["onboarded"] is True

    profile = await db.get(User, user_id)
    assert profile is not None
    assert (profile.birth_year, profile.is_adult, profile.name) == (1999, True, "Diya")

    again = await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": ADULT_DOB}, headers=headers
    )
    assert again.status_code == 200  # idempotent


async def test_under_18_leaves_nothing_behind(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    user_id, headers = await signed_in(db, make_token)
    seventeen = date.today().replace(year=date.today().year - 17).isoformat()

    res = await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": seventeen}, headers=headers
    )

    assert res.status_code == 403
    assert res.json()["detail"] == "under_18"
    assert await db.get(User, user_id) is None
    identity_rows = await db.scalar(
        text('select count(*) from auth."user" where id = :u'), {"u": user_id}
    )
    assert identity_rows == 0


async def test_impossible_birth_date_rejected(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    _, headers = await signed_in(db, make_token)
    res = await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": "2999-01-01"}, headers=headers
    )
    assert res.status_code == 422


@pytest.mark.parametrize(
    ("dob", "today", "age"),
    [
        (date(2008, 11, 13), date(2026, 11, 13), 18),  # birthday today
        (date(2008, 11, 14), date(2026, 11, 13), 17),  # birthday tomorrow
        (date(2008, 2, 29), date(2026, 2, 28), 17),
        (date(2008, 2, 29), date(2026, 3, 1), 18),
    ],
)
def test_age_on(dob: date, today: date, age: int) -> None:
    assert age_on(dob, today) == age


# --- 2.7 consent -----------------------------------------------------------------------------


async def test_consent_requires_profile_then_sticks(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    _, headers = await signed_in(db, make_token)
    early = await client.post("/me/consent", headers=headers)
    assert early.status_code == 403
    assert early.json()["detail"] == "onboarding_required"

    await client.post(
        "/me/profile", json={"name": "Diya", "date_of_birth": ADULT_DOB}, headers=headers
    )
    res = await client.post("/me/consent", headers=headers)
    assert res.status_code == 200
    assert res.json()["consented"] is True
    assert (await client.get("/me", headers=headers)).json()["consented"] is True


# --- 2.8 roots -------------------------------------------------------------------------------


async def test_roots_round_trip_and_replace(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    user_id, headers = await onboarded(client, db, make_token)
    assert (await client.get("/me/roots", headers=headers)).json() == {
        "birth_city": None,
        "school": None,
        "childhood_cities": [],
    }

    body = {
        "birth_city": "  Bombay ",
        "school": {"name": "Green  Valley School", "city": "Noida"},
        "childhood_cities": ["Pune", "", "pune.", "Bengaluru"],
    }
    res = await client.put("/me/roots", json=body, headers=headers)
    assert res.status_code == 200
    assert res.json() == {
        "birth_city": "Bombay",
        "school": {"name": "Green Valley School", "city": "Noida"},
        "childhood_cities": ["Pune", "Bengaluru"],  # blank and duplicate dropped
    }

    cleared = await client.put("/me/roots", json={}, headers=headers)
    assert cleared.json()["childhood_cities"] == []
    remaining = await db.scalar(
        select(func.count()).select_from(UserRoot).where(UserRoot.user_id == user_id)
    )
    assert remaining == 0


async def test_too_many_childhood_cities_rejected(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    _, headers = await onboarded(client, db, make_token)
    body = {"childhood_cities": ["A", "B", "C", "D"]}
    assert (await client.put("/me/roots", json=body, headers=headers)).status_code == 422


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bombay", "mumbai"),
        (" mumbai ", "mumbai"),
        ("Mumbai.", "mumbai"),
        ("Bangalore", "bengaluru"),
        ("New  Delhi", "delhi"),
        ("São Paulo", "sao paulo"),
    ],
)
def test_normalise_city(raw: str, expected: str) -> None:
    assert normalise_city(raw) == expected


def test_normalise_school_and_tidy() -> None:
    assert normalise_school("D.P.S.  Noida") == "d p s noida"
    assert tidy("  Green   Valley ") == "Green Valley"


# --- Sign-up profile: name and hobbies -----------------------------------------------------


async def test_sign_up_stores_name_and_hobbies_and_can_edit(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    user_id, headers = await signed_in(db, make_token, name="")
    body = {
        "name": "  Diya  Rao ",
        "date_of_birth": ADULT_DOB,
        "hobbies": ["Music", "Cricket", "Music"],
    }
    res = await client.post("/me/profile", json=body, headers=headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Diya Rao"
    assert res.json()["hobbies"] == ["Music", "Cricket"]  # duplicates dropped, order kept

    edited = await client.patch("/me", json={"hobbies": ["Travel"]}, headers=headers)
    assert edited.json()["hobbies"] == ["Travel"]
    assert edited.json()["name"] == "Diya Rao"
    assert (await db.get(User, user_id)).hobbies == ["Travel"]


@pytest.mark.parametrize(
    "bad",
    [
        {"hobbies": ["Skydiving"]},  # not on the list
        {"hobbies": ["Music", "Cricket", "Travel", "Art", "Tech", "Food", "Anime"]},  # 7 > 6
        {"name": "   "},
    ],
)
async def test_sign_up_validation(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory, bad: dict
) -> None:
    _, headers = await signed_in(db, make_token)
    body = {"name": "Diya", "date_of_birth": ADULT_DOB, **bad}
    assert (await client.post("/me/profile", json=body, headers=headers)).status_code == 422
