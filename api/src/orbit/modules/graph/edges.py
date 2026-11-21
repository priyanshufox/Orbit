"""Which closeness edges to draw (task 6.3). Pure."""

from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID

Pair = tuple[UUID, UUID]


def select_edges(
    scores: Iterable[tuple[UUID, UUID, float]], *, threshold: float, top_k: int
) -> set[Pair]:
    """Every pair at or above `threshold`, plus each player's `top_k` strongest pairs so nobody
    is drawn alone. Pairs are (a, b) with a < b."""
    scored = [(a, b, t) if str(a) < str(b) else (b, a, t) for a, b, t in scores]
    chosen = {(a, b) for a, b, t in scored if t >= threshold}
    per_player: dict[UUID, list[tuple[float, Pair]]] = defaultdict(list)
    for a, b, t in scored:
        per_player[a].append((t, (a, b)))
        per_player[b].append((t, (a, b)))
    for ranked in per_player.values():
        ranked.sort(key=lambda x: (-x[0], str(x[1])))
        chosen.update(pair for _, pair in ranked[:top_k])
    return chosen
