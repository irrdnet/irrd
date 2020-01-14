#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import logging
import sys

from pathlib import Path

from irrd.storage.preload import send_reload_signal

"""
Update a database based on a RPSL file.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting
from irrd.mirroring.parsers import MirrorUpdateFileImportParser
from irrd.storage.database_handler import DatabaseHandler


def update(source, filename, irrd_pidfile) -> int:
    if any([
        get_setting(f'sources.{source}.import_source'),
        get_setting(f'sources.{source}.import_serial_source')
    ]):
        print(f'Error: to use this command, import_source and import_serial_source '
              f'for source {source} must not be set.')
        return 2

    dh = DatabaseHandler(enable_preload_update=False)
    parser = MirrorUpdateFileImportParser(source, filename, database_handler=dh, direct_error_return=True)
    error = parser.run_import()
    if error:
        dh.rollback()
    else:
        dh.commit()
        send_reload_signal(irrd_pidfile)
    dh.close()
    if error:
        print(f'Error occurred while processing object:\n{error}')
        return 1
    return 0


def main():  # pragma: no cover
    description = """Update a database based on a RPSL file."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--irrd_pidfile', dest='irrd_pidfile', type=str, required=True,
                        help=f'path to the PID file for the running irrd instance')
    parser.add_argument('--source', dest='source', type=str, required=True,
                        help=f'name of the source, e.g. NTTCOM')
    parser.add_argument('input_file', type=str,
                        help='the name of a file to read')
    args = parser.parse_args()

    config_init(args.config_file_path)

    sys.exit(update(args.source, args.input_file, args.irrd_pidfile))


if __name__ == '__main__':  # pragma: no cover
    main()
