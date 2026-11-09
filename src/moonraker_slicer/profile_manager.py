"""Profile management - upload, validate, and store slicer profiles."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from moonraker_slicer.models import ProfileInfo, ProfileListResponse, ProfileUploadResponse
from moonraker_slicer.utils import sanitize_filename

logger = logging.getLogger("moonraker_slicer.profile_manager")

REQUIRED_KEYS = {
    "nozzle_diameter": "Nozzle diameter (mm)",
    "vertical_limit": "Vertical build limit (mm)",
    "travel_speed": "Travel speed (mm/s)",
}

VALID_EXTENSIONS = {".ini", ".txt"}


class ProfileManager:
    """Manages slicer profile storage and validation."""

    def __init__(self, profiles_dir: str | Path) -> None:
        self.profiles_dir = Path(profiles_dir).expanduser()
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, name: str) -> Path:
        """Get the directory path for a profile by name."""
        safe_name = sanitize_filename(name)
        return self.profiles_dir / safe_name

    def _metadata_path(self, name: str) -> Path:
        """Get the metadata JSON path for a profile."""
        return self._profile_path(name) / "metadata.json"

    def list_profiles(self) -> list[ProfileInfo]:
        """List all available profiles."""
        profiles: list[ProfileInfo] = []

        for profile_dir in sorted(self.profiles_dir.iterdir()):
            if not profile_dir.is_dir():
                continue

            metadata_path = profile_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    data = json.load(f)
                profiles.append(ProfileInfo(
                    name=data["name"],
                    files=data["files"],
                    updated=datetime.fromisoformat(data["updated"]),
                ))
            else:
                # Profile without metadata - infer from directory
                files = [f.name for f in profile_dir.iterdir()
                         if f.is_file() and f.suffix in VALID_EXTENSIONS]
                if files:
                    mtime = profile_dir.stat().st_mtime
                    profiles.append(ProfileInfo(
                        name=profile_dir.name,
                        files=files,
                        updated=datetime.fromtimestamp(mtime, tz=timezone.utc),
                    ))

        return profiles

    def get_profile(self, name: str) -> ProfileInfo | None:
        """Get profile info by name, or None if not found."""
        profile_dir = self._profile_path(name)
        if not profile_dir.exists():
            return None

        metadata_path = profile_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                data = json.load(f)
            return ProfileInfo(
                name=data["name"],
                files=data["files"],
                updated=datetime.fromisoformat(data["updated"]),
            )

        files = [f.name for f in profile_dir.iterdir() if f.is_file()]
        return ProfileInfo(
            name=profile_dir.name,
            files=files,
            updated=datetime.fromtimestamp(profile_dir.stat().st_mtime, tz=timezone.utc),
        )

    def upload_profile(
        self,
        name: str,
        files: list[tuple[str, bytes]],
    ) -> ProfileUploadResponse:
        """Upload and store a slicer profile.

        Args:
            name: Profile name.
            files: List of (filename, content_bytes) tuples.

        Returns:
            ProfileUploadResponse with details of the stored profile.
        """
        profile_dir = self._profile_path(name)

        # Clean up existing profile directory if it exists
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        profile_dir.mkdir(parents=True)

        saved_files: list[str] = []
        warnings: list[str] = []
        sanitized_name = sanitize_filename(name)

        for filename, content in files:
            safe_name = sanitize_filename(filename)

            # Validate extension
            if Path(safe_name).suffix not in VALID_EXTENSIONS:
                warnings.append(f"Skipping file with unsupported extension: {filename}")
                continue

            file_path = profile_dir / safe_name
            file_path.write_bytes(content)
            saved_files.append(safe_name)

            # Check for required keys in printer_settings.ini
            if safe_name == "printer_settings.ini":
                _validate_printersettings(file_path, warnings)

        if not saved_files:
            shutil.rmtree(profile_dir)
            raise ValueError("No valid profile files were uploaded")

        # Write metadata
        metadata = {
            "name": sanitized_name,
            "files": saved_files,
            "updated": datetime.now(timezone.utc).isoformat(),
            "warnings": warnings,
        }
        metadata_path = profile_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        logger.info("Profile '%s' uploaded with %d files", name, len(saved_files))

        return ProfileUploadResponse(
            status="ok",
            profile=ProfileInfo(
                name=sanitized_name,
                files=saved_files,
                updated=datetime.now(timezone.utc),
            ),
        )

    def delete_profile(self, name: str) -> bool:
        """Delete a profile by name. Returns True if deleted, False if not found."""
        profile_dir = self._profile_path(name)
        if not profile_dir.exists():
            return False

        shutil.rmtree(profile_dir)
        logger.info("Profile '%s' deleted", name)
        return True

    def validate_profile(self, name: str) -> dict[str, Any]:
        """Validate a profile's required keys.

        Returns:
            dict with 'valid' bool and 'warnings' list.
        """
        profile_dir = self._profile_path(name)
        warnings: list[str] = []

        printer_ini = profile_dir / "printer_settings.ini"
        if printer_ini.exists():
            _validate_printersettings(printer_ini, warnings)

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "profile_dir": str(profile_dir),
            "files": [f.name for f in profile_dir.iterdir() if f.is_file()],
        }


def _validate_printersettings(path: Path, warnings: list[str]) -> None:
    """Check printer_settings.ini for required keys and add warnings."""
    try:
        content = path.read_text()
        for key, desc in REQUIRED_KEYS.items():
            if key not in content:
                warnings.append(f"{desc} ('{key}') not found in printer_settings.ini")
    except OSError as e:
        warnings.append(f"Could not read printer_settings.ini: {e}")
