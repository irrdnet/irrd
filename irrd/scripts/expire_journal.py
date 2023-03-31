#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import logging
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pytz

"""
Remove journal entries from IRRd.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import CONFIG_PATH_DEFAULT, config_init, get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseJournalQuery


def expire_journal(skip_confirmation: bool, expire_before: datetime, source: str):
    dh = DatabaseHandler()

    q = (
        RPSLDatabaseJournalQuery(column_names=["timestamp"])
        .sources([source])
        .entries_before_date(expire_before)
    )
    affected_object_count = len(list(dh.execute_query(q)))

    if not affected_object_count:
        print("No journal entries found to expire.")
        dh.close()
        return 1

    if not skip_confirmation:
        print(
            textwrap.dedent(
                f"""
                Found {affected_object_count} journal entries to delete from the journal for {source}.
                This is the only record of history kept by IRRd itself.
                After deletion, this can not be recovered.
                
                To confirm deleting these entries for {source}, type 'yes':
                """
            ).strip()
        )
        confirmation = input("> ")
        if confirmation != "yes":
            print("Deletion cancelled.")
            dh.close()
            return 2

    dh.delete_journal_entries_before_date(expire_before, source)
    dh.commit()
    dh.close()
    print("Expiry complete.")
    return 0


def main():  # pragma: no cover
    description = """Remove journal entries from IRRd. NOTE: the journal is the only record IRRd keeps of object history, removal is irrevocable."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        dest="config_file_path",
        type=str,
        help=f"use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})",
    )
    parser.add_argument(
        "--delete-this-history-irrevocably-without-confirmation",
        dest="skip_confirmation",
        action="store_true",
        help=f"use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})",
    )
    parser.add_argument(
        "--expire-before",
        type=str,
        required=True,
        help="expire all entries from before this date (YYYY-MM-DD)",
    )
    parser.add_argument("--source", type=str, required=True, help="the name of the source to reload")

    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting("database_readonly"):
        print("Unable to run, because database_readonly is set")
        sys.exit(-1)

    try:
        expire_before = pytz.utc.localize(datetime.strptime(args.expire_before, "%Y-%m-%d"))
    except ValueError:
        print("Invalid date or date format")
        sys.exit(-1)
    sys.exit(expire_journal(args.skip_confirmation, expire_before, args.source))


if __name__ == "__main__":  # pragma: no cover
    main()
