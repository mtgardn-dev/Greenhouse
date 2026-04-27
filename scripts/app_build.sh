#!/usr/bin/env bash
set -euo pipefail

# Build the Greenhouse Log Viewer macOS app bundle with PyInstaller.
# Usage: ./scripts/app_build.sh [version]

APP_NAME="GreenhouseLogViewer"
APP_DISPLAY_NAME="Greenhouse Log Viewer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
BOOTSTRAP_DIR="$BUILD_DIR/bootstrap_data"
ENTRYPOINT="$PROJECT_ROOT/core/main.py"
ICON_SRC="$PROJECT_ROOT/resources/greenhouse.icns"

cd "$PROJECT_ROOT"

resolve_build_tag() {
  local raw="${1:-${GREENHOUSE_BUILD_TAG:-}}"
  if [[ -z "$raw" ]]; then
    raw="$(git -C "$PROJECT_ROOT" describe --tags --abbrev=0 2>/dev/null || true)"
  fi
  if [[ -z "$raw" ]]; then
    raw="v0.0.0"
  fi
  if [[ "$raw" == v* || "$raw" == V* ]]; then
    printf '%s\n' "$raw"
  else
    printf 'v%s\n' "$raw"
  fi
}

BUILD_TAG="$(resolve_build_tag "${1:-}")"
VERSION="${BUILD_TAG#v}"
BUILD_COMMIT="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
if [[ -z "$BUILD_COMMIT" ]]; then
  BUILD_COMMIT="unknown"
fi
BUILT_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -f "$ENTRYPOINT" ]]; then
  echo "[build:ERROR] Missing entrypoint: $ENTRYPOINT"
  exit 1
fi

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "[build:ERROR] Python interpreter not found."
  exit 1
fi

if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
  echo "[build] Installing PyInstaller into active environment..."
  "$PYTHON_BIN" -m pip install pyinstaller
fi

echo "[build] Cleaning build/dist directories..."
rm -rf "$PROJECT_ROOT/dist" "$BUILD_DIR"
mkdir -p "$BOOTSTRAP_DIR"

cat > "$BOOTSTRAP_DIR/version.json" <<METADATA
{
  "app_name": "$APP_NAME",
  "app_display_name": "$APP_DISPLAY_NAME",
  "build_tag": "$BUILD_TAG",
  "version": "$VERSION",
  "commit": "$BUILD_COMMIT",
  "built_at_utc": "$BUILT_AT_UTC"
}
METADATA

PYINSTALLER_ARGS=(
  --noconfirm
  --windowed
  --onedir
  --name "$APP_NAME"
  --add-data "$BOOTSTRAP_DIR:bootstrap_data"
)

if [[ -f "$ICON_SRC" ]]; then
  PYINSTALLER_ARGS+=(--icon "$ICON_SRC")
else
  echo "[build] No custom icon found at $ICON_SRC; building without one."
fi

echo "[build] Running PyInstaller for version $VERSION ($BUILD_TAG)..."
"$PYTHON_BIN" -m PyInstaller "${PYINSTALLER_ARGS[@]}" "$ENTRYPOINT"

echo "[build] ✅ Build complete: dist/${APP_NAME}.app"
