#!/bin/bash

set -eu

# When making code changes and irrd restarts due to a traceback (i.e., an un-graceful restart),
# we need to clean up the PID file
rm -rf /var/run/irrd.pid

# Wait for Postgres to start otherwise irrd sometimes starts faster and crashes
while true
do
  if ! nc -z postgresql 5432
  then
    echo "Postgres not reachable yet..."
    sleep 1
  else
    echo "Postgres is reachable!"
    break
  fi
done

# Use the poetry venv to run Python with all required deps
cd "$APP_PATH/"
export PATH="${APP_PATH}/.venv/bin:${PATH}"
python3 "${APP_PATH}/irrd/scripts/database_upgrade.py"
python3 "${APP_PATH}/irrd/daemon/main.py" --foreground
