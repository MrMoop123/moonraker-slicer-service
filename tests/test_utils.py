"""Tests for utility functions."""

from pathlib import Path

import pytest

from moonraker_slicer.utils import (
    extract_progress_from_line,
    format_filesize,
    generate_job_id,
    resolve_and_validate_path,
    sanitize_filename,
)


def test_generate_job_id_uniqueness() -> None:
    ids = {generate_job_id() for _ in range(100)}
    assert len(ids) == 100


def test_generate_job_id_format() -> None:
    for _ in range(20):
        job_id = generate_job_id()
        assert job_id.startswith("slice_")
        assert len(job_id) == 18  # "slice_" + 12 hex chars


def test_sanitize_filename() -> None:
    assert sanitize_filename("../etc/passwd") == "passwd"
    assert sanitize_filename("my-file_v2.1.stl") == "my-file_v2.1.stl"
    assert sanitize_filename("bad<>file") == "badfile"
    assert sanitize_filename("") == "unnamed"


def test_format_filesize() -> None:
    assert format_filesize(0) == "0.0 B"
    assert format_filesize(1023) == "1023.0 B"
    assert "KB" in format_filesize(1024)
    assert "MB" in format_filesize(1_048_576)
    assert "GB" in format_filesize(1_073_741_824)


def test_extract_progress_from_line() -> None:
    assert extract_progress_from_line("45%") == 45
    assert extract_progress_from_line("[====>           ] 72%") == 72
    assert extract_progress_from_line("No progress here") is None
    assert extract_progress_from_line("150%") is None  # out of range


def test_resolve_and_validate_path_within(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    sub = allowed / "sub"

    result = resolve_and_validate_path("sub/file.txt", allowed)
    assert result == sub / "file.txt"


def test_resolve_and_validate_path_traversal(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(ValueError, match="escapes allowed"):
        resolve_and_validate_path("../etc", allowed)


def test_resolve_and_validate_absolute_outside(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(ValueError, match="escapes allowed"):
        resolve_and_validate_path("/etc/passwd", allowed)
