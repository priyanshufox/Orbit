"""The four closeness signals (design: Closeness scoring). Each returns a value in [0, 1], or
None when there isn't enough data for this pair, in which case its weight is redistributed."""

import math
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from orbit.modules.scoring.domain.types import Player, QuestionInfo, RootsInfo

MIN_SHARED_QUESTIONS = 5
MIN_SHARED_ITEMS = 6

REACTION_VALUES: dict[str, float] = {"like": 1.0, "laugh": 1.0, "send": 1.5, "skip": -1.0}

ROOTS_SCHOOL = 0.6
ROOTS_BIRTH_CITY = 0.25
ROOTS_CHILDHOOD = 0.15

FOLLOW = 0.4
PROFILE_LIKE = 0.05


def cosine(a: list[float], b: list[float]) -> float | None:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return None if norm == 0 else dot / norm


def encode_answer(info: QuestionInfo, value: dict[str, Any]) -> list[float]:
    """single -> one-hot; multi -> multi-hot; slider v -> [v, 1 - v] (so 0.2 vs 0.9 differ)."""
    if info.kind == "slider":
        v = float(value.get("value", 0.5))
        return [v, 1.0 - v]
    vec = [0.0] * len(info.choices)
    picked = [value["choice"]] if info.kind == "single" else value.get("choices", [])
    for i in picked:
        if 0 <= i < len(vec):
            vec[i] = 1.0
    return vec


def shared_questions(a: Player, b: Player, questions: dict[UUID, QuestionInfo]) -> list[UUID]:
    return sorted((set(a.answers) & set(b.answers) & set(questions)), key=str)


def answers_similarity(
    a: Player,
    b: Player,
    questions: dict[UUID, QuestionInfo],
    *,
    min_shared: int = MIN_SHARED_QUESTIONS,
) -> float | None:
    shared = shared_questions(a, b, questions)
    if len(shared) < min_shared:
        return None
    va: list[float] = []
    vb: list[float] = []
    for q in shared:
        va += encode_answer(questions[q], a.answers[q])
        vb += encode_answer(questions[q], b.answers[q])
    # Sign-up hobbies count like one more multi-select question, when both picked some.
    if a.hobbies and b.hobbies:
        every = sorted(a.hobbies | b.hobbies)
        va += [1.0 if h in a.hobbies else 0.0 for h in every]
        vb += [1.0 if h in b.hobbies else 0.0 for h in every]
    sim = cosine(va, vb)
    return None if sim is None else max(0.0, min(1.0, sim))


def shared_items(a: Player, b: Player) -> list[UUID]:
    return sorted(set(a.reactions) & set(b.reactions), key=str)


def reactions_similarity(
    a: Player,
    b: Player,
    *,
    values: dict[str, float] = REACTION_VALUES,
    min_shared: int = MIN_SHARED_ITEMS,
) -> float | None:
    shared = shared_items(a, b)
    if len(shared) < min_shared:
        return None
    va = [values[a.reactions[c]] for c in shared]
    vb = [values[b.reactions[c]] for c in shared]
    sim = cosine(va, vb)
    return None if sim is None else (sim + 1) / 2


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def roots_similarity(a: RootsInfo, b: RootsInfo) -> float | None:
    """Skipped if either player left all roots blank, so keeping roots private costs nothing."""
    if a.blank or b.blank:
        return None
    score = 0.0
    if a.school and b.school and a.school == b.school:
        score += ROOTS_SCHOOL
    if a.birth_city and b.birth_city and a.birth_city == b.birth_city:
        score += ROOTS_BIRTH_CITY
    score += ROOTS_CHILDHOOD * jaccard(a.childhood, b.childhood)
    return min(1.0, score)


def social_score(a: UUID, b: UUID, social: Iterable[tuple[UUID, UUID, str]]) -> float:
    score = 0.0
    for src, dst, kind in social:
        if {src, dst} != {a, b}:
            continue
        score += FOLLOW if kind == "follow" else PROFILE_LIKE if kind == "like_profile" else 0.0
    return min(1.0, score)
