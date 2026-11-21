"""Plain inputs and outputs of the scoring maths."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class QuestionInfo:
    kind: str  # single | multi | slider
    prompt: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class RootsInfo:
    """Already normalised (lower-case, aliases applied). None/empty = not shared."""

    birth_city: str | None = None
    school: tuple[str, str] | None = None  # (name, city)
    childhood: frozenset[str] = frozenset()

    @property
    def blank(self) -> bool:
        return not (self.birth_city or self.school or self.childhood)


@dataclass
class Player:
    user_id: UUID
    answers: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    reactions: dict[UUID, str] = field(default_factory=dict)
    roots: RootsInfo = field(default_factory=RootsInfo)
    hobbies: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Reason:
    signal: str  # answers | reactions | roots | social
    text: str
    weight: float  # this signal's share of the total, for ordering


@dataclass(frozen=True)
class PairScore:
    user_a: UUID  # user_a < user_b
    user_b: UUID
    answers: float | None
    reactions: float | None
    roots: float | None
    social: float
    total: float
    reasons: tuple[Reason, ...]
