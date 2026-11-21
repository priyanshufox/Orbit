"""Scores storage. The maths is in scoring.domain; the round pipeline (orbit.pipeline) feeds it."""

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.scoring.domain import PairScore
from orbit.modules.scoring.models import Score


def _dec(v: float | None) -> Decimal | None:
    return None if v is None else Decimal(str(round(v, 4)))


async def write_scores(session: AsyncSession, code: str, pairs: list[PairScore]) -> None:
    """Replace the room's scores (re-scoring is idempotent)."""
    await session.execute(delete(Score).where(Score.room_code == code))
    session.add_all(
        Score(
            room_code=code,
            user_a=p.user_a,
            user_b=p.user_b,
            answers=_dec(p.answers),
            reactions=_dec(p.reactions),
            roots=_dec(p.roots),
            social=_dec(p.social),
            total=_dec(p.total),
            reasons=[asdict(r) for r in p.reasons],
        )
        for p in pairs
    )
    await session.commit()


def _f(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


async def get_scores(session: AsyncSession, code: str) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(Score).where(Score.room_code == code))).all()
    return [
        {
            "a": r.user_a,
            "b": r.user_b,
            "total": float(r.total),
            "answers": _f(r.answers),
            "reactions": _f(r.reactions),
            "roots": _f(r.roots),
            "social": _f(r.social),
            "reasons": r.reasons,
        }
        for r in rows
    ]


async def has_scores(session: AsyncSession, code: str) -> bool:
    return (
        await session.scalar(select(Score.room_code).where(Score.room_code == code).limit(1))
    ) is not None
