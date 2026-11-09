"""FastAPI HTTP server exposing the slicing service API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, UploadFile

from moonraker_slicer.job_queue import JobQueue
from moonraker_slicer.models import HealthResponse
from moonraker_slicer.profile_manager import ProfileManager
from moonraker_slicer.slicing import SlicingError

logger = logging.getLogger("moonraker_slicer.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service startup and shutdown."""
    job_queue: JobQueue = app.state.job_queue
    await job_queue.start()
    logger.info("Service initialized")
    yield
    await job_queue.stop()
    logger.info("Service shut down")


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    config = config or {}

    output_dir = config.get("output_dir", "/home/pi/gcode_files")
    profiles_dir = config.get("profiles_dir", "~/.config/moonraker-slicer/profiles")
    slicer_binary = config.get("slicer_binary", "/usr/local/bin/orca-slicer")
    max_concurrent = config.get("max_concurrent_jobs", 2)
    retention_days = config.get("job_retention_days", 30)

    job_queue = JobQueue(
        max_concurrent=max_concurrent,
        output_dir=output_dir,
        slicer_binary=slicer_binary,
        profiles_dir=profiles_dir,
        retention_days=retention_days,
    )
    profile_manager = ProfileManager(profiles_dir)

    app = FastAPI(
        title="Moonraker Slicing Service",
        version="0.1.0",
        description="Moonraker-compatible slicing service for headless 3D printing",
        lifespan=lifespan,
    )

    app.state.config = config
    app.state.job_queue = job_queue
    app.state.profile_manager = profile_manager

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes. Specific routes must come before parameterized ones."""

    # --- Health ---

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        jq = app.state.job_queue
        sb = Path(app.state.config.get("slicer_binary", ""))
        return HealthResponse(
            status="ok",
            slicer_available=sb.exists(),
            slicer_binary=str(sb),
            jobs_queued=jq.queued_count,
            jobs_running=jq.running_count,
        )

    # --- Profile endpoints ---

    @app.get("/api/profiles")
    async def list_profiles() -> dict[str, Any]:
        pm = app.state.profile_manager
        return {"profiles": [p.model_dump() for p in pm.list_profiles()]}

    @app.get("/api/profiles/{name}/metadata")
    async def get_profile_metadata(name: str) -> dict[str, Any]:
        pm = app.state.profile_manager
        profile = pm.get_profile(name)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
        return profile.model_dump()

    @app.post("/api/profiles/upload")
    async def upload_profile(
        profile_name: str = Form(..., description="Profile name"),
        files: list[UploadFile] = Form(..., description="Profile INI files"),
    ) -> dict[str, Any]:
        pm = app.state.profile_manager
        file_data = []
        try:
            for f in files:
                content = await f.read()
                file_data.append((f.filename or "unnamed", content))
            response = pm.upload_profile(profile_name, file_data)
            return response.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("Profile upload failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/profiles/{name}")
    async def delete_profile(name: str) -> dict[str, str]:
        pm = app.state.profile_manager
        if not pm.delete_profile(name):
            raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
        return {"status": "ok", "message": f"Profile '{name}' deleted"}

    @app.get("/api/profiles/{name}/validate")
    async def validate_profile(name: str) -> dict[str, Any]:
        pm = app.state.profile_manager
        return pm.validate_profile(name)

    # --- Slicing endpoint ---

    @app.post("/api/slice")
    async def slice_endpoint(request: dict[str, Any]) -> dict[str, Any]:
        """Submit a slicing job."""
        jq = app.state.job_queue
        pm = app.state.profile_manager

        model_file = request.get("model_file")
        profile_name = request.get("profile_name")

        if not model_file:
            raise HTTPException(status_code=422, detail="'model_file' is required")
        if not profile_name:
            raise HTTPException(status_code=422, detail="'profile_name' is required")
        if not pm.get_profile(profile_name):
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")

        try:
            job_id, message = await jq.submit(
                model_file=model_file,
                profile_name=profile_name,
                output_file=request.get("output_file"),
                settings=request.get("settings", {}),
                output_directory=request.get("output_directory"),
            )
            return {"status": "accepted", "job_id": job_id, "message": message}
        except SlicingError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # --- Job endpoints ---

    @app.get("/api/jobs")
    async def list_jobs(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        jq = app.state.job_queue
        return jq.list_jobs(limit=limit).model_dump()

    @app.get("/api/jobs/status")
    async def job_status_summary() -> dict[str, Any]:
        jq = app.state.job_queue
        return {
            "queued": jq.queued_count,
            "running": jq.running_count,
            "total": len(jq._jobs),
        }

    @app.get("/api/jobs/{job_id}")
    async def get_job_status(job_id: str) -> dict[str, Any]:
        jq = app.state.job_queue
        job = jq.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        return job.model_dump()
