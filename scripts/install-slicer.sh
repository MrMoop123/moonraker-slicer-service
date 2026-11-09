#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing PrusaSlicer (arm64) ==="

# Default to Flatpak (official, latest version)
METHOD="${1:-flatpak}"

install_flatpak() {
    echo ""
    echo "Installing PrusaSlicer via Flatpak..."

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

    # Install PrusaSlicer
    flatpak install flathub com.prusa3d.PrusaSlicer -y

    echo ""
    echo "Installed PrusaSlicer via Flatpak (version available in sandbox)"
    echo ""
    echo "To use from CLI, update config.yaml slicer_binary to:"
    echo "  slicer_binary: \"flatpak run com.prusa3d.PrusaSlicer\""
    echo "  # or use the bundled binary:"
    echo "  slicer_binary: \"$(flatpak list 2>/dev/null | grep PrusaSlicer | awk '{print $5}')\""
}

install_appimage() {
    echo ""
    echo "Downloading PrusaSlicer arm64 AppImage (community build by davidk)..."

    SLICER_PATH="/usr/local/bin/prusa-slicer"

    # Use davidk's community ARM AppImage (PrusaSlicer 2.8.1, arm64)
    # This is the last community-maintained arm64 AppImage
    SLICER_URL="https://github.com/davidk/PrusaSlicer-ARM.AppImage/releases/download/version_2.8.1/PrusaSlicer-version_2.8.1-aarch64.AppImage"

    echo "URL: $SLICER_URL"
    echo ""

    # Download
    if ! curl -L -f -o "$SLICER_PATH" "$SLICER_URL"; then
        echo "Download failed. Trying mirror URL..."
        curl -L -f -o "$SLICER_PATH" "https://github.com/davidk/PrusaSlicer-ARM.AppImage/releases/download/version_2.8.1/PrusaSlicer-version_2.8.1-aarch64.AppImage"
    fi

    chmod +x "$SLICER_PATH"

    # Check size - AppImage should be ~200MB+
    SIZE=$(stat -c%s "$SLICER_PATH" 2>/dev/null || echo "0")
    SIZE_MB=$((SIZE / 1048576))
    echo "Downloaded to: $SLICER_PATH ($SIZE_MB MB)"

    if [ "$SIZE_MB" -lt 50 ]; then
        echo ""
        echo "WARNING: Download seems too small - may have failed."
        echo "Try using flatpak instead: $0 flatpak"
        exit 1
    fi

    echo ""
    echo "Installed to: $SLICER_PATH"
    echo ""
    echo "Next steps:"
    echo "  Update config.yaml slicer_binary: /usr/local/bin/prusa-slicer"
}

case "$METHOD" in
    flatpak)
        install_flatpak
        ;;
    appimage)
        install_appimage
        ;;
    *)
        echo "Usage: $0 [appimage|flatpak]"
        echo ""
        echo "  flatpak   - Official PrusaSlicer 2.9.7 via Flatpak (recommended)"
        echo "  appimage  - Community PrusaSlicer 2.8.1 AppImage (lighter, no GUI needed)"
        exit 1
        ;;
esac
