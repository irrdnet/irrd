import datetime
import logging
import os
import textwrap
import time
from typing import Any, Dict, Iterable

from irrd import ENV_MAIN_STARTUP_TIME, __version__
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery

logger = logging.getLogger(__name__)


class MetricsGenerator:

    def generate_metrics(self) -> str:
        """
        Generate a machine-readable overview of database status.
        """
        database_handler = DatabaseHandler()

        statistics_query = RPSLDatabaseObjectStatisticsQuery()
        statistics_results = list(database_handler.execute_query(statistics_query))
        status_query = DatabaseStatusQuery()
        status_results = list(database_handler.execute_query(status_query))

        statistics = sorted(statistics_results, key=lambda item: f"{item['source']}-{item['object_class']}")
        status = sorted(status_results, key=lambda item: item['source'])

        results = [
            self._generate_header(),
            self._generate_object_counts(statistics),
            self._generate_updated(status),
            self._generate_last_error(status),
            self._generate_newest_mirror_serial(status),
            self._generate_last_export_serial(status),
            self._generate_oldest_journal_serial(status),
            self._generate_newest_journal_serial(status),
        ]
        database_handler.close()
        return '\n'.join(results) + '\n'

    def _generate_header(self) -> str:
        """
        Generate the header of the report, containing basic info like version and uptime
        """
        return textwrap.dedent(f"""
        # HELP irrd_info Info from IRRd, value is always 1
        # TYPE irrd_info gauge
        irrd_info{{version="{__version__}"}} 1
        
        # HELP irrd_uptime_seconds Uptime of IRRd in seconds
        # TYPE irrd_uptime_seconds gauge
        irrd_uptime_seconds {int(time.time()) - int(os.environ[ENV_MAIN_STARTUP_TIME])}
        
        # HELP irrd_startup_timestamp Startup time of IRRd in seconds since UNIX epoch
        # TYPE irrd_startup_timestamp gauge
        irrd_startup_timestamp {os.environ[ENV_MAIN_STARTUP_TIME]}
        """).strip() + '\n'

    def _generate_object_counts(self, statistics: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the number of object types per source
        """
        lines = []
        for stat in statistics:
            lines.append(
                f"""irrd_object_class_total{{source="{stat['source']}", object_class="{stat['object_class']}"}} """
                f"""{stat['count']}"""
            )

        return textwrap.dedent("""
        # HELP irrd_object_class_total Number of objects per class per source
        # TYPE irrd_object_class_total gauge
        """).lstrip() + '\n'.join(lines) + '\n'

    def _generate_updated(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the time since last update
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        lines = [
            "# HELP irrd_last_update_seconds Seconds since the last update",
            "# TYPE irrd_last_update_seconds gauge"
        ]
        for stat in status:
            if 'updated' not in stat or stat['updated'] is None:
                continue
            diff = now - stat['updated']
            lines.append(f"""irrd_last_update_seconds{{source="{stat['source']}"}} {int(diff.total_seconds())}""")

        lines += [
            "",
            "# HELP irrd_last_update_timestamp Timestamp of the last update in seconds since UNIX epoch",
            "# TYPE irrd_last_update_timestamp gauge"
        ]

        for stat in status:
            if 'updated' not in stat or stat['updated'] is None:
                continue
            lines.append(f"""irrd_last_update_timestamp{{source="{stat['source']}"}} """
                         f"""{int(stat['updated'].timestamp())}""")

        return '\n'.join(lines) + '\n'

    def _generate_last_error(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the time since last update
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        lines = [
            "# HELP irrd_last_error_seconds Seconds since the last error",
            "# TYPE irrd_last_error_seconds gauge"
        ]
        for stat in status:
            if 'last_error_timestamp' in stat and stat['last_error_timestamp'] is not None:
                diff = now - stat['last_error_timestamp']
                lines.append(f"""irrd_last_error_seconds{{source="{stat['source']}"}} """
                             f"""{int(diff.total_seconds())}""")

        lines += [
            "",
            "# HELP irrd_last_error_timestamp Timestamp of the last error in seconds since UNIX epoch",
            "# TYPE irrd_last_error_timestamp gauge"
        ]
        for stat in status:
            if 'last_error_timestamp' in stat and stat['last_error_timestamp'] is not None:
                lines.append(f"""irrd_last_error_timestamp{{source="{stat['source']}"}} """
                             f"""{int(stat['last_error_timestamp'].timestamp())}""")

        return '\n'.join(lines) + '\n'

    def _generate_newest_mirror_serial(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the newest mirrored serial
        """
        lines = []
        for stat in status:
            if 'serial_newest_mirror' not in stat or stat['serial_newest_mirror'] is None:
                continue
            lines.append(f"""irrd_mirrored_serial{{source="{stat['source']}"}} {stat['serial_newest_mirror']}""")

        return textwrap.dedent("""
        # HELP irrd_mirrored_serial Newest serial number mirrored from upstream
        # TYPE irrd_mirrored_serial gauge
        """).lstrip() + '\n'.join(lines) + '\n'

    def _generate_last_export_serial(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the last export
        """
        lines = []
        for stat in status:
            if 'serial_last_export' not in stat or stat['serial_last_export'] is None:
                continue
            lines.append(f"""irrd_last_export_serial{{source="{stat['source']}"}} {stat['serial_last_export']}""")

        return textwrap.dedent("""
        # HELP irrd_last_export_serial Last serial number exported
        # TYPE irrd_last_export_serial gauge
        """).lstrip() + '\n'.join(lines) + '\n'

    def _generate_oldest_journal_serial(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the oldest serial in the journal
        """
        lines = []
        for stat in status:
            if 'serial_oldest_journal' not in stat or stat['serial_oldest_journal'] is None:
                continue
            lines.append(f"""irrd_oldest_journal_serial{{source="{stat['source']}"}} {stat['serial_oldest_journal']}""")

        return textwrap.dedent("""
        # HELP irrd_oldest_journal_serial Oldest serial in the journal
        # TYPE irrd_oldest_journal_serial gauge
        """).lstrip() + '\n'.join(lines) + '\n'

    def _generate_newest_journal_serial(self, status: Iterable[Dict[str, Any]]) -> str:
        """
        Generate statistics about the last serial in the journal
        """
        lines = []
        for stat in status:
            if 'serial_newest_journal' not in stat or stat['serial_newest_journal'] is None:
                continue
            lines.append(f"""irrd_newest_journal_serial{{source="{stat['source']}"}} {stat['serial_newest_journal']}""")

        return textwrap.dedent("""
        # HELP irrd_newest_journal_serial Newest serial in the journal
        # TYPE irrd_newest_journal_serial gauge
        """).lstrip() + '\n'.join(lines) + '\n'
