from fastapi import APIRouter, Response, status

from orbit import pipeline
from orbit.core.db import SessionDep
from orbit.core.redis import RedisDep
from orbit.modules.accounts.deps import CurrentUserDep
from orbit.modules.graph.driver import Neo4jDep
from orbit.modules.privacy import service
from orbit.modules.privacy.schemas import Snapshot

router = APIRouter(prefix="/me", tags=["privacy"])


@router.get("/snapshots")
async def list_snapshots(user: CurrentUserDep, session: SessionDep) -> list[Snapshot]:
    """My saved graphs from rooms that have expired (task 8.4), newest first."""
    return await service.snapshots_for(session, user.id)


@router.delete("", status_code=status.HTTP_202_ACCEPTED)
async def delete_me(
    user: CurrentUserDep, session: SessionDep, redis: RedisDep, driver: Neo4jDep
) -> Response:
    """Delete my account (task 8.5): identity, profile, roots, snapshots, and my data in every
    room, in Postgres and Neo4j. Runs immediately; the design allows up to 24 h."""
    await pipeline.delete_account(session, redis, driver, user.id)
    return Response(status_code=status.HTTP_202_ACCEPTED)
