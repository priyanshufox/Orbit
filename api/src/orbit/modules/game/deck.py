"""Deck building (task 4.3). Pure and deterministic for a given seed and pool."""

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any
from uuid import UUID

QUESTIONS_PER_ROUND = 10
CONTENT_PER_ROUND = 15
MAX_CARDS_PER_TAG = 3


@dataclass(frozen=True)
class ContentCard:
    id: UUID
    tags: tuple[str, ...]


def build_deck(
    seed: str,
    question_ids: list[UUID],
    content: list[ContentCard],
    *,
    n_questions: int = QUESTIONS_PER_ROUND,
    n_content: int = CONTENT_PER_ROUND,
    max_per_tag: int = MAX_CARDS_PER_TAG,
) -> dict[str, Any]:
    """Pick questions and content for one room, with no tag on more than `max_per_tag` content
    cards (keeps reaction vectors informative), then interleave them: roughly two content cards
    between questions, starting with a question.

    Returns {"cards": [{"kind": "question"|"content", "id": "<uuid>"}, ...]}.
    """
    rng = random.Random(seed)  # noqa: S311 - not security sensitive, needs to be reproducible

    questions = sorted(question_ids, key=str)
    picked_q = rng.sample(questions, min(n_questions, len(questions)))

    pool = sorted(content, key=lambda c: str(c.id))
    rng.shuffle(pool)
    per_tag: Counter[str] = Counter()
    picked_c: list[ContentCard] = []
    for card in pool:
        if len(picked_c) == n_content:
            break
        if all(per_tag[t] < max_per_tag for t in card.tags):
            picked_c.append(card)
            per_tag.update(card.tags)

    cards: list[dict[str, str]] = []
    qi = ci = 0
    while qi < len(picked_q) or ci < len(picked_c):
        if qi < len(picked_q):
            cards.append({"kind": "question", "id": str(picked_q[qi])})
            qi += 1
        for _ in range(2):
            if ci < len(picked_c):
                cards.append({"kind": "content", "id": str(picked_c[ci].id)})
                ci += 1
    return {"cards": cards}


def deck_ids(deck: dict[str, Any] | None, kind: str) -> set[str]:
    return {c["id"] for c in (deck or {}).get("cards", []) if c["kind"] == kind}
