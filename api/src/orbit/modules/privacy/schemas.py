from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class Snapshot(BaseModel):
    id: UUID
    room_code: str
    taken_at: datetime
    # {"me": id, "nodes": [...], "edges": [...], "follows": [...]}: my ego graph from the reveal
    graph: dict[str, Any]
