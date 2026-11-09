"""Tests for the job queue."""

from pathlib import Path

import pytest

from moonraker_slicer.job_queue import JobQueue
from moonraker_slicer.models import JobStatus


@pytest.fixture
def job_queue(tmp_path: Path) -> JobQueue:
    return JobQueue(
        max_concurrent=2,
        output_dir=str(tmp_path / "output"),
        slicer_binary=str(tmp_path / "nonexistent_slicer"),
        profiles_dir=str(tmp_path / "profiles"),
    )


@pytest.mark.asyncio
async def test_submit_job(job_queue: JobQueue) -> None:
    job_id, msg = await job_queue.submit(
        model_file="cube.stl",
        profile_name="test",
    )
    assert job_id.startswith("slice_")
    assert "queued" in msg.lower()

    job = job_queue.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.model_file == "cube.stl"
    assert job.profile_name == "test"


@pytest.mark.asyncio
async def test_submit_job_with_output_file(job_queue: JobQueue) -> None:
    job_id, _ = await job_queue.submit(
        model_file="cube.stl",
        profile_name="test",
        output_file="custom_output.gcode",
    )

    job = job_queue.get_job(job_id)
    assert job is not None
    assert job.output_file.endswith("custom_output.gcode")


@pytest.mark.asyncio
async def test_submit_job_custom_output_dir(job_queue: JobQueue) -> None:
    job_id, _ = await job_queue.submit(
        model_file="cube.stl",
        profile_name="test",
        output_directory="/tmp/custom",
    )

    job = job_queue.get_job(job_id)
    assert job is not None
    assert "/tmp/custom" in job.output_file


@pytest.mark.asyncio
async def test_list_jobs(job_queue: JobQueue) -> None:
    # Submit a few jobs
    await job_queue.submit(model_file="a.stl", profile_name="test")
    await job_queue.submit(model_file="b.stl", profile_name="test")

    result = job_queue.list_jobs(limit=10)
    assert result.total >= 2
    assert len(result.jobs) >= 2


@pytest.mark.asyncio
async def test_job_not_found(job_queue: JobQueue) -> None:
    job = job_queue.get_job("slice_nonexistent")
    assert job is None


@pytest.mark.asyncio
async def test_start_stop(job_queue: JobQueue) -> None:
    await job_queue.start()
    await job_queue.stop()
    # Should not raise
