from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.schemas.auth import AuthLoginRequest, AuthSessionResponse
from app.services.admin_settings import get_login_password_hash
from app.core.security import (
    clear_session,
    is_authenticated,
    mark_session_authenticated,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/session", response_model=AuthSessionResponse)
def get_session_state(request: Request) -> AuthSessionResponse:
    return AuthSessionResponse(authenticated=is_authenticated(request))


@router.post("/login", response_model=AuthSessionResponse)
def login_api(payload: AuthLoginRequest, request: Request) -> AuthSessionResponse:
    settings = request.app.state.settings
    if not verify_password(payload.password, get_login_password_hash(settings)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )

    mark_session_authenticated(request)
    return AuthSessionResponse(authenticated=True)


@router.post("/logout", response_model=AuthSessionResponse)
def logout_api(request: Request) -> AuthSessionResponse:
    clear_session(request)
    return AuthSessionResponse(authenticated=False)
