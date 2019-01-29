#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import logging
import sys

from pathlib import Path

from irrd.storage.preload import send_reload_signal

"""
Load an RPSL file into the database.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT
from irrd.mirroring.parsers import MirrorFileImportParser
from irrd.storage.database_handler import DatabaseHandler


def load(source, filename, serial, irrd_pidfile) -> int:
    dh = DatabaseHandler(enable_preload_update=False)
    dh.delete_all_rpsl_objects_with_journal(source)
    dh.disable_journaling()
    parser = MirrorFileImportParser(source, filename, serial=serial, database_handler=dh, direct_error_return=True)
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
    description = """Load an RPSL file into the database."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--irrd_pidfile', dest='irrd_pidfile', type=str, required=True,
                        help=f'path to the PID file for the running irrd instance')
    parser.add_argument('--serial', dest='serial', type=int,
                        help=f'serial number (optional)')
    parser.add_argument('--source', dest='source', type=str, required=True,
                        help=f'name of the source, e.g. NTTCOM')
    parser.add_argument('input_file', type=str,
                        help='the name of a file to read')
    args = parser.parse_args()

    config_init(args.config_file_path)

    sys.exit(load(args.source, args.input_file, args.serial, args.irrd_pidfile))


if __name__ == '__main__':  # pragma: no cover
    main()
