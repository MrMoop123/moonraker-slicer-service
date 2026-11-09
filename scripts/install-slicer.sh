#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing PrusaSlicer (arm64) ==="

# Default to AppImage (headless)
METHOD="${1:-appimage}"

install_appimage() {
    echo ""
    echo "Downloading PrusaSlicer 2.6.0 arm64 AppImage..."
    echo "Note: 2.6.0 is the last version with official arm64 AppImage builds."

    # PrusaSlicer 2.6.0 arm64 AppImage
    SLICER_URL="https://github.com/prusa3d/PrusaSlicer/releases/download/v2.6.0/prusa-slicer-2.6.0-Dev-g561599d9e-linux-gtk2-armv7a.AppImage"
    SLICER_PATH="/usr/local/bin/prusa-slicer"

    # Alternative URL if the Dev build doesn't work (release version)
    ALT_URL="https://github.com/prusa3d/PrusaSlicer/releases/download/v2.6.0/prusa-slicer-2.6.0-linux-gtk2-armv7a.AppImage"

    # Try main URL first, fall back to alternative
    if ! curl -L -f -o "$SLICER_PATH" "$SLICER_URL" 2>/dev/null; then
        echo "Primary URL failed, trying alternative..."
        curl -L -f -o "$SLICER_PATH" "$ALT_URL"
    fi

    chmod +x "$SLICER_PATH"
    echo "Installed to: $SLICER_PATH"
}

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
    if ! flatpak remote-list | grep -q flathub; then
        flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    fi

    # Install PrusaSlicer
    flatpak install flathub com.prusa3d.PrusaSlicer -y

    # The CLI binary is inside the flatpak sandbox
    # We can call it via flatpak run
    echo "Installed PrusaSlicer via Flatpak"
    echo "Update config.yaml slicer_binary to use: flatpak run com.prusa3d.PrusaSlicer"
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
        echo "  appimage  - Standalone binary, works headless (recommended for BTT Pi)"
        echo "  flatpak   - Flatpak package, requires desktop environment"
        exit 1
        ;;
esac

echo ""
echo "=== PrusaSlicer installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Verify the binary works (may need dependencies for headless use)"
echo "  2. Update config.yaml slicer_binary path"
echo "  3. Run: ./$0 to install the Python service"
