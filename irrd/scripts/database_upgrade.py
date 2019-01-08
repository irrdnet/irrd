#!/usr/bin/env python
# flake8: noqa: E402
import sys

import argparse
import os
from alembic import command
from alembic.config import Config

irrd_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.append(irrd_root)

from irrd.conf import config_init, CONFIG_PATH_DEFAULT


def run(version):
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", f'{irrd_root}/irrd/storage/alembic')
    command.upgrade(alembic_cfg, version)
    print(f'Upgrade successful, or already on latest version.')


def main():  # pragma: no cover
    description = """Process a raw email message with requested changes. Authentication is checked, message
                     is always read from stdin. A report is sent to the user by email, along with any
                     notifications to mntners and others."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--version', dest='version', type=str, default='head',
                        help=f'version to upgrade to (default: head, i.e. latest)')
    args = parser.parse_args()

    config_init(args.config_file_path)
    run(args.version)


if __name__ == "__main__":  # pragma: no cover
    main()
