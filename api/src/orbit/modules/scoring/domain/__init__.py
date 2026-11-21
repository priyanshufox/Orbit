"""Pure scoring functions. No database, network or framework imports (ADR 0001 rule 3).

`score_room` turns one round's data into a score for every pair of players.
"""

from itertools import combinations
from uuid import UUID

from orbit.modules.scoring.domain import explain, signals
from orbit.modules.scoring.domain.types import (
    PairScore,
    Player,
    QuestionInfo,
    Reason,
    RootsInfo,
)

WEIGHTS: dict[str, float] = {"answers": 0.35, "reactions": 0.35, "roots": 0.15, "social": 0.15}
MAX_REASONS = 3

__all__ = [
    "WEIGHTS",
    "PairScore",
    "Player",
    "QuestionInfo",
    "Reason",
    "RootsInfo",
    "combine",
    "score_pair",
    "score_room",
]


def combine(subs: dict[str, float | None], weights: dict[str, float] = WEIGHTS) -> float:
    """Weighted mean of the signals present; a skipped signal's weight is spread proportionally
    over the others (design: Missing signals)."""
    present = {k: v for k, v in subs.items() if v is not None}
    total_weight = sum(weights[k] for k in present)
    if total_weight == 0:
        return 0.0
    return sum(weights[k] * v for k, v in present.items()) / total_weight


def score_pair(
    a: Player,
    b: Player,
    questions: dict[UUID, QuestionInfo],
    content_types: dict[UUID, str],
    social: list[tuple[UUID, UUID, str]],
    *,
    weights: dict[str, float] = WEIGHTS,
    reaction_values: dict[str, float] = signals.REACTION_VALUES,
) -> PairScore:
    if str(b.user_id) < str(a.user_id):
        a, b = b, a
    subs: dict[str, float | None] = {
        "answers": signals.answers_similarity(a, b, questions),
        "reactions": signals.reactions_similarity(a, b, values=reaction_values),
        "roots": signals.roots_similarity(a.roots, b.roots),
        "social": signals.social_score(a.user_id, b.user_id, social),
    }
    total = combine(subs, weights)

    present_weight = sum(weights[k] for k, v in subs.items() if v is not None) or 1.0
    texts = {
        "hobbies": explain.hobbies_reason(a, b),
        "answers": explain.answers_reason(a, b, questions),
        "reactions": explain.reactions_reason(a, b, content_types),
        "roots": explain.ROOTS_REASON if subs["roots"] else None,
        "social": explain.social_reason(a.user_id, b.user_id, social),
    }
    reasons = sorted(
        (
            Reason(
                signal=signal,
                text=t,
                weight=round(weights[signal] * (subs[signal] or 0) / present_weight, 4),
            )
            for k, t in texts.items()
            for signal in ["answers" if k == "hobbies" else k]
            if t and subs[signal]
        ),
        key=lambda r: -r.weight,
    )[:MAX_REASONS]

    return PairScore(
        user_a=a.user_id,
        user_b=b.user_id,
        answers=subs["answers"],
        reactions=subs["reactions"],
        roots=subs["roots"],
        social=subs["social"] or 0.0,
        total=round(total, 4),
        reasons=tuple(reasons),
    )


def score_room(
    players: list[Player],
    questions: dict[UUID, QuestionInfo],
    content_types: dict[UUID, str],
    social: list[tuple[UUID, UUID, str]],
    **kwargs: object,
) -> list[PairScore]:
    ordered = sorted(players, key=lambda p: str(p.user_id))
    return [
        score_pair(a, b, questions, content_types, social, **kwargs)
        for a, b in combinations(ordered, 2)
    ]  # type: ignore[arg-type]
