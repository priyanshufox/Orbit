from fastapi import APIRouter, HTTPException, status

from orbit.core.auth import IdentityDep
from orbit.core.db import SessionDep
from orbit.modules.accounts import service
from orbit.modules.accounts.deps import CurrentUserDep
from orbit.modules.accounts.schemas import AgeGate, Me, Roots

router = APIRouter(prefix="/me", tags=["accounts"])


@router.get("")
async def get_me(identity: IdentityDep, session: SessionDep) -> Me:
    """Who am I, and how far through onboarding (age gate, consent)."""
    return service.to_me(identity, await service.get_profile(session, identity.user_id))


@router.post(
    "/age",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Under 18: the sign-in was deleted"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Impossible date of birth"},
    },
)
async def pass_age_gate(body: AgeGate, identity: IdentityDep, session: SessionDep) -> Me:
    """Age gate (task 2.6). Adults get an Orbit profile; for under-18s the sign-in identity is
    deleted and nothing is stored."""
    try:
        profile = await service.pass_age_gate(session, identity, body.date_of_birth)
    except service.Under18Error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "under_18") from None
    except service.InvalidBirthDateError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_birth_date") from None
    return service.to_me(identity, profile)


@router.post("/consent")
async def give_consent(identity: IdentityDep, user: CurrentUserDep, session: SessionDep) -> Me:
    """Record agreement to the data notice (task 2.7). Idempotent."""
    return service.to_me(identity, await service.give_consent(session, user))


@router.get("/roots")
async def get_roots(user: CurrentUserDep, session: SessionDep) -> Roots:
    return await service.get_roots(session, user.id)


@router.put("/roots")
async def put_roots(body: Roots, user: CurrentUserDep, session: SessionDep) -> Roots:
    """Replace all roots (task 2.8). Every field is optional."""
    return await service.replace_roots(session, user.id, body)
