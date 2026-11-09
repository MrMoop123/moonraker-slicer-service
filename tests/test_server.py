"""Tests for the server API."""

import pytest
from fastapi.testclient import TestClient

from moonraker_slicer.server import create_app


@pytest.fixture
def app(tmp_path) -> TestClient:
    config = {
        "host": "127.0.0.1",
        "port": 8765,
        "slicer_binary": str(tmp_path / "nonexistent_slicer"),
        "profiles_dir": str(tmp_path / "profiles"),
        "output_dir": str(tmp_path / "output"),
        "max_concurrent_jobs": 2,
        "job_retention_days": 30,
    }
    return TestClient(create_app(config))


def test_health(app: TestClient) -> None:
    resp = app.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "slicer_available" in data
    assert "jobs_queued" in data


def test_list_profiles_empty(app: TestClient) -> None:
    resp = app.get("/api/profiles")
    assert resp.status_code == 200
    assert resp.json()["profiles"] == []


def test_upload_profile(app: TestClient) -> None:
    resp = app.post(
        "/api/profiles/upload",
        data={"profile_name": "test"},
        files=[
            ("files", ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n")),
            ("files", ("filament_settings.ini", b"[filament]\ntemperature = 210\n")),
        ],
    )
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "ok"


def test_get_profile_not_found(app: TestClient) -> None:
    resp = app.get("/api/profiles/nonexistent/metadata")
    assert resp.status_code == 404


def test_slice_requires_model_file(app: TestClient) -> None:
    resp = app.post("/api/slice", json={"profile_name": "test"})
    assert resp.status_code == 422


def test_slice_requires_profile_name(app: TestClient) -> None:
    resp = app.post("/api/slice", json={"model_file": "cube.stl"})
    assert resp.status_code == 422


def test_list_jobs(app: TestClient) -> None:
    resp = app.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert "total" in data


def test_job_status_summary(app: TestClient) -> None:
    resp = app.get("/api/jobs/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "queued" in data
    assert "running" in data
