#!/usr/bin/env bash
set -euo pipefail

echo "=== Setting up systemd service ==="

SERVICE_NAME="moonraker-slicer.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

# Detect user
USER="${SUDO_USER:-$(whoami)}"
HOME_DIR=$(eval echo ~$USER)
VENV="$HOME_DIR/.venvs/moonraker-slicer-service"

if [ ! -d "$VENV" ]; then
    echo "Error: Virtualenv not found at $VENV"
    echo "Run ./scripts/install.sh first."
    exit 1
fi

# Write service file
cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Moonraker Slicing Service
After=network-online.target moonraker.service
Wants=network-online.target

[Service]
Type=simple
User=${USER}
Group=${USER}
WorkingDirectory=${HOME_DIR}/src/moonraker-slicer-service
ExecStart=${VENV}/bin/python -m moonraker_slicer
Restart=on-failure
RestartSec=5
Environment=HOME=${HOME_DIR}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Service file written to: $SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "=== systemd setup complete ==="
echo "Start the service: sudo systemctl start ${SERVICE_NAME}"
echo "Check status:      sudo systemctl status ${SERVICE_NAME}"
echo "View logs:         sudo journalctl -u ${SERVICE_NAME} -f"
