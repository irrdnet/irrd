#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

irrd_root = str(Path(__file__).resolve().parents[2])
sys.path.append(irrd_root)

from irrd.conf import CONFIG_PATH_DEFAULT, config_init


def run(version):
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", f"{irrd_root}/irrd/storage/alembic")
    command.upgrade(alembic_cfg, version)
    print(f"Upgrade successful, or already on latest version.")


def main():  # pragma: no cover
    description = """Upgrade the IRRd SQL database to a particular version by running database migrations."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        dest="config_file_path",
        type=str,
        help=f"use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})",
    )
    parser.add_argument(
        "--version",
        dest="version",
        type=str,
        default="head",
        help=f"version to upgrade to (default: head, i.e. latest)",
    )
    args = parser.parse_args()

    config_init(args.config_file_path)
    run(args.version)


if __name__ == "__main__":  # pragma: no cover
    main()
