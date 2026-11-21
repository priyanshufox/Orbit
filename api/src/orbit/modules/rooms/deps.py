"""Room access for routes in any module: `RoomDep` (any consented user), `MemberRoomDep`,
`HostRoomDep`. They yield a `RoomContext`, never the ORM row."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from orbit.core.db import SessionDep
from orbit.modules.accounts.deps import ConsentedUserDep
from orbit.modules.rooms import codes, service
from orbit.modules.rooms.service import RoomContext


async def get_room_context(code: str, user: ConsentedUserDep, session: SessionDep) -> RoomContext:
    code = codes.normalise(code)
    if not codes.is_valid(code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room_not_found")
    try:
        return await service.context(session, code, user.id)
    except service.RoomNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room_not_found") from None


RoomDep = Annotated[RoomContext, Depends(get_room_context)]


async def require_member(room: RoomDep) -> RoomContext:
    if not room.is_member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_a_member")
    return room


async def require_host(room: RoomDep) -> RoomContext:
    if not room.is_host:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "host_only")
    return room


MemberRoomDep = Annotated[RoomContext, Depends(require_member)]
HostRoomDep = Annotated[RoomContext, Depends(require_host)]
