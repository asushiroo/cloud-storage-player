from __future__ import annotations

from app.core.config import Settings
from app.repositories.import_jobs import get_import_job
from app.services.imports import ImportValidationError, process_import_job
from app.services.video_delete import process_delete_job


class UnsupportedBackgroundJobError(RuntimeError):
    """Raised when a persisted background job cannot be dispatched."""


def process_background_job(settings: Settings, job_id: int):
    job = get_import_job(settings, job_id)
    if job is None:
        raise ImportValidationError(f"Import job does not exist: {job_id}")
    if job.status == "cancelled":
        return job
    if job.job_kind == "import":
        return process_import_job(settings, job_id)
    if job.job_kind == "delete":
        return process_delete_job(settings, job_id)
    raise UnsupportedBackgroundJobError(f"Unsupported background job kind: {job.job_kind}")
