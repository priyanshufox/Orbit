"""Game: the deck, answers, reactions and likes/follows of a round."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.content import service as content
from orbit.modules.game import answers as answer_rules
from orbit.modules.game.deck import ContentCard as DeckContent
from orbit.modules.game.deck import build_deck, deck_ids
from orbit.modules.game.models import Answer, Question, Reaction, Social
from orbit.modules.game.schemas import ContentCard, DeckView, QuestionCard


class NotInDeckError(Exception):
    pass


# --- Deck ------------------------------------------------------------------------------------


async def draw_deck(session: AsyncSession, seed: str) -> dict[str, Any]:
    q_ids = list((await session.scalars(select(Question.id).where(Question.active))).all())
    pool = [DeckContent(id=cid, tags=tags) for cid, tags in await content.active_pool(session)]
    return build_deck(seed, q_ids, pool)


async def deck_view(
    session: AsyncSession, deck: dict[str, Any] | None, code: str, user_id: UUID, ends_at: Any
) -> DeckView:
    q_ids = [UUID(i) for i in deck_ids(deck, "question")]
    c_ids = [UUID(i) for i in deck_ids(deck, "content")]
    questions = {
        q.id: q
        for q in (await session.scalars(select(Question).where(Question.id.in_(q_ids)))).all()
    }
    items = await content.items(session, c_ids)

    cards: list[QuestionCard | ContentCard] = []
    for card in (deck or {}).get("cards", []):
        cid = UUID(card["id"])
        if card["kind"] == "question" and cid in questions:
            q = questions[cid]
            cards.append(
                QuestionCard(id=q.id, question_kind=q.kind, prompt=q.prompt, options=q.options)
            )
        elif card["kind"] == "content" and cid in items:
            c = items[cid]
            cards.append(
                ContentCard(
                    id=c.id, content_type=c.type, payload=c.payload, source_url=c.source_url
                )
            )

    mine_a = (
        await session.execute(
            select(Answer.question_id, Answer.value).where(
                Answer.room_code == code, Answer.user_id == user_id
            )
        )
    ).all()
    mine_r = (
        await session.execute(
            select(Reaction.content_id, Reaction.reaction).where(
                Reaction.room_code == code, Reaction.user_id == user_id
            )
        )
    ).all()
    return DeckView(
        ends_at=ends_at,
        cards=cards,
        answers={row.question_id: row.value for row in mine_a},
        reactions={row.content_id: row.reaction for row in mine_r},
    )


# --- Writes (idempotent) ---------------------------------------------------------------------


async def save_answer(
    session: AsyncSession,
    deck: dict[str, Any] | None,
    code: str,
    user_id: UUID,
    question_id: UUID,
    value: dict[str, Any],
) -> None:
    if str(question_id) not in deck_ids(deck, "question"):
        raise NotInDeckError
    question = await session.get(Question, question_id)
    if question is None:
        raise NotInDeckError
    stored = answer_rules.validate(question.kind, question.options, value)
    stmt = insert(Answer).values(
        room_code=code, user_id=user_id, question_id=question_id, value=stored
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["room_code", "user_id", "question_id"], set_={"value": stored}
        )
    )
    await session.commit()


async def save_reaction(
    session: AsyncSession,
    deck: dict[str, Any] | None,
    code: str,
    user_id: UUID,
    content_id: UUID,
    reaction: str,
) -> None:
    if str(content_id) not in deck_ids(deck, "content"):
        raise NotInDeckError
    stmt = insert(Reaction).values(
        room_code=code, user_id=user_id, content_id=content_id, reaction=reaction
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["room_code", "user_id", "content_id"], set_={"reaction": reaction}
        )
    )
    await session.commit()


async def add_social(
    session: AsyncSession, code: str, from_user: UUID, to_user: UUID, kind: str
) -> bool:
    """True if this is new (repeats are ignored)."""
    stmt = (
        insert(Social)
        .values(room_code=code, from_user=from_user, to_user=to_user, kind=kind)
        .on_conflict_do_nothing()
        .returning(Social.from_user)
    )
    created = (await session.execute(stmt)).first() is not None
    await session.commit()
    return created


# --- Read side for scoring and the graph -----------------------------------------------------


@dataclass
class RoundData:
    """Everything a round produced, as plain data (no ORM objects leave this module)."""

    # question id -> (kind, prompt, choices)
    questions: dict[UUID, tuple[str, str, list[str]]] = field(default_factory=dict)
    answers: dict[UUID, dict[UUID, dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # content id -> (type, tags)
    content: dict[UUID, tuple[str, list[str]]] = field(default_factory=dict)
    reactions: dict[UUID, dict[UUID, str]] = field(default_factory=lambda: defaultdict(dict))
    social: list[tuple[UUID, UUID, str]] = field(default_factory=list)


async def round_data(session: AsyncSession, code: str) -> RoundData:
    data = RoundData()
    for a in (await session.scalars(select(Answer).where(Answer.room_code == code))).all():
        data.answers[a.user_id][a.question_id] = a.value
    for r in (await session.scalars(select(Reaction).where(Reaction.room_code == code))).all():
        data.reactions[r.user_id][r.content_id] = r.reaction
    data.social = [
        (s.from_user, s.to_user, s.kind)
        for s in (await session.scalars(select(Social).where(Social.room_code == code))).all()
    ]
    q_ids = {q for per_user in data.answers.values() for q in per_user}
    if q_ids:
        for q in (await session.scalars(select(Question).where(Question.id.in_(q_ids)))).all():
            data.questions[q.id] = (q.kind, q.prompt, list(q.options.get("choices", [])))
    c_ids = {c for per_user in data.reactions.values() for c in per_user}
    if c_ids:
        for cid, item in (await content.items(session, list(c_ids))).items():
            data.content[cid] = (item.type, list(item.tags))
    return data


async def social_edges(session: AsyncSession, code: str) -> list[tuple[UUID, UUID, str]]:
    rows = (await session.scalars(select(Social).where(Social.room_code == code))).all()
    return [(s.from_user, s.to_user, s.kind) for s in rows]
