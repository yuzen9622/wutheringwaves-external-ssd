#!/bin/bash
source "$(dirname -- "$0")/common.sh"
[ "$#" = 0 ] || { echo 'No arguments expected.' >&2; exit 1; }
load_config
closed
diskutil info "$VOLUME"
df -h "$VOLUME"
echo 'Read capacity/device identity above before continuing. No game changes made.'
