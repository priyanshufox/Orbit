"""Human reasons for an edge (task 5.6). Roots are only ever "Shared roots": never a school or
city name, because the reveal is public to the whole room."""

from uuid import UUID

from orbit.modules.scoring.domain.signals import shared_items, shared_questions
from orbit.modules.scoring.domain.types import Player, QuestionInfo

SLIDER_SAME = 0.15
CONTENT_WORDS = {"fact": "facts", "meme": "memes", "news": "headlines"}


def answers_reason(a: Player, b: Player, questions: dict[UUID, QuestionInfo]) -> str | None:
    shared = shared_questions(a, b, questions)
    same = 0
    highlight = None
    for q in shared:
        info, va, vb = questions[q], a.answers[q], b.answers[q]
        if info.kind == "slider":
            match = abs(va.get("value", 0) - vb.get("value", 0)) <= SLIDER_SAME
        elif info.kind == "single":
            match = va.get("choice") == vb.get("choice")
            if match and highlight is None and 0 <= va["choice"] < len(info.choices):
                highlight = f"Both picked “{info.choices[va['choice']]}” for “{info.prompt}”"
        else:
            match = bool(set(va.get("choices", [])) & set(vb.get("choices", [])))
        same += match
    if not shared or same == 0:
        return None
    base = f"Same answer on {same} of {len(shared)} questions"
    return f"{base}. {highlight}" if highlight else base


def hobbies_reason(a: Player, b: Player) -> str | None:
    shared = sorted(a.hobbies & b.hobbies)
    if not shared:
        return None
    if len(shared) == 1:
        return f"Both into {shared[0]}"
    listed = ", ".join(shared[:3][:-1]) + f" and {shared[:3][-1]}"
    return f"Both into {listed}"


def reactions_reason(a: Player, b: Player, content_types: dict[UUID, str]) -> str | None:
    shared = shared_items(a, b)
    if not shared:
        return None
    laughed = [c for c in shared if a.reactions[c] == b.reactions[c] == "laugh"]
    positive = [c for c in shared if a.reactions[c] != "skip" and b.reactions[c] != "skip"]
    skipped = [c for c in shared if a.reactions[c] == b.reactions[c] == "skip"]

    def noun(items: list[UUID]) -> str:
        kinds = {content_types.get(c) for c in items}
        return CONTENT_WORDS.get(kinds.pop(), "cards") if len(kinds) == 1 else "cards"

    if len(laughed) >= 2:
        return f"You both laughed at {len(laughed)} of {len(shared)} {noun(shared)}"
    if len(positive) >= 2:
        return f"You both liked {len(positive)} of {len(shared)} {noun(shared)}"
    if len(skipped) >= 2:
        return f"You both skipped the same {len(skipped)} {noun(skipped)}"
    return None


def social_reason(a: UUID, b: UUID, social: list[tuple[UUID, UUID, str]]) -> str | None:
    follows = {(s, d) for s, d, k in social if k == "follow" and {s, d} == {a, b}}
    if len(follows) == 2:
        return "Follow each other"
    if follows:
        return "One follows the other"
    if any(k == "like_profile" and {s, d} == {a, b} for s, d, k in social):
        return "Liked a profile"
    return None


ROOTS_REASON = "Shared roots"
