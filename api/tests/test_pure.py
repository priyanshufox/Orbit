"""Pure logic: room codes, state machine (3.2), deck (4.3), answer validation (4.6), edge
selection (6.3), community labels (6.4)."""

import itertools
from collections import Counter
from uuid import UUID, uuid4

import pytest

from orbit.modules.game.answers import InvalidAnswerError, validate
from orbit.modules.game.deck import ContentCard, build_deck, deck_ids
from orbit.modules.graph.clusters import louvain, relabel
from orbit.modules.graph.edges import select_edges
from orbit.modules.rooms import codes
from orbit.modules.rooms.state import (
    TRANSITIONS,
    IllegalTransitionError,
    RoomState,
    check_move,
    sources_for,
)

# --- codes -----------------------------------------------------------------------------------


def test_codes_avoid_look_alikes() -> None:
    for _ in range(500):
        code = codes.new_code()
        assert codes.is_valid(code)
        assert not set(code) & set("01OIL")


def test_code_normalising() -> None:
    assert codes.normalise(" abc2de ") == "ABC2DE"
    assert not codes.is_valid("ABC")


# --- state machine ---------------------------------------------------------------------------

HAPPY_PATH = ["CREATED", "LOBBY", "PLAYING", "SCORING", "REVEALED", "EXPIRED"]


def test_happy_path() -> None:
    for a, b in itertools.pairwise(HAPPY_PATH):
        check_move(RoomState(a), RoomState(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("LOBBY", "SCORING"),
        ("CREATED", "PLAYING"),
        ("REVEALED", "PLAYING"),
        ("EXPIRED", "LOBBY"),
        ("SCORING", "PLAYING"),
        ("PLAYING", "LOBBY"),
    ],
)
def test_illegal_moves(a: str, b: str) -> None:
    with pytest.raises(IllegalTransitionError):
        check_move(RoomState(a), RoomState(b))


def test_everything_can_expire_and_sources() -> None:
    for state in RoomState:
        if state != RoomState.EXPIRED:
            assert RoomState.EXPIRED in TRANSITIONS[state]
    assert sources_for(RoomState.SCORING) == {RoomState.PLAYING}


# --- deck ------------------------------------------------------------------------------------

TAGS = [
    "travel",
    "tech",
    "cricket",
    "food",
    "science",
    "bollywood",
    "wholesome",
    "dark-humour",
    "politics-light",
]


def pool(n: int = 60) -> tuple[list[UUID], list[ContentCard]]:
    qs = [uuid4() for _ in range(30)]
    content = [
        ContentCard(
            id=uuid4(), tags=(TAGS[i % 9], TAGS[(i + 2) % 9]) if i % 4 == 0 else (TAGS[i % 9],)
        )
        for i in range(n)
    ]
    return qs, content


def test_deck_is_deterministic_balanced_and_interleaved() -> None:
    qs, content = pool()
    deck = build_deck("ROOM42", qs, content)
    assert deck == build_deck("ROOM42", list(reversed(qs)), list(reversed(content)))
    assert deck != build_deck("OTHER1", qs, content)

    kinds = [c["kind"] for c in deck["cards"]]
    assert kinds.count("question") == 10
    assert kinds.count("content") == 15
    assert kinds[0] == "question"

    by_id = {str(c.id): c for c in content}
    per_tag = Counter(t for cid in deck_ids(deck, "content") for t in by_id[cid].tags)
    assert max(per_tag.values()) <= 3


def test_small_pool_takes_what_exists() -> None:
    qs, content = pool(4)
    deck = build_deck("X", qs[:3], content)
    assert len(deck_ids(deck, "question")) == 3
    assert len(deck_ids(deck, "content")) == 4


# --- answers ---------------------------------------------------------------------------------

CHOICES = {"choices": ["a", "b", "c"]}


@pytest.mark.parametrize(
    ("kind", "options", "value", "stored"),
    [
        ("single", CHOICES, {"choice": 2}, {"choice": 2}),
        ("multi", CHOICES, {"choices": [2, 0, 2]}, {"choices": [0, 2]}),
        ("multi", CHOICES, {"choices": []}, {"choices": []}),
        ("slider", {}, {"value": 0.33333}, {"value": 0.3333}),
        ("slider", {}, {"value": 1}, {"value": 1.0}),
    ],
)
def test_valid_answers(kind: str, options: dict, value: dict, stored: dict) -> None:
    assert validate(kind, options, value) == stored


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("single", {"choice": 3}),
        ("single", {"choice": True}),
        ("single", {}),
        ("multi", {"choices": [5]}),
        ("slider", {"value": 1.2}),
        ("slider", {"value": "0.5"}),
    ],
)
def test_invalid_answers(kind: str, value: dict) -> None:
    with pytest.raises(InvalidAnswerError):
        validate(kind, CHOICES, value)


# --- edges and clusters ----------------------------------------------------------------------


def ids(n: int) -> list[UUID]:
    return sorted((uuid4() for _ in range(n)), key=str)


def test_edges_threshold_plus_top_k() -> None:
    a, b, c, d = ids(4)
    scores = [(a, b, 0.9), (a, c, 0.2), (a, d, 0.1), (b, c, 0.3), (b, d, 0.05), (c, d, 0.01)]
    assert select_edges(scores, threshold=0.4, top_k=0) == {(a, b)}
    chosen = select_edges(scores, threshold=0.4, top_k=1)
    # Everyone keeps at least their best pair, so nobody is alone.
    assert {(a, b), (b, c), (a, d)} <= chosen
    assert all(any(p in pair for pair in chosen) for p in (a, b, c, d))


def test_louvain_finds_two_groups_with_stable_labels() -> None:
    p = ids(6)
    strong = [
        (p[0], p[1], 0.9),
        (p[1], p[2], 0.9),
        (p[0], p[2], 0.9),
        (p[3], p[4], 0.9),
        (p[4], p[5], 0.9),
        (p[3], p[5], 0.9),
    ]
    labels = louvain(p, [*strong, (p[2], p[3], 0.05)])
    assert labels[p[0]] == labels[p[1]] == labels[p[2]]
    assert labels[p[3]] == labels[p[4]] == labels[p[5]]
    assert labels[p[0]] != labels[p[3]]
    assert set(labels.values()) == {0, 1}


def test_relabel_is_order_independent() -> None:
    p = ids(3)
    assert relabel({p[0]: 7, p[1]: 7, p[2]: 3}) == relabel({p[0]: 1, p[1]: 1, p[2]: 9})
