"""3D layout: planets' distances follow closeness for every pair (graph/layout.py)."""

import itertools
import math
import random
from uuid import UUID, uuid4

from orbit.modules.graph.layout import MIN_GAP, SCALE, positions


def ids(n: int) -> list[UUID]:
    return sorted((uuid4() for _ in range(n)), key=str)


def dist(p: dict, a: UUID, b: UUID) -> float:
    return math.dist(p[a], p[b])


def ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for rank, i in enumerate(order):
        r[i] = rank
    return r


def spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    return cov / math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))


def test_small_rooms() -> None:
    (a,) = ids(1)
    assert positions([a], {}) == {a: (0.0, 0.0, 0.0)}
    a, b = ids(2)
    p = positions([a, b], {frozenset((a, b)): 0.5})
    expected = (MIN_GAP + (1 - MIN_GAP) * 0.5) * SCALE
    assert math.isclose(dist(p, a, b), expected, rel_tol=1e-3)


def test_deterministic_regardless_of_input_order() -> None:
    p = ids(6)
    scores = {frozenset(pair): random.Random(7).random() for pair in itertools.combinations(p, 2)}
    assert positions(p, scores) == positions(list(reversed(p)), scores)


def test_more_similar_pairs_are_closer() -> None:
    """Across random rooms of 20, distance and similarity rank almost perfectly opposite."""
    rng = random.Random(11)
    for _ in range(5):
        p = ids(20)
        # Realistic rooms: hidden "taste" points make scores consistent with one another.
        taste = {x: (rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)) for x in p}
        scores = {
            frozenset((a, b)): max(0.0, 1 - math.dist(taste[a], taste[b]) / 4)
            for a, b in itertools.combinations(p, 2)
        }
        pos = positions(p, scores)
        pairs = list(itertools.combinations(p, 2))
        rho = spearman([scores[frozenset(q)] for q in pairs], [dist(pos, *q) for q in pairs])
        assert rho < -0.95, rho


def test_groups_sit_together() -> None:
    g1, g2 = ids(5), ids(5)
    scores = {}
    for a, b in itertools.combinations(g1 + g2, 2):
        same = (a in g1) == (b in g1)
        scores[frozenset((a, b))] = 0.8 if same else 0.2
    pos = positions(g1 + g2, scores)
    inside = max(dist(pos, a, b) for g in (g1, g2) for a, b in itertools.combinations(g, 2))
    across = min(dist(pos, a, b) for a in g1 for b in g2)
    assert inside < across


def test_closest_pair_never_overlaps() -> None:
    a, b, c = ids(3)
    p = positions(
        [a, b, c], {frozenset((a, b)): 1.0, frozenset((a, c)): 0.0, frozenset((b, c)): 0.0}
    )
    assert dist(p, a, b) >= MIN_GAP * SCALE * 0.9
