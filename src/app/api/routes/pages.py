from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.security import clear_session, is_authenticated
from app.services.admin_settings import get_admin_settings, update_admin_settings, update_login_password
from app.services.settings import get_download_transfer_concurrency
from app.web.spa_assets import render_spa_index_html
from app.web.templates import build_templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return build_templates(request.app.state.settings).TemplateResponse(
        request,
        "login.html",
        {
            "error": None,
            "message": request.query_params.get("message"),
        },
    )


@router.get("/", response_class=HTMLResponse)
@router.get("/recommend", response_class=HTMLResponse)
@router.get("/library", response_class=HTMLResponse)
def library_page(request: Request) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    spa_response = _render_spa_if_enabled(request)
    if spa_response is not None:
        return spa_response
    return build_templates(request.app.state.settings).TemplateResponse(request, "library.html", {})


@router.get("/manage", response_class=HTMLResponse)
@router.get("/settings", response_class=HTMLResponse)
@router.get("/videos/{video_id}", response_class=HTMLResponse)
@router.get("/videos/{video_id}/play", response_class=HTMLResponse)
def spa_protected_page(request: Request) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    spa_response = _render_spa_if_enabled(request)
    if spa_response is not None:
        return spa_response
    return build_templates(request.app.state.settings).TemplateResponse(request, "library.html", {})


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return _render_admin_page(
        request,
        feedback=request.query_params.get("feedback"),
        error=request.query_params.get("error"),
    )


@router.post("/admin/settings", response_class=HTMLResponse)
def update_admin_settings_page(
    request: Request,
    playback_download_transfer_concurrency: Annotated[int, Form()],
    baidu_app_key: Annotated[str, Form()],
    baidu_secret_key: Annotated[str, Form()],
    baidu_sign_key: Annotated[str, Form()],
    baidu_oauth_redirect_uri: Annotated[str, Form()],
    session_secret: Annotated[str, Form()],
) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    settings = request.app.state.settings
    try:
        update_admin_settings(
            settings,
            playback_download_transfer_concurrency=playback_download_transfer_concurrency,
            baidu_app_key=baidu_app_key,
            baidu_secret_key=baidu_secret_key,
            baidu_sign_key=baidu_sign_key,
            baidu_oauth_redirect_uri=baidu_oauth_redirect_uri,
            session_secret=session_secret,
        )
    except ValueError as exc:
        return _render_admin_page(request, error=str(exc), status_code=status.HTTP_400_BAD_REQUEST)
    return _redirect_admin(feedback="管理员设置已更新。部分启动级配置需要重启服务后生效。")


@router.post("/admin/password", response_class=HTMLResponse)
def update_admin_password_page(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    confirm_new_password: Annotated[str, Form()],
) -> HTMLResponse:
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if new_password != confirm_new_password:
        return _render_admin_page(
            request,
            error="两次输入的新密码不一致。",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    settings = request.app.state.settings
    try:
        update_login_password(
            settings,
            current_password=current_password,
            new_password=new_password,
        )
    except ValueError as exc:
        return _render_admin_page(request, error=str(exc), status_code=status.HTTP_400_BAD_REQUEST)
    clear_session(request)
    return RedirectResponse(
        url="/login?message=%E5%AF%86%E7%A0%81%E5%B7%B2%E6%9B%B4%E6%96%B0%EF%BC%8C%E8%AF%B7%E9%87%8D%E6%96%B0%E7%99%BB%E5%BD%95%E3%80%82",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _render_admin_page(
    request: Request,
    *,
    feedback: str | None = None,
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    settings = request.app.state.settings
    admin_settings = get_admin_settings(settings)
    return build_templates(settings).TemplateResponse(
        request,
        "admin.html",
        {
            "feedback": feedback,
            "error": error,
            "admin_settings": admin_settings,
            "cache_download_transfer_concurrency": get_download_transfer_concurrency(settings),
        },
        status_code=status_code,
    )


def _redirect_admin(*, feedback: str | None = None, error: str | None = None) -> RedirectResponse:
    query_params: dict[str, str] = {}
    if feedback:
        query_params["feedback"] = feedback
    if error:
        query_params["error"] = error
    suffix = f"?{urlencode(query_params)}" if query_params else ""
    return RedirectResponse(
        url=f"/admin{suffix}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _render_spa_if_enabled(request: Request) -> HTMLResponse | None:
    settings = request.app.state.settings
    if not settings.use_frontend_dist:
        return None
    return render_spa_index_html(settings)
