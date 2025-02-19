#!/bin/sh
# This script performs the following actions:
# 1. Removes any existing PID files for the IRRD service from the /var/run/irrd directory.
# 2. Upgrades the IRRD database using the configuration file located at /etc/irrd.yaml.
# 3. Starts the IRRD service in the foreground using the configuration file located at /etc/irrd.yaml.

rm /var/run/irrd/* >/dev/null 2>&1 || true

irrd_database_upgrade --config=/etc/irrd.yaml
exec /usr/local/bin/irrd --foreground --config=/etc/irrd.yaml

