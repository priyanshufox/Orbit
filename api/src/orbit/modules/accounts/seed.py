"""Dev seed: 5 adult users who have consented, with overlapping roots so scoring has signal.

dev5 leaves roots blank, to exercise the "missing signal" path.
"""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.accounts.models import User, UserRoot, auth_user

DEV_USERS = [
    # email, name, birth_year
    ("dev1@orbit.test", "Aarav (dev)", 1998),
    ("dev2@orbit.test", "Diya (dev)", 2000),
    ("dev3@orbit.test", "Kabir (dev)", 1996),
    ("dev4@orbit.test", "Meera (dev)", 2003),
    ("dev5@orbit.test", "Rohan (dev)", 2001),
]

# email -> [(kind, slot, city, school)]
DEV_ROOTS: dict[str, list[tuple[str, int, str, str | None]]] = {
    "dev1@orbit.test": [
        ("birth", 0, "mumbai", None),
        ("school", 0, "noida", "green valley school"),
        ("childhood", 1, "mumbai", None),
        ("childhood", 2, "pune", None),
    ],
    "dev2@orbit.test": [
        ("birth", 0, "delhi", None),
        ("school", 0, "noida", "green valley school"),
        ("childhood", 1, "noida", None),
    ],
    "dev3@orbit.test": [
        ("birth", 0, "mumbai", None),
        ("childhood", 1, "pune", None),
        ("childhood", 2, "bengaluru", None),
    ],
    "dev4@orbit.test": [("birth", 0, "jaipur", None)],
}


def dev_user_id(email: str) -> UUID:
    """Stable id, so the dev login stub (task 2.2) and re-seeding agree."""
    return uuid5(NAMESPACE_URL, f"orbit-dev-user:{email}")


async def seed(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    users = [
        {
            "id": dev_user_id(email),
            "email": email,
            "name": name,
            "birth_year": year,
            "is_adult": True,
            "consented_at": now,
        }
        for email, name, year in DEV_USERS
    ]
    roots = [
        {"user_id": dev_user_id(email), "kind": k, "slot": s, "city": c, "school": sch}
        for email, rows in DEV_ROOTS.items()
        for k, s, c, sch in rows
    ]
    # Sign-in identities first (Better Auth's table); profiles share their ids.
    identities = [
        {"id": u["id"], "email": u["email"], "name": u["name"], "emailVerified": True}
        for u in users
    ]
    await session.execute(insert(auth_user).values(identities).on_conflict_do_nothing())
    res = await session.execute(insert(User).values(users).on_conflict_do_nothing())
    await session.execute(insert(UserRoot).values(roots).on_conflict_do_nothing())
    return res.rowcount
