from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import require_authenticated
from app.api.schemas.imports import ImportJobResponse, ImportRequest
from app.repositories.import_jobs import get_import_job, list_import_jobs
from app.services.imports import ImportValidationError, import_local_video

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_import(
    payload: ImportRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    try:
        job = import_local_video(
            settings,
            source_path=payload.source_path,
            folder_id=payload.folder_id,
            title=payload.title,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ImportJobResponse.model_validate(job)


@router.get("", response_model=list[ImportJobResponse])
async def get_import_jobs(
    request: Request,
    _: None = Depends(require_authenticated),
) -> list[ImportJobResponse]:
    settings = request.app.state.settings
    return [ImportJobResponse.model_validate(job) for job in list_import_jobs(settings)]


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_job_detail(
    job_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    job = get_import_job(settings, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found.")

    return ImportJobResponse.model_validate(job)
