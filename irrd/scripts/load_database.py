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

from irrd.rpki.validators import BulkRouteROAValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.mirroring.parsers import MirrorFileImportParser
from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting


def load(source, filename, serial) -> int:
    if any([
        get_setting(f'sources.{source}.import_source'),
        get_setting(f'sources.{source}.import_serial_source')
    ]):
        print(f'Error: to use this command, import_source and import_serial_source '
              f'for source {source} must not be set.')
        return 2

    dh = DatabaseHandler()
    roa_validator = BulkRouteROAValidator(dh)
    dh.delete_all_rpsl_objects_with_journal(source)
    dh.disable_journaling()
    parser = MirrorFileImportParser(
        source=source, filename=filename, serial=serial, database_handler=dh,
        direct_error_return=True, roa_validator=roa_validator)
    error = parser.run_import()
    if error:
        dh.rollback()
    else:
        dh.commit()
    dh.close()
    if error:
        print(f'Error occurred while processing object:\n{error}')
        return 1
    return 0


def main():  # pragma: no cover
    description = """Load an RPSL file into the database."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--serial', dest='serial', type=int,
                        help=f'serial number (optional)')
    parser.add_argument('--source', dest='source', type=str, required=True,
                        help=f'name of the source, e.g. NTTCOM')
    parser.add_argument('input_file', type=str,
                        help='the name of a file to read')
    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting('database_readonly'):
        print('Unable to run, because database_readonly is set')
        sys.exit(-1)

    sys.exit(load(args.source, args.input_file, args.serial))


if __name__ == '__main__':  # pragma: no cover
    main()
