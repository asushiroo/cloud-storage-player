from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.auth_api import router as auth_api_router
from app.api.routes.cache import router as cache_router
from app.api.routes.imports import router as imports_router
from app.api.routes.library_api import router as library_api_router
from app.api.routes.pages import router as pages_router
from app.api.routes.settings import router as settings_router
from app.api.routes.stream import router as stream_router
from app.core.config import Settings, get_settings
from app.db.schema import initialize_database
from app.services.import_worker import ImportWorker
from app.services.manifest_sync_scheduler import ManifestSyncScheduler
from app.services.playback_cache_flush import PlaybackCacheFlushRegistry
from app.services.segment_prefetch import set_playback_cache_registry


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    initialize_database(app_settings)
    app_settings.covers_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.import_worker.ensure_started()
        app.state.manifest_sync_scheduler.start()
        try:
            yield
        finally:
            app.state.import_worker.stop()
            app.state.manifest_sync_scheduler.stop()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.import_worker = ImportWorker(app_settings)
    app.state.manifest_sync_scheduler = ManifestSyncScheduler(app_settings)
    app.state.playback_cache_flush_registry = PlaybackCacheFlushRegistry(app_settings)
    set_playback_cache_registry(app.state.playback_cache_flush_registry)
    app.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/covers", StaticFiles(directory=str(app_settings.covers_dir)), name="covers")
    app.include_router(auth_router)
    app.include_router(auth_api_router)
    app.include_router(cache_router)
    app.include_router(imports_router)
    app.include_router(library_api_router)
    app.include_router(settings_router)
    app.include_router(stream_router)
    app.include_router(pages_router)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
