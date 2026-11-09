"""Entry point for the Moonraker Slicing Service."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import click
import yaml

from moonraker_slicer.server import create_app

CONFIG_PATHS = [
    Path.home() / ".config" / "moonraker-slicer" / "config.yaml",
    Path(__file__).resolve().parents[2] / "config" / "default.yaml",
]

logger = logging.getLogger("moonraker_slicer")


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML files, merging defaults with user overrides."""
    # Load defaults first
    config: dict = {}
    defaults_path = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            config = yaml.safe_load(f) or {}

    # Override with user config if provided
    user_path = Path(config_path) if config_path else CONFIG_PATHS[0]
    if user_path.exists():
        with open(user_path) as f:
            user_config = yaml.safe_load(f) or {}
            config.update(user_config)

    # Resolve ~ in paths
    for key in ("profiles_dir", "output_dir"):
        if key in config and config[key]:
            config[key] = str(Path(config[key]).expanduser())

    return config


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.command()
@click.option("--config", "-c", "config_path", help="Path to config YAML file")
@click.option("--host", help="Override host from config")
@click.option("--port", "-p", type=int, help="Override port from config")
@click.option("--log-level", help="Override log level from config")
def main(config_path: str | None, host: str | None, port: int | None, log_level: str | None) -> None:
    """Moonraker Slicing Service - HTTP API for headless 3D model slicing."""
    config = load_config(config_path)

    # Apply CLI overrides
    if host:
        config["host"] = host
    if port:
        config["port"] = port
    if log_level:
        config["log_level"] = log_level

    setup_logging(config.get("log_level", "INFO"))

    app = create_app(config)

    # Handle graceful shutdown
    loop = asyncio.new_event_loop()

    def shutdown(sig: int) -> None:
        logger.info("Received signal %d, shutting down...", sig)
        asyncio.create_task(app.shutdown())
        loop.call_soon(loop.stop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: shutdown(s))
        except NotImplementedError:
            pass

    # Start uvicorn in a thread
    import uvicorn
    config_obj = uvicorn.Config(
        app,
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 7125),
        log_level=config.get("log_level", "info").lower(),
    )
    server = uvicorn.Server(config_obj)

    logger.info("Starting Moonraker Slicing Service on %s:%d", config.get("host", "0.0.0.0"), config.get("port", 7125))

    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Service stopped.")


if __name__ == "__main__":
    main()
