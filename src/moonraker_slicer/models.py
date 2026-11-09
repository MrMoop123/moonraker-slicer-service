"""Pydantic models for request/response validation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pathlib import Path


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SlicingRequest(BaseModel):
    model_file: str = Field(..., description="Path or filename of the 3D model (STL/OBJ/AMF)")
    profile_name: str = Field(..., description="Name of the slicer profile to use")
    output_file: str | None = Field(None, description="Output G-code filename (auto-generated if omitted)")
    settings: dict[str, Any] = Field(default_factory=dict, description="Runtime slicing overrides")
    output_directory: str | None = Field(None, description="Output directory (defaults to config output_dir)")

    @field_validator("model_file")
    @classmethod
    def validate_model_file(cls, v: str) -> str:
        valid_extensions = {".stl", ".obj", ".amf"}
        suffix = Path(v).suffix.lower()
        if suffix not in valid_extensions:
            raise ValueError(f"Model file must have extension {', '.join(sorted(valid_extensions))}, got '{suffix}'")
        return v


class JobResponse(BaseModel):
    status: JobStatus
    job_id: str
    message: str = ""


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    model_file: str
    profile_name: str
    output_file: str | None = None
    progress: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobInfo]
    total: int = 0
    limit: int = 50


class ProfileMetadata(BaseModel):
    name: str
    files: list[str]
    updated: datetime


class ProfileInfo(BaseModel):
    name: str
    files: list[str]
    updated: datetime


class ProfileListResponse(BaseModel):
    profiles: list[ProfileInfo]


class ProfileUploadResponse(BaseModel):
    status: str
    profile: ProfileInfo


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    slicer_available: bool
    slicer_binary: str
    jobs_queued: int
    jobs_running: int
