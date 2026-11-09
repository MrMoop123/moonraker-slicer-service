#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing OrcaSlicer (arm64) ==="

# Default to AppImage (lightweight, no GUI needed)
METHOD="${1:-appimage}"

install_appimage() {
    echo ""
    echo "Downloading OrcaSlicer v2.5.0 arm64 AppImage (official)..."

    SLICER_PATH="/usr/local/bin/orca-slicer"
    SLICER_URL="https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v2.5.0/OrcaSlicer_Linux_AppImage_Ubuntu2404_aarch64_V2.5.0.AppImage"

    echo "URL: $SLICER_URL"
    echo ""

    # Download to temp dir first (no sudo needed)
    TMP_FILE=$(mktemp /tmp/orca-slicer-XXXXXX.AppImage)
    curl -L -f -o "$TMP_FILE" "$SLICER_URL"

    # Check size - AppImage should be ~200MB+
    SIZE=$(stat -c%s "$TMP_FILE" 2>/dev/null || echo "0")
    SIZE_MB=$((SIZE / 1048576))

    if [ "$SIZE_MB" -lt 50 ]; then
        echo "WARNING: Download seems too small ($SIZE_MB MB) - may have failed."
        rm -f "$TMP_FILE"
        exit 1
    fi

    echo "Downloaded ($SIZE_MB MB). Installing to $SLICER_PATH ..."

    # Move with sudo to system path
    sudo mv "$TMP_FILE" "$SLICER_PATH"
    sudo chmod +x "$SLICER_PATH"

    echo ""
    echo "Installed to: $SLICER_PATH ($SIZE_MB MB)"
    echo ""
    echo "Next steps:"
    echo "  Install the service:   ./scripts/install.sh"
    echo "  Verify config.yaml shows: slicer_binary: /usr/local/bin/orca-slicer"
}

install_flatpak() {
    echo ""
    echo "Installing OrcaSlicer via Flatpak..."

    # Check if flatpak is installed
    if ! command -v flatpak &>/dev/null; then
        echo "Flatpak not found. Installing..."
        sudo apt-get update
        sudo apt-get install -y flatpak
    fi

    # Add Flathub remote
    if ! flatpak remote-list 2>/dev/null | grep -q flathub; then
        flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    fi

    # Install OrcaSlicer
    flatpak install flathub com.orcaslicer.OrcaSlicer -y

    echo ""
    echo "Installed OrcaSlicer via Flatpak"
    echo ""
    echo "To use from CLI, update config.yaml slicer_binary to:"
    echo "  slicer_binary: \"flatpak run com.orcaslicer.OrcaSlicer\""
}

case "$METHOD" in
    appimage)
        install_appimage
        ;;
    flatpak)
        install_flatpak
        ;;
    *)
        echo "Usage: $0 [appimage|flatpak]"
        echo ""
        echo "  appimage  - Official OrcaSlicer v2.5.0 AppImage (recommended, lightweight)"
        echo "  flatpak   - OrcaSlicer via Flatpak (larger install, requires desktop)"
        exit 1
        ;;
esac
