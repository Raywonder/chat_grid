#!/usr/bin/env bash
set -euo pipefail

# Install or register optional Indiginous agent tools once per host.  Every
# server points at this same root; rerunning this script is intentionally safe.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SERVER_DIR="$REPO_ROOT/server"
if [[ -n "${CHGRID_SHARED_TOOL_ROOT:-}" ]]; then
  TOOL_ROOT="$CHGRID_SHARED_TOOL_ROOT"
elif [[ -w "/var/lib" ]]; then
  TOOL_ROOT="/var/lib/indiginous/tools"
else
  TOOL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/indiginous/tools"
fi
TOOL_ROOT="$(realpath -m "$TOOL_ROOT")"

if [[ ! -d "$SERVER_DIR" || ! -f "$SERVER_DIR/pyproject.toml" ]]; then
  echo "error: expected Indiginous server source at $SERVER_DIR" >&2
  exit 1
fi
if ! command -v flock >/dev/null 2>&1; then
  echo "error: flock is required for safe shared-host installation" >&2
  exit 1
fi

mkdir -p "$TOOL_ROOT/bin"
exec 9>"$TOOL_ROOT/.install.lock"
flock 9

if [[ "${CHGRID_INSTALL_DEMUCS:-0}" == "1" && ! -x "$TOOL_ROOT/.venv/bin/python" ]]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required to create the shared tool environment" >&2
    exit 1
  fi
  uv venv "$TOOL_ROOT/.venv" --python "${PYTHON_SPEC:-3.13}"
fi

# Ollama is a host service and must never be duplicated per Indiginous server.
if command -v ollama >/dev/null 2>&1 || curl -fsS --max-time 2 "${CHGRID_OLLAMA_URL:-http://127.0.0.1:11434/api/tags}" >/dev/null 2>&1; then
  echo "ollama=available (shared host service)"
else
  echo "ollama=not detected (install/start one host Ollama service separately)"
fi

# Reuse an existing Demucs executable when present. Install only when the
# operator explicitly requests it, avoiding a large surprise model download.
if [[ -n "${CHGRID_DEMUCS_COMMAND:-}" ]]; then
  echo "demucs=using configured command ${CHGRID_DEMUCS_COMMAND%% *}"
elif command -v demucs >/dev/null 2>&1; then
  echo "demucs=using PATH executable $(command -v demucs)"
elif [[ -x "$TOOL_ROOT/.venv/bin/demucs" ]]; then
  echo "demucs=using shared executable $TOOL_ROOT/.venv/bin/demucs"
elif [[ "${CHGRID_INSTALL_DEMUCS:-0}" == "1" ]]; then
  uv pip install --python "$TOOL_ROOT/.venv/bin/python" "demucs>=4.0.1,<5"
  echo "demucs=installed in $TOOL_ROOT/.venv"
else
  echo "demucs=not installed (set CHGRID_INSTALL_DEMUCS=1 to install once for this host)"
fi

echo "shared_tool_root=$TOOL_ROOT"
echo "Add CHGRID_SHARED_TOOL_ROOT=$TOOL_ROOT to each Indiginous server .env."
