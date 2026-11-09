"""Tests for the profile manager module."""

from pathlib import Path

import pytest

from moonraker_slicer.profile_manager import ProfileManager


@pytest.fixture
def profile_manager(tmp_path: Path) -> ProfileManager:
    return ProfileManager(tmp_path / "profiles")


def test_list_empty(profile_manager: ProfileManager) -> None:
    profiles = profile_manager.list_profiles()
    assert profiles == []


def test_upload_and_list(profile_manager: ProfileManager) -> None:
    profile_manager.upload_profile(
        "test_profile",
        [
            ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n"),
            ("filament_settings.ini", b"[filament]\ntemperature = 210\n"),
        ],
    )

    profiles = profile_manager.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "test_profile"
    assert "printer_settings.ini" in profiles[0].files
    assert "filament_settings.ini" in profiles[0].files


def test_get_profile(profile_manager: ProfileManager) -> None:
    profile_manager.upload_profile(
        "my_profile",
        [
            ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n"),
        ],
    )

    profile = profile_manager.get_profile("my_profile")
    assert profile is not None
    assert profile.name == "my_profile"


def test_get_profile_not_found(profile_manager: ProfileManager) -> None:
    profile = profile_manager.get_profile("nonexistent")
    assert profile is None


def test_delete_profile(profile_manager: ProfileManager) -> None:
    profile_manager.upload_profile(
        "to_delete",
        [
            ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\n"),
        ],
    )

    assert profile_manager.delete_profile("to_delete") is True
    assert profile_manager.get_profile("to_delete") is None


def test_delete_profile_not_found(profile_manager: ProfileManager) -> None:
    assert profile_manager.delete_profile("nonexistent") is False


def test_upload_invalid_extension(profile_manager: ProfileManager) -> None:
    with pytest.raises(ValueError, match="No valid profile files"):
        profile_manager.upload_profile(
            "bad_profile",
            [("readme.md", b"Some readme")],
        )


def test_validate_profile_with_warnings(profile_manager: ProfileManager) -> None:
    profile_manager.upload_profile(
        "incomplete",
        [
            ("printer_settings.ini", b"[printer]\n# missing required keys\n"),
        ],
    )

    result = profile_manager.validate_profile("incomplete")
    assert result["valid"] is False
    assert len(result["warnings"]) > 0


def test_validate_valid_profile(profile_manager: ProfileManager) -> None:
    profile_manager.upload_profile(
        "complete",
        [
            ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n"),
            ("filament_settings.ini", b"[filament]\ntemperature = 210\n"),
        ],
    )

    result = profile_manager.validate_profile("complete")
    assert result["valid"] is True


def test_profile_sanitizes_name(tmp_path: Path) -> None:
    pm = ProfileManager(tmp_path / "profiles")
    pm.upload_profile(
        "../tricky",
        [
            ("printer_settings.ini", b"[printer]\nnozzle_diameter = 0.4\nvertical_limit = 250\ntravel_speed = 200\n"),
        ],
    )

    profiles = pm.list_profiles()
    assert len(profiles) == 1
    assert ".." not in profiles[0].name
