from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from orbit.core import events
from orbit.core.config import SettingsDep
from orbit.core.db import SessionDep
from orbit.core.redis import RedisDep
from orbit.modules.accounts.deps import ConsentedUserDep
from orbit.modules.game import service
from orbit.modules.game.answers import InvalidAnswerError
from orbit.modules.game.schemas import AnswerIn, DeckView, ReactionIn, SocialIn
from orbit.modules.graph import service as graph
from orbit.modules.graph.driver import Neo4jDep
from orbit.modules.rooms import service as rooms
from orbit.modules.rooms.deps import MemberRoomDep
from orbit.modules.rooms.service import RoomContext
from orbit.modules.rooms.state import RoomState

router = APIRouter(prefix="/rooms/{code}", tags=["game"])


def _accepting(room: RoomContext, settings: SettingsDep) -> None:
    """Answers and reactions count only during the round (plus a short network grace)."""
    if room.state not in (RoomState.PLAYING, RoomState.SCORING) or room.ends_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "round_not_running")
    if datetime.now(UTC) > room.ends_at + timedelta(seconds=settings.answer_grace_seconds):
        raise HTTPException(status.HTTP_409_CONFLICT, "round_over")


@router.get("/deck", responses={409: {"description": "round_not_started"}})
async def get_deck(room: MemberRoomDep, user: ConsentedUserDep, session: SessionDep) -> DeckView:
    """The room's cards, the same for every member, plus what I already answered (task 4.3)."""
    if room.deck is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "round_not_started")
    return await service.deck_view(session, room.deck, room.code, user.id, room.ends_at)


@router.put("/answers/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def put_answer(
    question_id: UUID,
    body: AnswerIn,
    room: MemberRoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    """Idempotent: sending the same answer twice, or changing it, is fine (task 4.6)."""
    _accepting(room, settings)
    try:
        await service.save_answer(session, room.deck, room.code, user.id, question_id, body.value)
    except service.NotInDeckError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_in_deck") from None
    except InvalidAnswerError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/reactions/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def put_reaction(
    content_id: UUID,
    body: ReactionIn,
    room: MemberRoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    _accepting(room, settings)
    try:
        await service.save_reaction(
            session, room.deck, room.code, user.id, content_id, body.reaction
        )
    except service.NotInDeckError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_in_deck") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/social", status_code=status.HTTP_204_NO_CONTENT)
async def add_social(
    body: SocialIn,
    room: MemberRoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    redis: RedisDep,
    driver: Neo4jDep,
) -> Response:
    """Follow or like another player's profile (task 4.7). After the reveal, new follows are
    pushed so the graph can animate them (7.4); they don't change scores."""
    if room.state not in (RoomState.PLAYING, RoomState.SCORING, RoomState.REVEALED):
        raise HTTPException(status.HTTP_409_CONFLICT, "round_not_running")
    if body.to_user == user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "cannot_follow_self")
    if not await rooms.is_member(session, room.code, body.to_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_a_member")
    created = await service.add_social(session, room.code, user.id, body.to_user, body.kind)
    if created and room.state == RoomState.REVEALED:
        if body.kind == "follow":
            await graph.add_follow(driver, room.code, user.id, body.to_user)
        await events.publish(
            redis,
            room.code,
            events.SocialAdded(from_user=user.id, to_user=body.to_user, kind=body.kind),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
