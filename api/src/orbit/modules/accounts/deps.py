"""`CurrentUserDep`: the signed-in player's Orbit profile. Other modules import this, not models."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from orbit.core.auth import IdentityDep
from orbit.core.db import SessionDep
from orbit.modules.accounts import service
from orbit.modules.accounts.models import User


async def get_current_user(identity: IdentityDep, session: SessionDep) -> User:
    profile = await service.get_profile(session, identity.user_id)
    if profile is None:
        # Signed in, but has not passed the age gate yet.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "onboarding_required")
    return profile


CurrentUserDep = Annotated[User, Depends(get_current_user)]
