from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.security import is_authenticated
from app.web.templates import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None},
    )


@router.get("/", response_class=HTMLResponse)
async def library_page(request: Request) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "library.html",
        {},
    )


@router.get("/manage", response_class=HTMLResponse)
@router.get("/settings", response_class=HTMLResponse)
@router.get("/videos/{video_id}", response_class=HTMLResponse)
@router.get("/videos/{video_id}/play", response_class=HTMLResponse)
async def spa_protected_page(request: Request) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "library.html",
        {},
    )
