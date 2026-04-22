#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
APP_SUPPORT_DIR="$HOME/Library/Application Support/StarMap"
RUNTIME_BIN_DIR="$APP_SUPPORT_DIR/bin"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_LABEL="com.ianwang.starmap.backend"
FRONTEND_LABEL="com.ianwang.starmap.frontend"
BACKEND_PLIST="$LAUNCH_AGENTS_DIR/$BACKEND_LABEL.plist"
FRONTEND_PLIST="$LAUNCH_AGENTS_DIR/$FRONTEND_LABEL.plist"
BACKEND_RUNNER="$RUNTIME_BIN_DIR/start_backend.sh"
FRONTEND_RUNNER="$RUNTIME_BIN_DIR/start_frontend.sh"
UID_VALUE="$(id -u)"

mkdir -p "$LAUNCH_AGENTS_DIR" "$APP_SUPPORT_DIR" "$RUNTIME_BIN_DIR" "$LOG_DIR"

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  echo "Missing Python runtime at $ROOT_DIR/backend/.venv/bin/python" >&2
  exit 1
fi

cat > "$BACKEND_RUNNER" <<EOF
#!/bin/zsh
set -euo pipefail
cd "$ROOT_DIR/backend"
exec "$ROOT_DIR/backend/.venv/bin/python" main.py
EOF

cat > "$FRONTEND_RUNNER" <<EOF
#!/bin/zsh
set -euo pipefail
cd "$ROOT_DIR"
exec "$ROOT_DIR/backend/.venv/bin/python" -m http.server 8000 --bind 127.0.0.1 --directory frontend
EOF

chmod 755 "$BACKEND_RUNNER" "$FRONTEND_RUNNER"

cat > "$BACKEND_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$BACKEND_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BACKEND_RUNNER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR/backend</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/backend.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/backend.stderr.log</string>
</dict>
</plist>
EOF

cat > "$FRONTEND_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$FRONTEND_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$FRONTEND_RUNNER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/frontend.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/frontend.stderr.log</string>
</dict>
</plist>
EOF

chmod 644 "$BACKEND_PLIST" "$FRONTEND_PLIST"

launchctl bootout "gui/$UID_VALUE/$BACKEND_LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$UID_VALUE/$FRONTEND_LABEL" >/dev/null 2>&1 || true

launchctl bootstrap "gui/$UID_VALUE" "$BACKEND_PLIST"
launchctl bootstrap "gui/$UID_VALUE" "$FRONTEND_PLIST"

launchctl enable "gui/$UID_VALUE/$BACKEND_LABEL"
launchctl enable "gui/$UID_VALUE/$FRONTEND_LABEL"

launchctl kickstart -k "gui/$UID_VALUE/$BACKEND_LABEL"
launchctl kickstart -k "gui/$UID_VALUE/$FRONTEND_LABEL"

echo "Installed and started:"
echo "  $BACKEND_LABEL"
echo "  $FRONTEND_LABEL"
