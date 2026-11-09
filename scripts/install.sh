#!/usr/bin/env bash
set -euo pipefail

VENV="$HOME/.venvs/moonraker-slicer-service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Moonraker Slicing Service Installer ==="

# Create virtualenv
if [ ! -d "$VENV" ]; then
    echo "Creating virtualenv at $VENV..."
    python3 -m venv "$VENV"
fi

# Install dependencies
echo "Installing dependencies..."
"$VENV/bin/pip" install --upgrade pip setuptools wheel
cd "$PROJECT_DIR"
"$VENV/bin/pip" install -e ".[moonraker]"

# Create config directory
CONFIG_DIR="$HOME/.config/moonraker-slicer"
mkdir -p "$CONFIG_DIR"

# Copy default config if not present
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "Creating default config at $CONFIG_DIR/config.yaml"
    cp "$PROJECT_DIR/config/default.yaml" "$CONFIG_DIR/config.yaml"
else
    echo "Config already exists at $CONFIG_DIR/config.yaml (skipping)"
fi

# Create output directory
OUTPUT_DIR="${OUTPUT_DIR:-/home/pi/gcode_files}"
mkdir -p "$OUTPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

echo ""
echo "=== Installation complete ==="
echo "Service is installed in: $VENV"
echo "Config location: $CONFIG_DIR/config.yaml"
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Install PrusaSlicer:   ./scripts/install-slicer.sh"
echo "  2. Edit config:           nano $CONFIG_DIR/config.yaml"
echo "  3. Start the service:     $VENV/bin/python -m moonraker_slicer"
echo "  4. Or install as systemd: ./scripts/systemd-setup.sh"
