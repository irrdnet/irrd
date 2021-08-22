#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import logging
import sys

from pathlib import Path

"""
Load an RPSL file into the database.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.storage.database_handler import DatabaseHandler
from irrd.rpsl.rpsl_objects import rpsl_object_from_text

def load_pgp_keys(source: str) -> None:
    dh = DatabaseHandler()
    query = RPSLDatabaseQuery(column_names=['rpsl_pk', 'object_text'])
    query = query.sources([source]).object_classes(['key-cert'])
    keycerts = dh.execute_query(query)

    for keycert in keycerts:
        rpsl_pk = keycert["rpsl_pk"]
        print(f'Loading key-cert {rpsl_pk}')
        # Parsing the keycert in strict mode will load it into the GPG keychain
        result = rpsl_object_from_text(keycert['object_text'], strict_validation=True)
        if result.messages.errors():
            print(f'Errors in PGP key {rpsl_pk}: {result.messages.errors()}')

    print('All valid key-certs loaded into the GnuPG keychain.')
    dh.close()


def main():  # pragma: no cover
    description = """Load all PGP keys from key-cert objects for a specific source into the GnuPG keychain."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('source', type=str,
                        help='the name of the source for which to load PGP keys')
    args = parser.parse_args()

    config_init(args.config_file_path)

    load_pgp_keys(args.source)


if __name__ == '__main__':  # pragma: no cover
    main()
