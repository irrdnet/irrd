#!/bin/bash

# This script can be used to import data for testing.
# This is for use when running IRRd in Docker.

set -eu

function download() {
    local URL="$1"
    # wget returns 1 if file exists and using -nc
    wget -nc -O "${DATA_PATH}/$(basename "$URL")" "${URL}" || true
}

mkdir -p "${DATA_PATH}"
cd "${DATA_PATH}/"

# download "https://ftp.afrinic.net/pub/dbase/afrinic.db.gz"
# download "https://ftp.afrinic.net/pub/dbase/AFRINIC.CURRENTSERIAL"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.as-block.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.as-set.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.aut-num.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.domain.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.filter-set.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.inet-rtr.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.inet6num.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.inetnum.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.irt.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.key-cert.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.limerick.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.mntner.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.organisation.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.peering-set.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.role.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.route-set.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.route.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.route6.gz"
# download "ftp://ftp.apnic.net/apnic/whois/apnic.db.rtr-set.gz"
# download "ftp://ftp.apnic.net/pub/apnic/whois/APNIC.CURRENTSERIAL"
# download "https://ftp.arin.net/pub/rr/arin.db.gz"
# download "https://ftp.arin.net/pub/rr/ARIN.CURRENTSERIAL"
# download "https://irr.lacnic.net/lacnic.db.gz"
# download "https://irr.lacnic.net/LACNIC.CURRENTSERIAL"
# download "ftp://ftp.radb.net/radb/dbase/radb.db.gz"
# download "ftp://ftp.radb.net/radb/dbase/RADB.CURRENTSERIAL"
download "https://ftp.ripe.net/ripe/dbase/split/ripe.db.as-set.gz"
download "https://ftp.ripe.net/ripe/dbase/split/ripe.db.aut-num.gz"
# download "https://ftp.ripe.net/ripe/dbase/split/ripe.db.route-set.gz"
# download "https://ftp.ripe.net/ripe/dbase/split/ripe.db.route.gz"
# download "https://ftp.ripe.net/ripe/dbase/split/ripe.db.route6.gz"
download "https://ftp.ripe.net/ripe/dbase/RIPE.CURRENTSERIAL"

gunzip -kf "${DATA_PATH}"/*.gz

# Don't add the config below more than once / don't clobber existing config
if ! grep -E "sources_default:|sources:" /etc/irrd.yaml
then

  echo "

sources_default:
    - AFRINIC
    - APNIC
    - ARIN
    - LACNIC
    - RADB
    - RIPE

sources:
    AFRINIC:
      authoritative: false
      keep_journal: false
      import_source: file://${DATA_PATH}/afrinic.db.gz
      import_serial_source: file://${DATA_PATH}/AFRINIC.CURRENTSERIAL
    APNIC:
      authoritative: false
      keep_journal: false
      import_source:
        - file://${DATA_PATH}/apnic.db.as-block.gz
        - file://${DATA_PATH}/apnic.db.as-set.gz
        - file://${DATA_PATH}/apnic.db.aut-num.gz
        - file://${DATA_PATH}/apnic.db.domain.gz
        - file://${DATA_PATH}/apnic.db.filter-set.gz
        - file://${DATA_PATH}/apnic.db.inet-rtr.gz
        - file://${DATA_PATH}/apnic.db.inet6num.gz
        - file://${DATA_PATH}/apnic.db.inetnum.gz
        - file://${DATA_PATH}/apnic.db.irt.gz
        - file://${DATA_PATH}/apnic.db.key-cert.gz
        - file://${DATA_PATH}/apnic.db.limerick.gz
        - file://${DATA_PATH}/apnic.db.mntner.gz
        - file://${DATA_PATH}/apnic.db.organisation.gz
        - file://${DATA_PATH}/apnic.db.peering-set.gz
        - file://${DATA_PATH}/apnic.db.role.gz
        - file://${DATA_PATH}/apnic.db.route-set.gz
        - file://${DATA_PATH}/apnic.db.route.gz
        - file://${DATA_PATH}/apnic.db.route6.gz
        - file://${DATA_PATH}/apnic.db.rtr-set.gz
      import_serial_source: file://${DATA_PATH}/APNIC.CURRENTSERIAL
    ARIN:
      authoritative: false
      keep_journal: false
      import_source: file://${DATA_PATH}/arin.db.gz
      import_serial_source: file://${DATA_PATH}/ARIN.CURRENTSERIAL
    LACNIC:
      authoritative: false
      keep_journal: false
      import_source: file://${DATA_PATH}/lacnic.db.gz
      import_serial_source: file://${DATA_PATH}/LACNIC.CURRENTSERIAL
    RADB:
        authoritative: false
        keep_journal: false
        import_serial_source: file://${DATA_PATH}/RADB.CURRENTSERIAL
        import_source:
        - file://${DATA_PATH}/radb.db.gz
    RIPE:
        authoritative: false
        keep_journal: false
        import_serial_source: file:///opt/irrd_data/RIPE.CURRENTSERIAL
        import_source:
        - file://${DATA_PATH}/ripe.db.as-set.gz
        - file://${DATA_PATH}/ripe.db.aut-num.gz
        - file://${DATA_PATH}/ripe.db.route.gz
        - file://${DATA_PATH}/ripe.db.route6.gz
        - file://${DATA_PATH}/ripe.db.route-set.gz

" >> /etc/irrd.yaml

fi

# Trigger a config import by irrd so that the new data sources are defined
kill -s SIGHUP "$(cat /var/run/irrd.pid)"

# Wait for irrd to restart
sleep 2

# Import the new data, each import runs single-threaded so spin them all up together
for IRRDB in "AFRINIC afrinic.db" "APNIC apnic.db" "ARIN arin.db" "LACNIC lacnic.db" "RADB radb.db" "RIPE ripe.db"
do
  set -- $IRRDB # $1 = "AFRINC", $2 = "afrinic.db"
  for FILE_NAME in $(find $DATA_PATH/ -not -name "*.gz" -name "${2}*")
  do
    "${APP_PATH}/.venv/bin/python3" "${APP_PATH}/irrd/scripts/load_database.py"  \
    --source "$1" --serial "$(cat "${DATA_PATH}/$1.CURRENTSERIAL")" "${FILE_NAME}" &
  done
done

# Wait for all imports to finish
echo -e "\nWaiting for data import to completed...\n"
wait $(jobs -p)
echo -e "\nData import completed"
