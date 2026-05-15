from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies import require_authenticated
from app.api.schemas.imports import (
    CancelAllImportJobsResponse,
    ClearedImportJobsResponse,
    FolderImportRequest,
    FolderImportResponse,
    ImportJobResponse,
    ImportRequest,
)
from app.repositories.import_jobs import (
    ImportJobCancellationNotAllowedError,
    delete_completed_import_jobs,
    delete_failed_import_jobs,
    get_import_job,
    list_import_jobs,
    request_cancel_all_active_jobs,
    request_cancel_job,
)
from app.services.imports import ImportValidationError, queue_folder_import_jobs, queue_import_job

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
def create_import(
    payload: ImportRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    worker = request.app.state.import_worker
    try:
        job = queue_import_job(
            settings,
            source_path=payload.source_path,
            title=payload.title,
            tags=payload.tags,
            worker=worker,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ImportJobResponse.model_validate(job)


@router.post("/folders", response_model=FolderImportResponse, status_code=status.HTTP_201_CREATED)
def create_folder_import(
    payload: FolderImportRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> FolderImportResponse:
    settings = request.app.state.settings
    worker = request.app.state.import_worker
    try:
        jobs = queue_folder_import_jobs(
            settings,
            source_dir=payload.source_dir,
            tags=payload.tags,
            worker=worker,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return FolderImportResponse(
        discovered_file_count=len(jobs),
        jobs=[ImportJobResponse.model_validate(job) for job in jobs],
    )


@router.post("/{job_id}/cancel", response_model=ImportJobResponse)
def cancel_import_job(
    job_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    try:
        job = request_cancel_job(settings, job_id)
    except ImportJobCancellationNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found.")
    return ImportJobResponse.model_validate(job)


@router.post("/cancel-all", response_model=CancelAllImportJobsResponse)
def cancel_all_import_jobs(
    request: Request,
    _: None = Depends(require_authenticated),
) -> CancelAllImportJobsResponse:
    settings = request.app.state.settings
    updated_job_count = request_cancel_all_active_jobs(settings)
    return CancelAllImportJobsResponse(updated_job_count=updated_job_count)


@router.delete("", response_model=ClearedImportJobsResponse)
def clear_finished_import_jobs(
    request: Request,
    status_group: Literal["completed", "failed"] = Query(default="completed"),
    _: None = Depends(require_authenticated),
) -> ClearedImportJobsResponse:
    settings = request.app.state.settings
    if status_group == "failed":
        deleted_job_count = delete_failed_import_jobs(settings)
    else:
        deleted_job_count = delete_completed_import_jobs(settings)
    return ClearedImportJobsResponse(
        deleted_job_count=deleted_job_count,
        status_group=status_group,
    )


@router.get("", response_model=list[ImportJobResponse])
def get_import_jobs(
    request: Request,
    _: None = Depends(require_authenticated),
) -> list[ImportJobResponse]:
    settings = request.app.state.settings
    request.app.state.import_worker.ensure_started()
    return [ImportJobResponse.model_validate(job) for job in list_import_jobs(settings)]


@router.get("/{job_id}", response_model=ImportJobResponse)
def get_import_job_detail(
    job_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    request.app.state.import_worker.ensure_started()
    job = get_import_job(settings, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found.")

    return ImportJobResponse.model_validate(job)
