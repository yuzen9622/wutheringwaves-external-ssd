#!/bin/bash
source "$(dirname -- "$0")/common.sh"
load_config
python3 "$SCRIPT_DIR/migrate_saved.py" "$@"
