"""The room state machine (task 3.2). Pure: no I/O.

CREATED -> LOBBY -> PLAYING -> SCORING -> REVEALED -> EXPIRED; any state may expire.
"""

from enum import StrEnum


class RoomState(StrEnum):
    CREATED = "CREATED"
    LOBBY = "LOBBY"
    PLAYING = "PLAYING"
    SCORING = "SCORING"
    REVEALED = "REVEALED"
    EXPIRED = "EXPIRED"


TRANSITIONS: dict[RoomState, frozenset[RoomState]] = {
    RoomState.CREATED: frozenset({RoomState.LOBBY, RoomState.EXPIRED}),
    RoomState.LOBBY: frozenset({RoomState.PLAYING, RoomState.EXPIRED}),
    RoomState.PLAYING: frozenset({RoomState.SCORING, RoomState.EXPIRED}),
    RoomState.SCORING: frozenset({RoomState.REVEALED, RoomState.EXPIRED}),
    RoomState.REVEALED: frozenset({RoomState.EXPIRED}),
    RoomState.EXPIRED: frozenset(),
}

# Who may join: before scoring starts. Late joiners play until the timer ends.
JOINABLE = frozenset({RoomState.CREATED, RoomState.LOBBY, RoomState.PLAYING})


class IllegalTransitionError(ValueError):
    pass


def can_move(current: RoomState, target: RoomState) -> bool:
    return target in TRANSITIONS[current]


def check_move(current: RoomState, target: RoomState) -> None:
    if not can_move(current, target):
        raise IllegalTransitionError(f"{current} -> {target}")


def sources_for(target: RoomState) -> frozenset[RoomState]:
    """States from which `target` can be reached (used for compare-and-set updates)."""
    return frozenset(s for s, targets in TRANSITIONS.items() if target in targets)
