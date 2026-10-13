#!/bin/bash
source "$(dirname -- "$0")/common.sh"
load_config
[ -d "$TEST_APP" ] || { echo 'Test app missing.' >&2; exit 1; }
closed
confirm 'Launches ONLY the configured test app. First inspect Saved ownership; do not immediately download or enter credentials. Launch may write game data.' "$@"
codesign --verify --deep --strict "$TEST_APP"
open -n "$TEST_APP"
echo 'Find the test PID with: pgrep -fl /Contents/MacOS/Client-Mac-Shipping'
