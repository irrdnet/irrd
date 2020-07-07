#!/usr/bin/env python
# flake8: noqa: E402
import sys

import argparse
from alembic import command
from alembic.config import Config
from pathlib import Path

irrd_root = str(Path(__file__).resolve().parents[2])
sys.path.append(irrd_root)

from irrd.conf import config_init, CONFIG_PATH_DEFAULT


def run(version):
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', f'{irrd_root}/irrd/storage/alembic')
    command.downgrade(alembic_cfg, version)
    print(f'Downgrade successful, or already on this version.')


def main():  # pragma: no cover
    description = """Downgrade the IRRd SQL database to a particular version by running database migrations. See release notes."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--version', dest='version', type=str, required=True,
                        help=f'version to downgrade to (see release notes)')
    args = parser.parse_args()

    config_init(args.config_file_path)
    run(args.version)


if __name__ == '__main__':  # pragma: no cover
    main()
