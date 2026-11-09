"""Moonraker plugin - optional JSON-RPC extension for Moonraker integration."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("moonraker_slicer.moonraker_plugin")

# Optional dependency - only import if moonraker is available
try:
    from moonraker.api.component_registration import components
    from moonraker.components.websockets import WebSocketsManager
    _MOONRAKER_AVAILABLE = True
except ImportError:
    _MOONRAKER_AVAILABLE = False


class SlicerComponent:
    """Moonraker component for the slicing service.

    This allows direct JSON-RPC calls from Mainsail/Fluidd:
      - slicer.slice
      - slicer.job_status
      - slicer.list_profiles
      - slicer.list_jobs
    """

    def __init__(self, config: dict[str, Any]) -> None:
        if not _MOONRAKER_AVAILABLE:
            logger.warning("Moonraker not installed - plugin disabled")
            return

        self.config = config
        self.slicer_url = config.get("slicer_url", "http://localhost:7125")

    async def register(self) -> None:
        """Register JSON-RPC endpoints with Moonraker."""
        if not _MOONRAKER_AVAILABLE:
            return

        @components.on("websockets:register_message_handlers")
        def _register(websocket: WebSocketsManager) -> None:
            websocket.register_json_rpc_method(
                "slicer.slice", self._handle_slice
            )
            websocket.register_json_rpc_method(
                "slicer.job_status", self._handle_job_status
            )
            websocket.register_json_rpc_method(
                "slicer.list_profiles", self._handle_list_profiles
            )
            websocket.register_json_rpc_method(
                "slicer.list_jobs", self._handle_list_jobs
            )

    async def _handle_slice(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle slicer.slice JSON-RPC call."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.slicer_url}/api/slice",
                    json=params or {},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("slicer.slice failed: %s", e)
            return {"status": "error", "message": str(e)}

    async def _handle_job_status(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle slicer.job_status JSON-RPC call."""
        import httpx
        job_id = (params or {}).get("job_id", "")
        if not job_id:
            return {"status": "error", "message": "job_id is required"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.slicer_url}/api/jobs/{job_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("slicer.job_status failed: %s", e)
            return {"status": "error", "message": str(e)}

    async def _handle_list_profiles(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle slicer.list_profiles JSON-RPC call."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.slicer_url}/api/profiles")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("slicer.list_profiles failed: %s", e)
            return {"status": "error", "message": str(e)}

    async def _handle_list_jobs(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle slicer.list_jobs JSON-RPC call."""
        import httpx
        try:
            limit = (params or {}).get("limit", 50)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.slicer_url}/api/jobs", params={"limit": limit})
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("slicer.list_jobs failed: %s", e)
            return {"status": "error", "message": str(e)}


def load_component(config: dict[str, Any]) -> SlicerComponent:
    """Factory function for Moonraker component loading."""
    return SlicerComponent(config)
