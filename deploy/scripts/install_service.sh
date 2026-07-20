#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
UNIT_NAME="${2:-chat-grid.service}"
DST_UNIT="/etc/systemd/system/$UNIT_NAME"
DROPIN_FILE="/etc/systemd/system/$UNIT_NAME.d/env.conf"
OWNER_USER="$(stat -c '%U' "$REPO_ROOT")"
OWNER_GROUP="$(stat -c '%G' "$REPO_ROOT")"
SERVER_DIR="$REPO_ROOT/server"
RUNTIME_DIR="$SERVER_DIR/runtime"
RUN_SERVER="$SERVER_DIR/run_server.sh"
SERVER_LOG="$RUNTIME_DIR/server.log"

if [[ ! -x "$RUN_SERVER" ]]; then
  echo "error: executable run script not found: $RUN_SERVER" >&2
  exit 1
fi

sudo tee "$DST_UNIT" >/dev/null <<EOF
[Unit]
Description=Endiginous signaling server
After=network.target

[Service]
Type=simple
User=$OWNER_USER
Group=$OWNER_GROUP
WorkingDirectory=$SERVER_DIR
Environment=PATH=$SERVER_DIR/.venv/bin:/usr/bin:/bin
ExecStartPre=/usr/bin/mkdir -p $RUNTIME_DIR
ExecStart=$RUN_SERVER
StandardOutput=append:$SERVER_LOG
StandardError=append:$SERVER_LOG
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

if [[ -f "$DROPIN_FILE" ]]; then
  sudo rm -f "$DROPIN_FILE"
fi
sudo install -d -m 0755 -o "$OWNER_USER" -g "$OWNER_GROUP" "$RUNTIME_DIR"
sudo touch "$SERVER_LOG"
sudo chown "$OWNER_USER:$OWNER_GROUP" "$SERVER_LOG"
sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT_NAME"
sudo systemctl restart "$UNIT_NAME"
sudo systemctl status "$UNIT_NAME" --no-pager
