from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.security import (
    clear_session,
    mark_session_authenticated,
    verify_password,
)
from app.web.templates import templates

router = APIRouter()


@router.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, password: Annotated[str, Form()]) -> HTMLResponse:
    settings = request.app.state.settings
    if verify_password(password, settings.effective_password_hash):
        mark_session_authenticated(request)
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid password."},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@router.post("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    clear_session(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
