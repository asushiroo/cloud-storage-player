from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse

from app.core.config import Settings


def read_spa_index_html(settings: Settings) -> str | None:
    index_path = settings.frontend_dist_dir / "index.html"
    if not index_path.exists() or not index_path.is_file():
        return None
    return index_path.read_text(encoding="utf-8")


def render_spa_index_html(settings: Settings) -> HTMLResponse | None:
    content = read_spa_index_html(settings)
    if content is None:
        return None
    return HTMLResponse(content=content)


def frontend_dist_assets_dir(settings: Settings) -> Path:
    return settings.frontend_dist_dir / "assets"
