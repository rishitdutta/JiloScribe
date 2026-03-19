from enum import StrEnum
import asyncio
import inspect
from typing import Callable, ParamSpec, TypeVar, Generic, Awaitable, Self
from uuid import UUID
from datetime import datetime, timezone


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"
    CANCELLED = "cancelled"


P = ParamSpec("P")
T = TypeVar("T")


class Job(Generic[P, T]):
    def __init__(
        self, id: str | UUID, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ):
        self.id = id if isinstance(id, str) else str(id)
        self.fn: Callable[P, T] = fn
        self.callback: Callable[[Self], None | Awaitable[None]] | None = None
        self.callback_error: Exception | None = None
        self.args = args
        self.kwargs = kwargs
        self.created_at: datetime = datetime.now(tz=timezone.utc)

        self.status = JobStatus.PENDING
        self.result: T  # undefined
        self.error: Exception  # undefined

        self.event = asyncio.Event()
        self._task: asyncio.Task[T] | None = None

    async def wait(self) -> T:
        await self.event.wait()
        if self.status == JobStatus.DONE:
            return self.result
        if self.status == JobStatus.FAILED:
            raise self.error
        raise RuntimeError(f"Job ended with {self.status}")

    async def cancel_or_finish(self):
        if self.status == JobStatus.PENDING:
            self.status = JobStatus.CANCELLED
        elif self.status == JobStatus.RUNNING and self._task is not None:
            self._task.cancel()
        await self.event.wait()

    def add_callback(self, callback: Callable[[Self], None | Awaitable[None]]) -> None:
        if self.status != JobStatus.PENDING:
            raise RuntimeError(
                f"Cannot add callback: job {self.id} is not pending (current status: {self.status})."
            )

        if self.callback is not None:
            raise RuntimeError(
                f"Cannot add callback: job {self.id} already has a callback attached."
            )

        self.callback = callback

    def remove_callback(self) -> Callable[[Self], None | Awaitable[None]]:
        if self.status != JobStatus.PENDING:
            raise RuntimeError(
                f"Cannot remove callback: job {self.id} is not pending (current status: {self.status})."
            )

        if self.callback is None:
            raise RuntimeError(
                f"Cannot remove callback: no callback is attached to job {self.id}."
            )

        cb = self.callback
        self.callback = None
        return cb


async def runner(job: Job[P, T]) -> T:
    if inspect.iscoroutinefunction(job.fn):
        return await job.fn(*job.args, **job.kwargs)
    return await asyncio.to_thread(job.fn, *job.args, **job.kwargs)


class JobRegistry(Generic[P, T]):
    def __init__(self):
        self.jobs: dict[str, Job[P, T]] = {}
        self.queue: asyncio.Queue[Job[P, T]] = asyncio.Queue()

    def add(self, job: Job[P, T]):
        self.jobs[job.id] = job

    def get(self, job_id: str) -> Job[P, T] | None:
        return self.jobs.get(job_id)

    async def submit(self, job: Job[P, T]):
        self.add(job)
        await self.queue.put(job)

    def remove(self, job_id: str):
        self.jobs.pop(job_id, None)

    async def worker(self):
        while True:
            try:
                job = await self.queue.get()
            except asyncio.QueueShutDown:
                break

            if job.status == JobStatus.CANCELLED:
                job.event.set()
                self.queue.task_done()
                continue

            job.status = JobStatus.RUNNING

            try:
                job._task = asyncio.create_task(runner(job))  # pyright: ignore[reportPrivateUsage]
                job.result = await job._task  # pyright: ignore[reportPrivateUsage]
                job.status = JobStatus.DONE

            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
                continue

            except Exception as e:
                job.error = e
                job.status = JobStatus.FAILED

            finally:
                if job.callback is not None:
                    try:
                        if inspect.iscoroutinefunction(job.callback):
                            await job.callback(job)
                        await asyncio.to_thread(job.callback, job)
                    except Exception as e:
                        job.callback_error = e
                job.event.set()
                self.queue.task_done()
