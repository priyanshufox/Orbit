from fastapi import APIRouter, HTTPException, status

from orbit import pipeline
from orbit.core.config import SettingsDep
from orbit.core.db import SessionDep
from orbit.modules.graph.driver import Neo4jDep
from orbit.modules.graph.schemas import GraphView
from orbit.modules.rooms.deps import RoomDep
from orbit.modules.rooms.state import RoomState

router = APIRouter(prefix="/rooms/{code}", tags=["graph"])


@router.get(
    "/graph", responses={403: {"description": "not_in_room"}, 409: {"description": "not_revealed"}}
)
async def get_graph(
    room: RoomDep, session: SessionDep, driver: Neo4jDep, settings: SettingsDep
) -> GraphView:
    """The reveal (task 6.6): the same view for every member and the host screen. Every edge
    carries its score and reasons (reveal is public to the room)."""
    if not (room.is_member or room.is_host):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_in_room")
    if room.state != RoomState.REVEALED:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_revealed")
    view = await pipeline.graph_for(session, driver, room.code, settings)
    if view is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_revealed")
    return view
