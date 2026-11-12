"""Who is calling: verify the short-lived JWT that Better Auth (web app) issues.

The web app signs tokens with keys it publishes at /api/auth/jwks; we fetch and cache those
public keys, so no secret is shared between the two apps. This gives an *identity* (auth user id,
email). Whether that identity has an Orbit profile is the accounts module's business
(`orbit.modules.accounts.deps.CurrentUserDep`).

The same `TokenVerifier.verify` authenticates WebSocket connections (task 3.4).
"""

from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Algorithms Better Auth's jwt plugin can be configured with (default EdDSA / Ed25519).
ALGORITHMS = ["EdDSA", "ES256", "ES512", "RS256", "PS256"]


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    email: str
    name: str | None = None
    picture: str | None = None


class SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK: ...


class InvalidTokenError(Exception):
    pass


class TokenVerifier:
    def __init__(self, keys: SigningKeySource, *, issuer: str, audience: str) -> None:
        self._keys = keys
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_jwks_url(cls, url: str, *, issuer: str, audience: str) -> "TokenVerifier":
        # Caches keys for an hour and refetches on an unknown key id (key rotation).
        keys = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)
        return cls(keys, issuer=issuer, audience=audience)

    def verify(self, token: str) -> Identity:
        """Blocking on a key-cache miss (HTTP fetch); call via `averify` in async code."""
        try:
            key = self._keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=ALGORITHMS,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            return Identity(
                user_id=UUID(claims["sub"]),
                email=claims["email"],
                name=claims.get("name"),
                picture=claims.get("picture"),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as e:
            raise InvalidTokenError(str(e)) from e

    async def averify(self, token: str) -> Identity:
        return await run_in_threadpool(self.verify, token)


_bearer = HTTPBearer(auto_error=False)


async def get_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Identity:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "not_authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    verifier: TokenVerifier = request.app.state.token_verifier
    try:
        return await verifier.averify(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None


IdentityDep = Annotated[Identity, Depends(get_identity)]
