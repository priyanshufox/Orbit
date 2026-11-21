"""Retention (Phase 8): graph snapshots kept on the account, and the deletion audit log."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.graph.schemas import GraphView
from orbit.modules.privacy.models import AuditLog, GraphSnapshot
from orbit.modules.privacy.schemas import Snapshot


def ego_graph(view: GraphView, user_id: UUID) -> dict[str, Any]:
    """Me, the people I'm connected to, and the edges and follows that touch me."""
    edges = [e for e in view.edges if user_id in (e.a, e.b)]
    ids = {user_id} | {e.a for e in edges} | {e.b for e in edges}
    follows = [f for f in view.follows if user_id in (f.from_user, f.to_user)]
    return {
        "me": str(user_id),
        "nodes": [n.model_dump(mode="json") for n in view.nodes if n.id in ids],
        "edges": [e.model_dump(mode="json") for e in edges],
        "follows": [f.model_dump(mode="json") for f in follows],
    }


async def write_snapshots(session: AsyncSession, view: GraphView, member_ids: list[UUID]) -> int:
    present = {n.id for n in view.nodes}
    rows = [
        GraphSnapshot(user_id=m, room_code=view.room_code, graph=ego_graph(view, m))
        for m in member_ids
        if m in present
    ]
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def snapshots_for(session: AsyncSession, user_id: UUID) -> list[Snapshot]:
    stmt = (
        select(GraphSnapshot)
        .where(GraphSnapshot.user_id == user_id)
        .order_by(GraphSnapshot.taken_at.desc())
    )
    return [
        Snapshot(id=s.id, room_code=s.room_code, taken_at=s.taken_at, graph=s.graph)
        for s in (await session.scalars(stmt)).all()
    ]


async def audit(session: AsyncSession, action: str, detail: dict[str, Any]) -> None:
    """Record a deletion. `detail` must hold no personal data: codes and counts only."""
    session.add(AuditLog(action=action, detail=detail))
    await session.commit()
