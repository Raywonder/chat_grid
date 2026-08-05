#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SERVER_DIR="$REPO_ROOT/server"
PYTHON_SPEC="${PYTHON_SPEC:-3.13}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required but not found in PATH" >&2
  exit 1
fi

if [[ ! -d "$SERVER_DIR" ]]; then
  echo "error: server directory not found: $SERVER_DIR" >&2
  exit 1
fi
if [[ ! -f "$SERVER_DIR/pyproject.toml" ]]; then
  echo "error: missing $SERVER_DIR/pyproject.toml" >&2
  echo "       verify repository files were copied to the expected repo directory" >&2
  exit 1
fi

cd "$SERVER_DIR"

# Avoid interactive prompts: reuse existing venv; create only when missing.
if [[ ! -d .venv ]]; then
  uv venv .venv --python "$PYTHON_SPEC"
  echo "created .venv with Python $PYTHON_SPEC"
else
  echo "using existing .venv"
fi

if [[ -x .venv/bin/python ]]; then
  VENV_PYTHON_VERSION="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
  )"
  if [[ "$VENV_PYTHON_VERSION" != "$PYTHON_SPEC" ]]; then
    echo "warning: .venv uses Python $VENV_PYTHON_VERSION (requested $PYTHON_SPEC)" >&2
    echo "         remove .venv and rerun script to recreate with Python $PYTHON_SPEC" >&2
  fi
fi

uv sync --no-dev --project "$SERVER_DIR"

if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
  echo "created $SERVER_DIR/config.toml from template"
fi

mkdir -p runtime

# Register optional agent capabilities against one host-wide root. This keeps
# separate Indiginous server installs from downloading duplicate toolchains.
if [[ -z "${CHGRID_SHARED_TOOL_ROOT:-}" ]]; then
  if [[ -w "/var/lib" ]]; then
    CHGRID_SHARED_TOOL_ROOT="/var/lib/indiginous/tools"
  else
    CHGRID_SHARED_TOOL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/indiginous/tools"
  fi
fi
if [[ "${CHGRID_SKIP_AGENT_TOOLS:-0}" != "1" ]]; then
  export CHGRID_SHARED_TOOL_ROOT
  if [[ -x "$REPO_ROOT/deploy/scripts/install_agent_tools.sh" ]]; then
    "$REPO_ROOT/deploy/scripts/install_agent_tools.sh" "$REPO_ROOT"
  fi
fi

if [[ ! -f .env ]]; then
  AUTH_SECRET="$(
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
  )"
  printf "CHGRID_AUTH_SECRET=%s\n" "$AUTH_SECRET" > .env
  printf "# Required browser origin, for example CHGRID_HOST_ORIGIN=https://example.com\n" >> .env
  chmod 600 .env
  echo "created $SERVER_DIR/.env with CHGRID_AUTH_SECRET"
fi

if ! grep -q '^CHGRID_SHARED_TOOL_ROOT=' .env; then
  printf "CHGRID_SHARED_TOOL_ROOT=%s\n" "$CHGRID_SHARED_TOOL_ROOT" >> .env
fi

# Load generated/shared auth secret for bootstrap checks.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -n "${CHGRID_AUTH_SECRET:-}" ]]; then
  HAS_ADMIN="$(
    .venv/bin/python - <<'PY'
from pathlib import Path
import os
from app.auth_service import AuthService
from app.config import load_config

cfg = load_config(Path("config.toml"))
secret = os.getenv("CHGRID_AUTH_SECRET", "").strip()
if not secret:
    print("unknown")
    raise SystemExit(0)
db_file = cfg.auth.db_file.strip() or "runtime/chatgrid.db"
db_path = Path(db_file)
if not db_path.is_absolute():
    db_path = Path.cwd() / db_path
svc = AuthService(
    db_path=db_path,
    token_hash_secret=secret,
    password_min_length=cfg.auth.password_min_length,
    password_max_length=cfg.auth.password_max_length,
    username_min_length=cfg.auth.username_min_length,
    username_max_length=cfg.auth.username_max_length,
)
try:
    print("yes" if svc.has_admin() else "no")
finally:
    svc.close()
PY
  )"

  if [[ "$HAS_ADMIN" == "no" ]]; then
    if [[ -t 0 ]]; then
      read -r -p "No admin account found. Create one now? [y/N] " CREATE_ADMIN_NOW
      case "${CREATE_ADMIN_NOW:-}" in
        y|Y|yes|YES)
          .venv/bin/python main.py --config config.toml --bootstrap-admin
          ;;
        *)
          echo "skipped admin bootstrap (you can run: .venv/bin/python main.py --config config.toml --bootstrap-admin)"
          ;;
      esac
    else
      echo "no admin account found (non-interactive run)."
      echo "run once to bootstrap: .venv/bin/python main.py --config config.toml --bootstrap-admin"
    fi
  fi
fi

chmod +x "$SERVER_DIR/run_server.sh"

echo "server install complete"
echo "next: edit $SERVER_DIR/config.toml (TLS, bind_ip, port) and set CHGRID_HOST_ORIGIN in $SERVER_DIR/.env"
