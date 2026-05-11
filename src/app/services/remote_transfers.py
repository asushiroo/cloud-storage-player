from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Event
from time import perf_counter, time_ns
import time
from typing import Generic, TypeVar

from app.core.config import Settings
from app.repositories.import_jobs import record_import_job_transfer
from app.services.job_control import throw_if_cancel_requested
from app.services.settings import get_remote_transfer_concurrency

TTask = TypeVar("TTask")
TResult = TypeVar("TResult")


@dataclass(slots=True)
class TransferResult(Generic[TResult]):
    task: TResult
    byte_count: int
    elapsed_seconds: float
    started_at_millis: int | None = None
    completed_at_millis: int | None = None


@dataclass(slots=True)
class DeferredTransferRetry(Generic[TTask]):
    task: TTask
    wait_seconds: float


def run_bounded_transfers(
    settings: Settings,
    *,
    job_id: int | None,
    tasks: Iterable[TTask],
    transfer_func: Callable[[TTask], TransferResult[TResult]],
    concurrency: int | None = None,
    stop_event: Event | None = None,
    on_result: Callable[[TransferResult[TResult], int, int], None] | None = None,
    on_exception: Callable[[TTask, Exception], DeferredTransferRetry[TTask] | None] | None = None,
) -> list[TransferResult[TResult]]:
    pending_tasks = list(tasks)
    if not pending_tasks:
        return []
    total_task_count = len(pending_tasks)

    worker_count = max(1, concurrency or get_remote_transfer_concurrency(settings))
    results: list[TransferResult[TResult]] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        in_flight: dict[Future[TransferResult[TResult]], TTask] = {}
        next_task_index = 0

        deferred_retries: list[DeferredTransferRetry[TTask]] = []

        def submit_next() -> None:
            nonlocal next_task_index
            while next_task_index < len(pending_tasks) and len(in_flight) < worker_count:
                task = pending_tasks[next_task_index]
                next_task_index += 1
                in_flight[executor.submit(transfer_func, task)] = task

        submit_next()
        while in_flight:
            if job_id is not None:
                throw_if_cancel_requested(settings, job_id)
            if stop_event is not None and stop_event.is_set():
                for future in in_flight:
                    future.cancel()
                break

            done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
            for future in done:
                task = in_flight.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    if on_exception is None:
                        raise
                    deferred_retry = on_exception(task, exc)
                    if deferred_retry is None:
                        raise
                    deferred_retries.append(deferred_retry)
                    continue
                results.append(result)
                if job_id is not None:
                    record_import_job_transfer(
                        settings,
                        job_id,
                        byte_count=result.byte_count,
                        elapsed_seconds=result.elapsed_seconds,
                        started_at_millis=result.started_at_millis,
                        completed_at_millis=result.completed_at_millis,
                    )
                if on_result is not None:
                    on_result(result, len(results), total_task_count)
            submit_next()

            if not in_flight and deferred_retries:
                pending_tasks.extend(retry.task for retry in deferred_retries)
                _wait_for_deferred_retries(
                    settings,
                    job_id=job_id,
                    deferred_retries=deferred_retries,
                    stop_event=stop_event,
                )
                deferred_retries.clear()
                submit_next()

    return results


def measure_transfer(task: TResult, *, byte_count: int, started_at: float) -> TransferResult[TResult]:
    completed_at_millis = _current_time_millis()
    elapsed_seconds = max(perf_counter() - started_at, 0.0)
    elapsed_millis = max(int(round(elapsed_seconds * 1000)), 0)
    return TransferResult(
        task=task,
        byte_count=max(byte_count, 0),
        elapsed_seconds=elapsed_seconds,
        started_at_millis=completed_at_millis - elapsed_millis,
        completed_at_millis=completed_at_millis,
    )


def _wait_for_deferred_retries(
    settings: Settings,
    *,
    job_id: int | None,
    deferred_retries: list[DeferredTransferRetry[object]],
    stop_event: Event | None,
) -> None:
    wait_seconds = max(retry.wait_seconds for retry in deferred_retries)
    deadline = perf_counter() + wait_seconds
    while perf_counter() < deadline:
        if job_id is not None:
            throw_if_cancel_requested(settings, job_id)
        if stop_event is not None and stop_event.is_set():
            return
        remaining = deadline - perf_counter()
        time.sleep(min(1.0, max(remaining, 0.0)))


def _current_time_millis() -> int:
    return time_ns() // 1_000_000
