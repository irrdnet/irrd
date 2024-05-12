#!/bin/bash

set -e

BASE_PATH="$1"

rm -rf /var/run/irrd.pid
python3 "${BASE_PATH}/irrd/scripts/database_upgrade.py"
python3 "${BASE_PATH}/irrd/daemon/main.py" --foreground
