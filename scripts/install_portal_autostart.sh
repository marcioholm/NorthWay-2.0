#!/bin/bash
set -e

PLIST_PATH="$HOME/Library/LaunchAgents/com.northway.prospector.plist"
SCRIPT_PATH="/Users/Marci.Holm/Downloads/NorthWay-2.0-main/scripts/scraper_portal.py"
LOG_DIR="/Users/Marci.Holm/Downloads/NorthWay-2.0-main/scraper_data"
PYTHON_BIN="$(which python3)"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.northway.prospector</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$SCRIPT_PATH</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/Marci.Holm/Downloads/NorthWay-2.0-main</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/portal.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/portal.err.log</string>
</dict>
</plist>
EOF

# Encerra eventual instancia manual na 8080 e ativa o servico LaunchAgent
lsof -ti :8080 | xargs kill -9 2>/dev/null || true
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Servico com.northway.prospector instalado e ativo em http://localhost:8080"

