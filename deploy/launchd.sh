#!/usr/bin/env bash
#
# Keep the API running on this Mac: started at login, started again if it falls
# over, answering this machine only.
#
# The API is the piece that has to be up for anything to work here. The
# operator's console at http://127.0.0.1:<PORT> is served by it, and the model
# is only reachable through it. A process started in a terminal stops with the
# terminal, and after a restart nobody remembers to start it. This installs a
# LaunchAgent, macOS's own answer to that, for the user who runs it: no root,
# no system settings.
#
# It will not install one that answers other machines. Address and port come
# from .env (HOST, PORT), and HOST has to be loopback. The public site does not
# need this API, and the decision is that it does not reach it.
#
#   ./deploy/launchd.sh install     start now, and at every login
#   ./deploy/launchd.sh status      whether it is running, and answering
#   ./deploy/launchd.sh restart     after pulling new code or editing .env
#   ./deploy/launchd.sh logs        follow the log
#   ./deploy/launchd.sh uninstall   stop it and remove it
#
# Answers also need LM Studio's server. That is LM Studio's own setting.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="org.civicaiengine.api"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/civic-ai-engine"
LOG="$LOGDIR/api.log"
TARGET="gui/$(id -u)"
PYTHON="$ROOT/.venv/bin/python3"

say() { printf '%s\n' "$*"; }
die() { printf '\n%s\n' "$*" >&2; exit 1; }

env_value() { sed -n "s/^$1=//p" "$ROOT/.env" 2>/dev/null | tail -1; }
HOST="$(env_value HOST)"; HOST="${HOST:-127.0.0.1}"
PORT="$(env_value PORT)"; PORT="${PORT:-8000}"

installed() { launchctl print "$TARGET/$LABEL" >/dev/null 2>&1; }
answering() { curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/api/health"; }
wait_until_answering() {
  # The first start loads the embedding model, which takes a while.
  for _ in $(seq 1 60); do answering && return 0; sleep 2; done
  return 1
}

case "${1:-}" in
  install)
    [[ -x "$PYTHON" ]] || die "No virtualenv at $ROOT/.venv. HANDOFF.md says how to make one."
    case "$HOST" in
      127.0.0.1|localhost|::1) ;;
      *) die "HOST in .env is $HOST. This installs something that runs all the time, and it
only installs one that answers this machine. Set HOST=127.0.0.1 in .env." ;;
    esac
    if ! installed && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      die "Something is already listening on port $PORT:
$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | awk 'NR > 1 { print "  " $1 " (pid " $2 ")" }')
Stop it first, or the service will fail to start and keep trying."
    fi

    mkdir -p "$LOGDIR" "$(dirname "$PLIST")"
    cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$ROOT/app.py</string>
  </array>
  <!-- app.py reads ./data and ./.env from here -->
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$ROOT/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <!-- Start it again if it exits with an error or is killed; not if it is stopped on purpose. -->
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$LOG</string>
</dict>
</plist>
PLIST
    plutil -lint "$PLIST" >/dev/null || die "The generated plist is malformed: $PLIST"

    launchctl bootout "$TARGET/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$TARGET" "$PLIST"
    say "Installed $LABEL. Waiting for it to answer on 127.0.0.1:$PORT..."
    wait_until_answering || die "It did not answer within two minutes. The log: $LOG"
    say "Running. The console: http://127.0.0.1:$PORT"
    say "macOS may say a background item was added; that is this."
    ;;

  status)
    if installed; then
      INFO="$(launchctl print "$TARGET/$LABEL")"
      STATE="$(printf '%s\n' "$INFO" | sed -n 's/^[[:space:]]*state = //p' | head -1)"
      PID="$(printf '%s\n' "$INFO" | sed -n 's/^[[:space:]]*pid = //p' | head -1)"
      say "service:    $LABEL, ${STATE:-unknown}${PID:+, pid $PID}"
    else
      say "service:    not installed  (./deploy/launchd.sh install)"
    fi
    if answering; then say "answering:  yes, http://127.0.0.1:$PORT"; else say "answering:  no"; fi
    say "log:        $LOG"
    ;;

  restart)
    installed || die "Not installed. ./deploy/launchd.sh install"
    launchctl kickstart -k "$TARGET/$LABEL"
    wait_until_answering || die "Restarted, but not answering after two minutes. The log: $LOG"
    say "Restarted, and answering on 127.0.0.1:$PORT."
    ;;

  logs)
    touch "$LOG"
    tail -n 50 -f "$LOG"
    ;;

  uninstall)
    launchctl bootout "$TARGET/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    say "Stopped and removed. The log is still at $LOG."
    ;;

  *)
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
    [[ -z "${1:-}" ]] || exit 2
    ;;
esac
