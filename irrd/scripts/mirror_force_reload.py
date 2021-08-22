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

from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting

from irrd.storage.database_handler import DatabaseHandler

def set_force_reload(source) -> None:
    dh = DatabaseHandler()
    dh.set_force_reload(source)
    dh.commit()
    dh.close()


def main():  # pragma: no cover
    description = """Force a full reload for a mirror."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('source', type=str,
                        help='the name of the source to reload')
    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting('database_readonly'):
        print('Unable to run, because database_readonly is set')
        sys.exit(-1)

    set_force_reload(args.source)


if __name__ == '__main__':  # pragma: no cover
    main()
