"""Async job queue for managing slicing tasks."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from moonraker_slicer.models import JobInfo, JobListResponse, JobStatus
from moonraker_slicer.slicing import SlicingError, slice_file
from moonraker_slicer.utils import generate_job_id

logger = logging.getLogger("moonraker_slicer.job_queue")


class JobQueue:
    """Manages slicing job lifecycle."""

    def __init__(
        self,
        max_concurrent: int = 2,
        output_dir: str | Path = "/home/pi/gcode_files",
        slicer_binary: str | Path = "/usr/local/bin/orca-slicer",
        profiles_dir: str | Path = "~/.config/moonraker-slicer/profiles",
        retention_days: int = 30,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.output_dir = Path(output_dir).expanduser()
        self.slicer_binary = Path(slicer_binary).expanduser()
        self.profiles_dir = Path(profiles_dir).expanduser()
        self.retention_days = retention_days

        self._jobs: dict[str, dict[str, Any]] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._processor_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the job processor."""
        self._running = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._processor_task = asyncio.create_task(self._process_queue())
        logger.info("Job queue started (max_concurrent=%d)", self.max_concurrent)

    async def stop(self) -> None:
        """Stop the job processor gracefully."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Job queue stopped")

    async def submit(
        self,
        model_file: str,
        profile_name: str,
        output_file: str | None = None,
        settings: dict[str, Any] | None = None,
        output_directory: str | None = None,
    ) -> tuple[str, str]:
        """Submit a new slicing job.

        Returns:
            (job_id, message) tuple.
        """
        job_id = generate_job_id()

        # Generate output filename if not provided
        if not output_file:
            model_name = Path(model_file).stem
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
            output_file = f"{model_name}_{timestamp}.gcode"

        # Determine output directory
        out_dir = Path(output_directory).expanduser() if output_directory else self.output_dir
        out_path = out_dir / output_file

        job: dict[str, Any] = {
            "job_id": job_id,
            "status": JobStatus.QUEUED,
            "model_file": model_file,
            "profile_name": profile_name,
            "output_file": str(out_path),
            "output_dir": str(out_dir),
            "settings": settings or {},
            "progress": 0,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
        }

        self._jobs[job_id] = job
        await self._queue.put(job_id)

        logger.info("Job '%s' submitted: %s with profile '%s'", job_id, model_file, profile_name)
        return job_id, "Slicing job queued"

    async def _process_queue(self) -> None:
        """Background task that processes queued jobs."""
        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                asyncio.create_task(self._run_job(job_id))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error dequeuing job: %s", e)

    async def _run_job(self, job_id: str) -> None:
        """Execute a single job with concurrency control."""
        if job_id not in self._jobs:
            return

        async with self._semaphore:
            job = self._jobs[job_id]
            job["status"] = JobStatus.RUNNING
            job["started_at"] = datetime.now(timezone.utc)
            job["progress"] = 0

            logger.info("Job '%s' started", job_id)

            try:
                model_path = Path(job["model_file"])
                profile_dir = self.profiles_dir / job["profile_name"]
                output_path = Path(job["output_file"])

                def on_progress(progress: int, message: str) -> None:
                    job["progress"] = progress

                await slice_file(
                    model_path=model_path,
                    profile_dir=profile_dir,
                    output_path=output_path,
                    slicer_binary=self.slicer_binary,
                    overrides=job.get("settings"),
                    on_progress=on_progress,
                )

                job["status"] = JobStatus.COMPLETED
                job["completed_at"] = datetime.now(timezone.utc)
                job["progress"] = 100
                logger.info("Job '%s' completed successfully", job_id)

            except SlicingError as e:
                job["status"] = JobStatus.FAILED
                job["error"] = str(e)
                job["completed_at"] = datetime.now(timezone.utc)
                logger.error("Job '%s' failed: %s", job_id, e)
            except asyncio.CancelledError:
                job["status"] = JobStatus.FAILED
                job["error"] = "Job cancelled"
                job["completed_at"] = datetime.now(timezone.utc)
                raise
            except Exception as e:
                job["status"] = JobStatus.FAILED
                job["error"] = f"Unexpected error: {e}"
                job["completed_at"] = datetime.now(timezone.utc)
                logger.error("Job '%s' unexpected error: %s", job_id, e, exc_info=True)

    def get_job(self, job_id: str) -> JobInfo | None:
        """Get job info by ID."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return JobInfo(**job)

    def list_jobs(self, limit: int = 50) -> JobListResponse:
        """List recent jobs."""
        jobs = sorted(
            self._jobs.values(),
            key=lambda j: j.get("created_at", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        limited = jobs[:limit]
        return JobListResponse(
            jobs=[JobInfo(**j) for j in limited],
            total=len(self._jobs),
            limit=limit,
        )

    async def cleanup_old_jobs(self) -> int:
        """Remove jobs older than retention period."""
        cutoff = datetime.now(timezone.utc).timestamp() - (self.retention_days * 86400)
        to_remove = [
            jid for jid, job in self._jobs.items()
            if job.get("completed_at") and job["completed_at"].timestamp() < cutoff
        ]
        for jid in to_remove:
            del self._jobs[jid]
            logger.debug("Removed old job: %s", jid)
        return len(to_remove)

    @property
    def queued_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j["status"] == JobStatus.QUEUED)

    @property
    def running_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j["status"] == JobStatus.RUNNING)
