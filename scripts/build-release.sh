#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
RELEASE_DIR="$ROOT_DIR/release"
VERSION="${1:-v0.1.0-alpha}"
ARCHIVE_NAME="financial-assistant-${VERSION}.tar.gz"

command -v npm >/dev/null 2>&1 || { echo "ERROR: npm is required" >&2; exit 1; }
PYTHON_BIN="$(command -v python || command -v python3 || true)"
[ -n "$PYTHON_BIN" ] || { echo "ERROR: python is required" >&2; exit 1; }

echo "==> Building frontend"
cd "$FRONTEND_DIR"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build

echo "==> Creating release archive from exact allowlist"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
"$PYTHON_BIN" "$ROOT_DIR/scripts/release_package.py" \
  --source "$ROOT_DIR" \
  --allowlist "$ROOT_DIR/scripts/release-package-allowlist.txt" \
  --stage "$RELEASE_DIR/package" \
  --archive "$RELEASE_DIR/$ARCHIVE_NAME"

echo "==> Done"
echo "Release archive: $RELEASE_DIR/$ARCHIVE_NAME"
echo "Run locally: cd backend && python api_server.py, then open http://localhost:8000"
