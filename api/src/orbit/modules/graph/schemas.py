from uuid import UUID

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: UUID
    name: str
    avatar_url: str | None
    community: int
    # Position in the 3D scene: distance between two planets follows their closeness.
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class EdgeReason(BaseModel):
    signal: str
    text: str
    weight: float


class GraphEdge(BaseModel):
    a: UUID
    b: UUID
    total: float
    answers: float | None
    reactions: float | None
    roots: float | None
    social: float | None
    reasons: list[EdgeReason]


class Follow(BaseModel):
    from_user: UUID
    to_user: UUID


class GraphView(BaseModel):
    """The reveal (design: everything public): every drawn edge carries its score and reasons."""

    room_code: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    follows: list[Follow]
