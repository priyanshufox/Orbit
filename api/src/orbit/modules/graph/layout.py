"""3D positions from closeness (pure, deterministic).

Every pair's similarity becomes a target distance: the more similar, the shorter. Classical
MDS gives a deterministic starting shape (axis 1 = the room's strongest divide, then the next),
and SMACOF (stress majorization) then moves planets to fit all target distances as closely as
3D allows. Same scores in, same picture out.
"""

from collections.abc import Iterable
from uuid import UUID

import numpy as np

MIN_GAP = 0.18  # share of the scale kept between even the closest pair, so planets never overlap
SCALE = 160.0  # scene units for a pair at 0% similarity
DIMS = 3


def target_distances(ids: list[UUID], scores: dict[frozenset[UUID], float]) -> np.ndarray:
    """Pair distance = MIN_GAP + (1 - MIN_GAP) * (1 - similarity). Unscored pairs count as 0%."""
    n = len(ids)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            sim = min(1.0, max(0.0, scores.get(frozenset((ids[i], ids[j])), 0.0)))
            d[i, j] = d[j, i] = MIN_GAP + (1 - MIN_GAP) * (1 - sim)
    return d


def _classical_mds(d: np.ndarray) -> np.ndarray:
    n = d.shape[0]
    j = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * j @ (d**2) @ j
    values, vectors = np.linalg.eigh(b)
    order = np.argsort(values)[::-1][:DIMS]
    x = vectors[:, order] * np.sqrt(np.clip(values[order], 0, None))
    if x.shape[1] < DIMS:
        x = np.hstack([x, np.zeros((n, DIMS - x.shape[1]))])
    return x


def _smacof(d: np.ndarray, x: np.ndarray, iterations: int = 300, tol: float = 1e-9) -> np.ndarray:
    n = d.shape[0]
    prev = np.inf
    for _ in range(iterations):
        diff = x[:, None, :] - x[None, :, :]
        dist = np.sqrt((diff**2).sum(-1))
        stress = ((np.triu(dist - d, 1)) ** 2).sum()
        if prev - stress < tol:
            break
        prev = stress
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(dist > 1e-12, d / dist, 0.0)
        b = -ratio
        np.fill_diagonal(b, 0.0)
        np.fill_diagonal(b, -b.sum(axis=1))
        x = b @ x / n
    return x


def _canonical(x: np.ndarray) -> np.ndarray:
    """Centre, and fix each axis's sign so the same room always faces the same way."""
    x = x - x.mean(axis=0)
    for k in range(x.shape[1]):
        col = x[:, k]
        pivot = col[np.argmax(np.abs(col))] if col.size else 0.0
        if pivot < 0:
            x[:, k] = -col
    return x


def positions(
    ids: Iterable[UUID], scores: dict[frozenset[UUID], float], *, scale: float = SCALE
) -> dict[UUID, tuple[float, float, float]]:
    """x, y, z per player; distances follow similarity for every pair, not only drawn edges."""
    ordered = sorted(ids, key=str)
    n = len(ordered)
    if n == 0:
        return {}
    if n == 1:
        return {ordered[0]: (0.0, 0.0, 0.0)}
    d = target_distances(ordered, scores)
    x = _canonical(_smacof(d, _classical_mds(d)))
    return {pid: tuple(float(v) * scale for v in row) for pid, row in zip(ordered, x, strict=True)}  # type: ignore[misc]
