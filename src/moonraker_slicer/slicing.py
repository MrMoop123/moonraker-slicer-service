"""Core slicing logic - wraps the headless slicer CLI."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from moonraker_slicer.utils import extract_progress_from_line

logger = logging.getLogger("moonraker_slicer.slicing")


class SlicingError(Exception):
    """Raised when slicing fails."""

    def __init__(self, message: str, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


async def slice_file(
    model_path: Path,
    profile_dir: Path,
    output_path: Path,
    slicer_binary: Path,
    overrides: dict | None = None,
    on_progress: callable | None = None,
) -> Path:
    """Execute the slicer in headless mode.

    Args:
        model_path: Path to the input 3D model file.
        profile_dir: Directory containing printer_settings.ini and filament_settings.ini.
        output_path: Where to write the output G-code file.
        slicer_binary: Path to the slicer executable.
        overrides: Optional runtime settings to override profile values.
        on_progress: Optional callback(progress: int, message: str) for progress updates.

    Returns:
        Path to the output G-code file.

    Raises:
        SlicingError: If the slicer fails.
    """
    # Validate inputs
    if not model_path.exists():
        raise SlicingError(f"Model file not found: {model_path}")
    if not slicer_binary.exists():
        raise SlicingError(f"Slicer binary not found: {slicer_binary}")
    if not profile_dir.exists():
        raise SlicingError(f"Profile directory not found: {profile_dir}")

    # Build command
    cmd = [
        str(slicer_binary),
        "--export-gcode", str(output_path),
        "--load", str(profile_dir / "printer_settings.ini"),
        "--load", str(profile_dir / "filament_settings.ini"),
        "--progress",
        "--verbosity", "0",
        str(model_path),
    ]

    # Handle runtime overrides
    temp_override = None
    if overrides:
        temp_override = _write_temp_override(overrides)
        cmd += ["--load", temp_override]

    logger.info("Executing: %s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        progress = 0
        # Read stdout line by line for progress updates
        if proc.stdout:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode().strip()
                prog = extract_progress_from_line(text)
                if prog is not None and prog != progress:
                    progress = prog
                    logger.debug("Progress: %d%%", progress)
                    if on_progress:
                        on_progress(progress, text)

        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode() if stdout else ""
        stderr_text = stderr.decode() if stderr else ""

        if proc.returncode != 0:
            raise SlicingError(
                f"Slicer failed (exit {proc.returncode})",
                stdout=stdout_text,
                stderr=stderr_text,
            )

        if on_progress:
            on_progress(100, "Slicing complete")

        logger.info("Slicing completed successfully, output: %s", output_path)
        return output_path

    except SlicingError:
        raise
    except FileNotFoundError:
        raise SlicingError(f"Slicer binary not found or not executable: {slicer_binary}")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        raise SlicingError(f"Unexpected error during slicing: {e}")
    finally:
        # Clean up temp override file
        if temp_override:
            try:
                Path(temp_override).unlink(missing_ok=True)
            except OSError:
                pass


def _write_temp_override(overrides: dict) -> str:
    """Write runtime overrides to a temporary INI and return its path."""
    content = "[print]\n"
    for key, value in overrides.items():
        content += f"{key} = {value}\n"

    fd, path = tempfile.mkstemp(suffix=".ini", prefix="mkslice_override_")
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)

    return path
