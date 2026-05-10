from __future__ import annotations

from app.core.config import Settings
from app.repositories.import_jobs import get_import_job


class JobCancelledError(RuntimeError):
    """Raised when the user requests cancellation for a background job."""


CANCELLED_BY_USER_MESSAGE = "Cancelled by user."


def throw_if_cancel_requested(settings: Settings, job_id: int) -> None:
    job = get_import_job(settings, job_id)
    if job is None:
        raise JobCancelledError("Background job no longer exists.")
    if job.cancel_requested:
        raise JobCancelledError(CANCELLED_BY_USER_MESSAGE)
