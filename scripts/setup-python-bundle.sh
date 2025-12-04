#!/bin/bash

# LangConfig - Python Bundle Setup Script
# Downloads and configures python-build-standalone for bundling

set -e

echo "🐍 Setting up Python standalone for LangConfig..."

# Determine platform
OS=$(uname -s)
ARCH=$(uname -m)

PYTHON_VERSION="3.12.7"
BUILD_DATE="20241016"

# Select appropriate Python build
case "$OS" in
  Linux)
    if [ "$ARCH" = "x86_64" ]; then
      PYTHON_BUILD="cpython-${PYTHON_VERSION}+${BUILD_DATE}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    else
      echo "❌ Unsupported Linux architecture: $ARCH"
      exit 1
    fi
    ;;
  Darwin)
    if [ "$ARCH" = "arm64" ]; then
      PYTHON_BUILD="cpython-${PYTHON_VERSION}+${BUILD_DATE}-aarch64-apple-darwin-install_only.tar.gz"
    elif [ "$ARCH" = "x86_64" ]; then
      PYTHON_BUILD="cpython-${PYTHON_VERSION}+${BUILD_DATE}-x86_64-apple-darwin-install_only.tar.gz"
    else
      echo "❌ Unsupported macOS architecture: $ARCH"
      exit 1
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PYTHON_BUILD="cpython-${PYTHON_VERSION}+${BUILD_DATE}-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
    ;;
  *)
    echo "❌ Unsupported operating system: $OS"
    exit 1
    ;;
esac

DOWNLOAD_URL="https://github.com/indygreg/python-build-standalone/releases/download/${BUILD_DATE}/${PYTHON_BUILD}"

# Create directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_DIR="$PROJECT_ROOT/src-tauri/python"
BACKEND_DIR="$PROJECT_ROOT/backend"
BACKEND_LIB="$BACKEND_DIR/lib"

echo "📁 Creating directories..."
mkdir -p "$PYTHON_DIR"
mkdir -p "$BACKEND_LIB"

# Download Python standalone
echo "⬇️  Downloading Python standalone: $PYTHON_BUILD"
cd "$PROJECT_ROOT"

if [ -f "$PYTHON_BUILD" ]; then
  echo "✓ Python build already downloaded"
else
  curl -L -o "$PYTHON_BUILD" "$DOWNLOAD_URL"
  echo "✓ Download complete"
fi

# Extract Python
echo "📦 Extracting Python standalone..."
tar -xzf "$PYTHON_BUILD" -C "$PYTHON_DIR" --strip-components=1
echo "✓ Python extracted to: $PYTHON_DIR"

# Set Python executable path
if [ "$OS" = "MINGW"* ] || [ "$OS" = "MSYS"* ] || [ "$OS" = "CYGWIN"* ]; then
  PYTHON_EXE="$PYTHON_DIR/python.exe"
else
  PYTHON_EXE="$PYTHON_DIR/bin/python3"
fi

# Verify Python installation
echo "🔍 Verifying Python installation..."
"$PYTHON_EXE" --version

# Install backend dependencies
echo "📚 Installing backend dependencies..."
"$PYTHON_EXE" -m pip install --upgrade pip
"$PYTHON_EXE" -m pip install -r "$BACKEND_DIR/requirements.txt" -t "$BACKEND_LIB"
echo "✓ Dependencies installed to: $BACKEND_LIB"

# Cleanup
echo "🧹 Cleaning up..."
rm "$PYTHON_BUILD"

echo ""
echo "✅ Python standalone setup complete!"
echo ""
echo "Python location: $PYTHON_DIR"
echo "Python executable: $PYTHON_EXE"
echo "Backend libraries: $BACKEND_LIB"
echo ""
echo "Next steps:"
echo "  1. Run 'npm run tauri dev' to test in development mode"
echo "  2. Run 'npm run tauri build' to create production bundle"
echo ""
