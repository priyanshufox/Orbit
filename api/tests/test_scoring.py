"""Closeness scoring maths (Phase 5): each signal, the combination, and the reasons."""

import itertools
import random
from uuid import uuid4

import pytest

from orbit.modules.scoring.domain import (
    WEIGHTS,
    Player,
    QuestionInfo,
    RootsInfo,
    combine,
    score_pair,
    score_room,
    signals,
)
from orbit.modules.scoring.domain.explain import answers_reason, reactions_reason

Q = [uuid4() for _ in range(8)]
QUESTIONS = {
    Q[0]: QuestionInfo("single", "Chai or coffee?", ("Chai", "Coffee")),
    Q[1]: QuestionInfo("single", "Pick a holiday", ("Mountains", "Beach", "City")),
    Q[2]: QuestionInfo("multi", "Hobbies", ("Sports", "Music", "Reading")),
    Q[3]: QuestionInfo("slider", "Plan your day", ()),
    Q[4]: QuestionInfo("single", "Night owl?", ("Yes", "No")),
    Q[5]: QuestionInfo("slider", "Spicy?", ()),
    Q[6]: QuestionInfo("multi", "Music", ("Bollywood", "Indie")),
    Q[7]: QuestionInfo("single", "Superpower", ("Fly", "Read minds")),
}
C = [uuid4() for _ in range(8)]
TYPES = dict.fromkeys(C, "meme")


def player(
    answers: dict | None = None, reactions: dict | None = None, roots: RootsInfo | None = None
) -> Player:
    return Player(
        user_id=uuid4(),
        answers=answers or {},
        reactions=reactions or {},
        roots=roots or RootsInfo(),
    )


SAME_ANSWERS = {
    Q[0]: {"choice": 0},
    Q[1]: {"choice": 2},
    Q[2]: {"choices": [0, 1]},
    Q[3]: {"value": 0.8},
    Q[4]: {"choice": 1},
    Q[5]: {"value": 0.2},
}


# --- answers ---------------------------------------------------------------------------------


def test_identical_answers_score_one() -> None:
    a, b = player(SAME_ANSWERS), player(SAME_ANSWERS)
    assert signals.answers_similarity(a, b, QUESTIONS) == pytest.approx(1.0)


def test_opposite_singles_and_sliders_score_low() -> None:
    a = player(
        {
            Q[0]: {"choice": 0},
            Q[1]: {"choice": 0},
            Q[4]: {"choice": 0},
            Q[3]: {"value": 0.0},
            Q[5]: {"value": 0.0},
        }
    )
    b = player(
        {
            Q[0]: {"choice": 1},
            Q[1]: {"choice": 1},
            Q[4]: {"choice": 1},
            Q[3]: {"value": 1.0},
            Q[5]: {"value": 1.0},
        }
    )
    assert signals.answers_similarity(a, b, QUESTIONS) == pytest.approx(0.0)


def test_too_few_shared_questions_skips() -> None:
    a = player({q: v for q, v in list(SAME_ANSWERS.items())[:4]})
    assert signals.answers_similarity(a, player(SAME_ANSWERS), QUESTIONS) is None


def test_slider_encoding_distinguishes_values() -> None:
    assert signals.encode_answer(QUESTIONS[Q[3]], {"value": 0.2}) == [0.2, 0.8]


# --- reactions -------------------------------------------------------------------------------


def test_reactions_same_and_opposite() -> None:
    likes = dict.fromkeys(C[:6], "laugh")
    skips = dict.fromkeys(C[:6], "skip")
    assert signals.reactions_similarity(
        player(reactions=likes), player(reactions=likes)
    ) == pytest.approx(1.0)
    assert signals.reactions_similarity(
        player(reactions=likes), player(reactions=skips)
    ) == pytest.approx(0.0)
    assert (
        signals.reactions_similarity(
            player(reactions=dict.fromkeys(C[:5], "like")), player(reactions=likes)
        )
        is None
    )


def test_send_counts_more_than_like() -> None:
    base = dict.fromkeys(C[:6], "like")
    mixed = {**base, C[0]: "send", C[1]: "skip"}
    s = signals.reactions_similarity(player(reactions=base), player(reactions=mixed))
    assert s is not None and 0 < s < 1


# --- roots and social ------------------------------------------------------------------------


def test_roots_formula() -> None:
    a = RootsInfo(
        birth_city="mumbai", school=("gvs", "noida"), childhood=frozenset({"pune", "delhi"})
    )
    b = RootsInfo(birth_city="mumbai", school=("gvs", "noida"), childhood=frozenset({"pune"}))
    assert signals.roots_similarity(a, b) == pytest.approx(min(1, 0.6 + 0.25 + 0.15 * 0.5))
    assert signals.roots_similarity(a, RootsInfo()) is None
    assert signals.roots_similarity(a, RootsInfo(birth_city="jaipur")) == 0.0


def test_social_score_caps_at_one() -> None:
    a, b = uuid4(), uuid4()
    assert signals.social_score(a, b, [(a, b, "follow")]) == pytest.approx(0.4)
    assert signals.social_score(
        a, b, [(a, b, "follow"), (b, a, "follow"), (a, b, "like_profile")]
    ) == pytest.approx(0.85)
    many = [(a, b, "follow"), (b, a, "follow")] + [(a, b, "like_profile")] * 10
    assert signals.social_score(a, b, many) == 1.0
    assert signals.social_score(a, b, [(a, uuid4(), "follow")]) == 0.0


# --- combine ---------------------------------------------------------------------------------


def test_skipped_signals_redistribute_weight() -> None:
    assert combine(
        {"answers": 1.0, "reactions": None, "roots": None, "social": 0.0}
    ) == pytest.approx(0.35 / 0.5)
    assert combine(
        {"answers": 0.5, "reactions": 0.5, "roots": 0.5, "social": 0.5}
    ) == pytest.approx(0.5)
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def random_player(rng: random.Random) -> Player:
    answers = {}
    for q, info in QUESTIONS.items():
        if info.kind == "single":
            answers[q] = {"choice": rng.randrange(len(info.choices))}
        elif info.kind == "multi":
            answers[q] = {
                "choices": sorted(
                    rng.sample(range(len(info.choices)), rng.randint(0, len(info.choices)))
                )
            }
        else:
            answers[q] = {"value": rng.random()}
    reactions = {c: rng.choice(["like", "laugh", "skip", "send"]) for c in C}
    cities = ["mumbai", "pune", "delhi", "noida"]
    roots = (
        RootsInfo(birth_city=rng.choice(cities), childhood=frozenset(rng.sample(cities, 2)))
        if rng.random() < 0.7
        else RootsInfo()
    )
    return player(answers, reactions, roots)


def test_symmetric_and_in_range_on_random_rooms() -> None:
    rng = random.Random(7)
    for _ in range(20):
        players = [random_player(rng) for _ in range(6)]
        social = [
            (a.user_id, b.user_id, rng.choice(["follow", "like_profile"]))
            for a, b in itertools.permutations(players, 2)
            if rng.random() < 0.2
        ]
        pairs = score_room(players, QUESTIONS, TYPES, social)
        assert len(pairs) == 15
        for p in pairs:
            assert str(p.user_a) < str(p.user_b)
            assert 0 <= p.total <= 1
        a, b = players[0], players[1]
        assert score_pair(a, b, QUESTIONS, TYPES, social) == score_pair(
            b, a, QUESTIONS, TYPES, social
        )


# --- reasons ---------------------------------------------------------------------------------


def test_reasons_are_specific_and_never_name_places() -> None:
    roots = RootsInfo(
        birth_city="mumbai", school=("green valley school", "noida"), childhood=frozenset({"pune"})
    )
    a = player(SAME_ANSWERS, dict.fromkeys(C[:7], "laugh"), roots)
    b = player(SAME_ANSWERS, dict.fromkeys(C[:7], "laugh"), roots)
    pair = score_pair(
        a, b, QUESTIONS, TYPES, [(a.user_id, b.user_id, "follow"), (b.user_id, a.user_id, "follow")]
    )
    texts = [r.text for r in pair.reasons]
    assert any("Same answer on 6 of 6 questions" in t for t in texts)
    assert any(t == "You both laughed at 7 of 7 memes" for t in texts)
    assert len(texts) <= 3
    everything = " ".join(r.text for r in pair.reasons).lower()
    for secret in ("mumbai", "noida", "pune", "green valley"):
        assert secret not in everything
    assert pair.roots == pytest.approx(1.0)


def test_shared_roots_reason_is_generic() -> None:
    roots = RootsInfo(birth_city="mumbai")
    a, b = player(roots=roots), player(roots=roots)
    pair = score_pair(a, b, QUESTIONS, TYPES, [])
    assert [r.text for r in pair.reasons] == ["Shared roots"]


def test_answer_reason_highlights_a_pick() -> None:
    a, b = player(SAME_ANSWERS), player(SAME_ANSWERS)
    reason = answers_reason(a, b, QUESTIONS) or ""
    assert reason.startswith("Same answer on 6 of 6 questions. Both picked “")
    assert reactions_reason(player(), player(), TYPES) is None


def test_shared_hobbies_raise_answers_and_explain() -> None:
    def pair_with(b_hobbies: set[str]) -> tuple[float | None, list[str]]:
        a = player(SAME_ANSWERS)
        b = player({**SAME_ANSWERS, Q[0]: {"choice": 1}})
        a.hobbies, b.hobbies = frozenset({"Cricket", "Music"}), frozenset(b_hobbies)
        reasons = [r.text for r in score_pair(a, b, QUESTIONS, TYPES, []).reasons]
        return signals.answers_similarity(a, b, QUESTIONS), reasons

    shared, shared_reasons = pair_with({"Cricket", "Music", "Art"})
    different, different_reasons = pair_with({"Anime", "Fashion"})
    assert shared is not None and different is not None and shared > different
    assert "Both into Cricket and Music" in shared_reasons
    assert not any(r.startswith("Both into") for r in different_reasons)
