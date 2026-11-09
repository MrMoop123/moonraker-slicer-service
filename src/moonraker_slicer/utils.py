"""Utility helpers for the slicing service."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any


def generate_job_id() -> str:
    """Generate a unique job identifier."""
    return f"slice_{secrets.token_hex(6)}"


def resolve_and_validate_path(path: str, allowed_base: Path, description: str = "path") -> Path:
    """Resolve a path and verify it stays within the allowed base directory.

    Raises ValueError if path traversal is detected or resolved path is outside allowed_base.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = allowed_base / p
    resolved = p.resolve()

    if not str(resolved).startswith(str(allowed_base.resolve())):
        raise ValueError(f"Security: {description} escapes allowed base directory")

    return resolved


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    # Strip directory components and dangerous characters
    name = Path(filename).name
    # Remove .. sequences
    name = name.replace("..", "_")
    safe = "".join(c for c in name if c.isalnum() or c in "-_. ")
    return safe or "unnamed"


def format_filesize(bytes_val: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(bytes_val) < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def extract_progress_from_line(line: str) -> int | None:
    """Extract progress percentage from a slicer output line.

    Looks for patterns like '45%' or '[====>           ] 45%'.
    """
    line = line.strip()
    if "%" not in line:
        return None

    # Try to find a number followed by %
    parts = line.split("%")
    if len(parts) >= 2:
        # Take the last number before the % sign
        before_percent = parts[-2].strip()
        # Try to extract a number from the segment
        import re
        match = re.search(r"(\d+)", before_percent)
        if match:
            val = int(match.group(1))
            if 0 <= val <= 100:
                return val

    return None


def cleanup_temp_files(directory: Path, pattern: str = "mkslice_override_*", max_age_seconds: int = 3600) -> int:
    """Remove temporary files older than max_age_seconds.

    Returns the number of files removed.
    """
    removed = 0
    now = Path().stat().st_mtime

    if not directory.exists():
        return 0

    for temp_file in directory.glob(pattern):
        try:
            file_age = now - temp_file.stat().st_mtime
            if file_age > max_age_seconds:
                temp_file.unlink(missing_ok=True)
                removed += 1
        except OSError:
            pass

    return removed
