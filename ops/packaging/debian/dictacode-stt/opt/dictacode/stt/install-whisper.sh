#!/bin/bash
# install-whisper.sh - Download and build whisper.cpp for dictacode
#
# Usage: sudo /opt/dictacode/stt/install-whisper.sh [model]
#
# Installs to: /opt/dictacode/whisper.cpp
# Model options: tiny (default), base, small, medium, large

set -e

WHISPER_DIR="/opt/dictacode/whisper.cpp"
CONFIG_FILE="/etc/dictacode/stt.conf"

# Default model
MODEL="tiny"

# Read model from config if available
if [ -f "$CONFIG_FILE" ]; then
    CONFIG_MODEL=$(grep "^model=" "$CONFIG_FILE" | cut -d= -f2 | tr -d ' ')
    if [ -n "$CONFIG_MODEL" ]; then
        MODEL="$CONFIG_MODEL"
    fi
fi

# Override with command line argument
if [ -n "$1" ]; then
    MODEL="$1"
fi

# Validate model
case "$MODEL" in
    tiny|base|small|medium|large|tiny.en|base.en|small.en|medium.en)
        ;;
    *)
        echo "ERROR: Unknown model: $MODEL"
        echo "Valid options: tiny, base, small, medium, large"
        echo "              tiny.en, base.en, small.en, medium.en (English-only)"
        exit 1
        ;;
esac

echo "=== Installing whisper.cpp ==="
echo "Target: $WHISPER_DIR"
echo "Model:  $MODEL"
echo ""

# Check for existing installation
if [ -d "$WHISPER_DIR" ]; then
    echo "whisper.cpp already exists at $WHISPER_DIR"
    echo ""
    read -p "Rebuild? This will delete existing installation. [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    echo "Removing existing installation..."
    rm -rf "$WHISPER_DIR"
fi

# Check dependencies
echo "Checking dependencies..."
for cmd in git cmake make; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd is required but not installed"
        echo "Install with: sudo apt install build-essential cmake git"
        exit 1
    fi
done

# Clone repository
echo ""
echo "=== Cloning whisper.cpp ==="
git clone --depth 1 https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR"

# Build
echo ""
echo "=== Building whisper.cpp ==="
cd "$WHISPER_DIR"
cmake -B build
cmake --build build --config Release -j$(nproc)

# Download model
echo ""
echo "=== Downloading model: $MODEL ==="
./models/download-ggml-model.sh "$MODEL"

# Check for additional models in config
if [ -f "$CONFIG_FILE" ]; then
    EXTRA_MODELS=$(grep "^models_extra=" "$CONFIG_FILE" | cut -d= -f2 | tr -d ' ')
    if [ -n "$EXTRA_MODELS" ]; then
        echo ""
        echo "=== Downloading additional models: $EXTRA_MODELS ==="
        IFS=',' read -ra MODELS <<< "$EXTRA_MODELS"
        for extra in "${MODELS[@]}"; do
            echo "Downloading: $extra"
            ./models/download-ggml-model.sh "$extra" || echo "WARNING: Failed to download $extra"
        done
    fi
fi

# Set ownership
echo ""
echo "=== Setting ownership ==="
chown -R dictacode:dictacode "$WHISPER_DIR"

# Verify installation
echo ""
echo "=== Verifying installation ==="
BINARY="$WHISPER_DIR/build/bin/whisper-cli"
MODEL_FILE="$WHISPER_DIR/models/ggml-$MODEL.bin"

if [ -x "$BINARY" ]; then
    echo "Binary: $BINARY [OK]"
else
    echo "ERROR: Binary not found: $BINARY"
    exit 1
fi

if [ -f "$MODEL_FILE" ]; then
    echo "Model:  $MODEL_FILE [OK]"
else
    echo "ERROR: Model not found: $MODEL_FILE"
    exit 1
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To start the STT service:"
echo "  sudo systemctl enable --now dictacode-stt"
echo ""
echo "To test manually:"
echo "  $BINARY -m $MODEL_FILE -f /path/to/audio.wav"
