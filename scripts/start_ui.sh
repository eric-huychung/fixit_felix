#!/usr/bin/env bash
# Start the Felix thin UI (loopback API + Next.js).
#
# Usage:
#   ./scripts/start_ui.sh
#   ./scripts/start_ui.sh --api-port 8787 --web-port 3737
#
# Opens:
#   UI  http://127.0.0.1:3737
#   API http://127.0.0.1:8787
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT=8787
WEB_PORT=3737

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-port)
      API_PORT="${2:?--api-port requires a value}"
      shift 2
      ;;
    --web-port)
      WEB_PORT="${2:?--web-port requires a value}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Start the Felix thin UI (loopback API + Next.js).

Usage:
  ./scripts/start_ui.sh
  ./scripts/start_ui.sh --api-port 8787 --web-port 3737

Opens:
  UI  http://127.0.0.1:3737
  API http://127.0.0.1:8787
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--api-port PORT] [--web-port PORT]" >&2
      exit 1
      ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node.js first." >&2
  exit 1
fi

if [[ ! -d web/node_modules ]]; then
  echo "Installing web dependencies…"
  (cd web && npm install)
fi

echo "Starting Felix UI (loopback only)…"
echo "  UI  http://127.0.0.1:${WEB_PORT}"
echo "  API http://127.0.0.1:${API_PORT}"
echo "Ctrl+C stops both."
exec uv run felix ui --api-port "$API_PORT" --web-port "$WEB_PORT"
