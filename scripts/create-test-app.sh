#!/bin/bash
source "$(dirname -- "$0")/common.sh"
load_config
confirm 'Creates a NEW independent APFS clone and strips its entitlements with ad-hoc signing. Account/isolation risks; original stays unchanged. Failed copies are kept, never removed automatically.' "$@"
python3 "$SCRIPT_DIR/safety.py" clone
