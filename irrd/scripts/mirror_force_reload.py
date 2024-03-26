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

from irrd.conf import CONFIG_PATH_DEFAULT, config_init, get_setting
from irrd.storage.database_handler import DatabaseHandler


def set_force_reload(source) -> None:
    if not any(
        [
            get_setting(f"sources.{source}.nrtm4_client_notification_file_url"),
            get_setting(f"sources.{source}.nrtm_host"),
            get_setting(f"sources.{source}.import_source"),
        ]
    ):
        print(
            f"You can only set the force reload flag for sources that are a mirror. Source {source} has"
            " neither nrtm4_client_notification_file_url, nrtm_host, or import_source set."
        )
        return
    if get_setting(f"sources.{source}.nrtm4_client_initial_public_key"):
        print(
            "Note: the reload flag will be set on the source, but existing NRTMv4 client key information is"
            " kept. To revert to the key currently set in the"
            f" sources.{source}.nrtm4_client_initial_public_key setting, use 'irrdctl nrtmv4"
            " client-clear-known-keys'"
        )

    dh = DatabaseHandler()
    dh.set_force_reload(source)
    dh.commit()
    dh.close()


def main():  # pragma: no cover
    description = """Force a full reload for a mirror."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        dest="config_file_path",
        type=str,
        help=f"use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})",
    )
    parser.add_argument("source", type=str, help="the name of the source to reload")
    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting("readonly_standby"):
        print("Unable to run, because readonly_standby is set")
        sys.exit(-1)

    set_force_reload(args.source)


if __name__ == "__main__":  # pragma: no cover
    main()
