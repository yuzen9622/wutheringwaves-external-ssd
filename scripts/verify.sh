#!/bin/bash
source "$(dirname -- "$0")/common.sh"
[ "$#" = 1 ] || { echo 'Usage: bash scripts/verify.sh PID' >&2; exit 1; }
load_config
check_pid "$1"
readlink "$HOME/Library/Client/Saved"
df -h "$HOME/Library/Client/Saved/Resources"
du -sh "$WORK/Saved/Resources"
lsof -p "$1" -Fn | grep -F "$WORK/Saved/" || { echo 'No external open files (or lsof unavailable); inspect manually.' >&2; exit 1; }
echo 'Snapshot only: compare size over time; independently verify download, login and gameplay. NOT automatic success.'
