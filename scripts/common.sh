#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PACKAGE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
[ "$(id -u)" != 0 ] || { echo 'Do not run as root/sudo.' >&2; exit 1; }
[ -z "${SUDO_USER:-}" ] || { echo 'Do not use sudo.' >&2; exit 1; }
[ "$(uname -s)" = Darwin ] || { echo 'macOS required.' >&2; exit 1; }
command -v python3 >/dev/null
load_config() {
  [ -f "$PACKAGE_DIR/config.env" ] || { echo 'Copy config.env.example to config.env and edit it first.' >&2; exit 1; }
  source "$PACKAGE_DIR/config.env"
  python3 "$SCRIPT_DIR/safety.py" preflight
}
confirm() {
  local message="$1" answer
  shift
  if [ "$#" = 1 ] && [ "$1" = --yes ]; then return; fi
  [ "$#" = 0 ] || { echo 'Only optional --yes is accepted.' >&2; exit 1; }
  printf '%s\nType YES to continue: ' "$message"
  read -r answer
  [ "$answer" = YES ] || { echo 'Cancelled.' >&2; exit 1; }
}
closed() { python3 "$SCRIPT_DIR/safety.py" closed; }
check_pid() {
  python3 "$SCRIPT_DIR/safety.py" pid "$1"
}
