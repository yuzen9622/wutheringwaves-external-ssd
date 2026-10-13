#!/bin/bash
source "$(dirname -- "$0")/common.sh"
[ "$#" = 1 ] || { echo 'Usage: bash scripts/inspect.sh PID' >&2; exit 1; }
load_config
check_pid "$1"
lsof -p "$1" -Fn | grep -E '/Library/Client/|/Saved/' || { echo 'No matching open files (or lsof unavailable). This is not proof of success.' >&2; exit 1; }
echo 'Read-only snapshot. Confirm Saved belongs to THIS test game, then fully quit before migration.'
