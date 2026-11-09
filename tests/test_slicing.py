"""Tests for the slicing module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moonraker_slicer.slicing import SlicingError, slice_file


@pytest.fixture
def tmp_model(tmp_path: Path) -> Path:
    model = tmp_path / "cube.stl"
    model.write_bytes(b"solid test\nendsolid test\n")
    return model


@pytest.fixture
def tmp_profile_dir(tmp_path: Path) -> Path:
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "printer_settings.ini").write_text(
        "[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n"
    )
    (profile / "filament_settings.ini").write_text(
        "[filament]\ntemperature = 210\n"
    )
    return profile


@pytest.fixture
def mock_slicer(tmp_path: Path) -> Path:
    slicer = tmp_path / "orca-slicer"
    slicer.write_text("#!/bin/bash\necho '45%'\necho '100%'\nexit 0\n")
    slicer.chmod(0o755)
    return slicer


@pytest.mark.asyncio
async def test_slice_file_success(tmp_model: Path, tmp_profile_dir: Path, mock_slicer: Path, tmp_path: Path) -> None:
    output = tmp_path / "output.gcode"
    progress_log: list[tuple[int, str]] = []

    result = await slice_file(
        model_path=tmp_model,
        profile_dir=tmp_profile_dir,
        output_path=output,
        slicer_binary=mock_slicer,
        on_progress=lambda p, m: progress_log.append((p, m)),
    )

    assert result == output
    assert progress_log  # Progress callbacks were called


@pytest.mark.asyncio
async def test_slice_file_model_not_found(tmp_profile_dir: Path, mock_slicer: Path, tmp_path: Path) -> None:
    with pytest.raises(SlicingError, match="Model file not found"):
        await slice_file(
            model_path=Path("/nonexistent/model.stl"),
            profile_dir=tmp_profile_dir,
            output_path=tmp_path / "out.gcode",
            slicer_binary=mock_slicer,
        )


@pytest.mark.asyncio
async def test_slice_file_slicer_not_found(tmp_model: Path, tmp_profile_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(SlicingError, match="Slicer binary not found"):
        await slice_file(
            model_path=tmp_model,
            profile_dir=tmp_profile_dir,
            output_path=tmp_path / "out.gcode",
            slicer_binary=Path("/nonexistent/slicer"),
        )


@pytest.mark.asyncio
async def test_slice_file_with_overrides(mock_slicer: Path, tmp_profile_dir: Path, tmp_path: Path) -> None:
    tmp_model = tmp_path / "model.stl"
    tmp_model.write_bytes(b"solid test\n")

    output = tmp_path / "output.gcode"
    await slice_file(
        model_path=tmp_model,
        profile_dir=tmp_profile_dir,
        output_path=output,
        slicer_binary=mock_slicer,
        overrides={"layer_height": "0.2", "infill_percentage": "20"},
    )


@pytest.mark.asyncio
async def test_slice_file_stderr_on_error(tmp_path: Path) -> None:
    # Create a mock slicer that fails
    bad_slicer = tmp_path / "bad-slicer"
    bad_slicer.write_text("#!/bin/bash\necho 'Error: model corrupted' >&2\nexit 1\n")
    bad_slicer.chmod(0o755)

    tmp_model = tmp_path / "model.stl"
    tmp_model.write_bytes(b"solid test\n")

    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "printer_settings.ini").write_text("[printer]\nnozzle_diameter = 0.4\n")
    (profile / "filament_settings.ini").write_text("[filament]\n")

    with pytest.raises(SlicingError) as exc_info:
        await slice_file(
            model_path=tmp_model,
            profile_dir=profile,
            output_path=tmp_path / "out.gcode",
            slicer_binary=bad_slicer,
        )

    assert "Error: model corrupted" in str(exc_info.value.stderr)
