from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.security import is_authenticated


def require_authenticated(request: Request) -> None:
    if is_authenticated(request):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
    )
