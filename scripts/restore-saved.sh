#!/bin/bash
source "$(dirname -- "$0")/common.sh"
# Intentionally NO config/preflight: recovery must work with an unplugged SSD.
python3 "$SCRIPT_DIR/restore_saved.py" "$@"
