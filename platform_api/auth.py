import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from platform_api.config import get_settings
from platform_api.schemas import TokenRequest, TokenResponse

AUDIENCE = "ml-platform"
ALGORITHM = "HS256"

router = APIRouter(tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Who is calling: their user name, their team, and their role (member or admin)."""

    username: str
    team: str
    role: str


# Builds the fake user store. In real life the identity provider owns users, teams and roles.
def fake_users() -> dict[str, Principal]:
    return {
        "alice": Principal("alice", "team-a", "member"),
        "bob": Principal("bob", "team-b", "member"),
        "root": Principal("root", "platform", "admin"),
    }


# Builds a signed JWT carrying the user, team and role, plus audience and expiry.
def create_token(principal: Principal) -> str:
    settings = get_settings()
    claims = {
        "sub": principal.username,
        "team": principal.team,
        "role": principal.role,
        "aud": AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


# Checks signature, expiry and audience, and returns the token's claims or raises 401.
def verify_token(token: str) -> dict[str, str]:
    try:
        return jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            options={"require": ["exp", "sub", "aud", "team", "role"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None


# Fake login: all demo users share one password from the environment.
@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest) -> TokenResponse:
    principal = fake_users().get(body.username)
    # compare_digest avoids leaking information through how long the comparison takes.
    if principal is None or not hmac.compare_digest(get_settings().demo_password, body.password):
        raise HTTPException(status_code=401, detail="Wrong username or password")
    return TokenResponse(access_token=create_token(principal))


# Dependency: reads the Bearer token, verifies it, and returns who is calling.
def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = verify_token(credentials.credentials)
    principal = Principal(claims["sub"], claims["team"], claims["role"])
    # Saved on the request so the access log records who called and for which team.
    request.state.user = principal.username
    request.state.team = principal.team
    return principal


# Dependency: only platform admins get through, everyone else gets 403.
def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Platform admins only")
    return principal
