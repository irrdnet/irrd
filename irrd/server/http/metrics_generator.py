import datetime
import logging
import os
import textwrap
import time
from collections.abc import Iterable
from typing import Any

from irrd import ENV_MAIN_STARTUP_TIME, __version__
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery

logger = logging.getLogger(__name__)


class MetricsGenerator:
    def generate(self) -> str:
        """
        Generate a machine-readable overview of database status.
        """
        database_handler = DatabaseHandler()

        statistics_query = RPSLDatabaseObjectStatisticsQuery()
        statistics_results = list(database_handler.execute_query(statistics_query))
        status_query = DatabaseStatusQuery()
        status_results = list(database_handler.execute_query(status_query))

        statistics = sorted(statistics_results, key=lambda item: f"{item['source']}-{item['object_class']}")
        status = sorted(status_results, key=lambda item: item["source"])

        results = [
            self._generate_header(),
            self._generate_object_counts(statistics),
            self._generate_rpsl_data_updated(status),
            self._generate_updated(status),
            self._generate_last_error(status),
            self._generate_field(
                status,
                "nrtm4_client_version",
                "irrd_nrtm4_client_version",
                "Newest NRTMv4 version mirrored from upstream",
            ),
            self._generate_field(
                status,
                "serial_newest_mirror",
                "irrd_mirrored_serial",
                "Newest serial NRTMv3 number mirrored from upstream",
            ),
            self._generate_field(
                status, "serial_last_export", "irrd_last_export_serial", "Last serial number for full export"
            ),
            self._generate_field(
                status, "serial_oldest_journal", "irrd_oldest_journal_serial", "Oldest serial in the journal"
            ),
            self._generate_field(
                status, "serial_newest_journal", "irrd_newest_journal_serial", "Newest serial in the journal"
            ),
        ]
        database_handler.close()
        return "\n".join(results) + "\n"

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
        """).strip() + "\n"

    def _generate_object_counts(self, statistics: Iterable[dict[str, Any]]) -> str:
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
        """).lstrip() + "\n".join(lines) + "\n"

    def _generate_rpsl_data_updated(self, status: Iterable[dict[str, Any]]) -> str:
        """
        Generate statistics about the time since last update
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        lines = [
            "# HELP irrd_last_rpsl_data_update_seconds Seconds since the last update to RPSL data",
            "# TYPE irrd_last_rpsl_data_update_seconds gauge",
        ]
        for stat in status:
            if stat.get("rpsl_data_updated"):
                diff = now - stat["rpsl_data_updated"]
                lines.append(
                    f"""irrd_last_rpsl_data_update_seconds{{source="{stat['source']}"}} {int(diff.total_seconds())}"""
                )

        lines += [
            "",
            (
                "# HELP irrd_last_rpsl_data_update_timestamp Timestamp of the last update to RPSL data in"
                " seconds since UNIX epoch"
            ),
            "# TYPE irrd_last_rpsl_data_update_timestamp gauge",
        ]

        for stat in status:
            if stat.get("rpsl_data_updated"):
                lines.append(
                    f"""irrd_last_rpsl_data_update_timestamp{{source="{stat['source']}"}} """
                    f"""{int(stat['rpsl_data_updated'].timestamp())}"""
                )

        return "\n".join(lines) + "\n"

    def _generate_updated(self, status: Iterable[dict[str, Any]]) -> str:
        """
        Generate statistics about the time since last update
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        lines = [
            "# HELP irrd_last_update_seconds Seconds since the last internal status change",
            "# TYPE irrd_last_update_seconds gauge",
        ]
        for stat in status:
            if stat.get("updated"):
                diff = now - stat["updated"]
                lines.append(
                    f"""irrd_last_update_seconds{{source="{stat['source']}"}} {int(diff.total_seconds())}"""
                )

        lines += [
            "",
            (
                "# HELP irrd_last_update_timestamp Timestamp of the last internal status change in seconds"
                " since UNIX epoch"
            ),
            "# TYPE irrd_last_update_timestamp gauge",
        ]

        for stat in status:
            if stat.get("updated"):
                lines.append(
                    f"""irrd_last_update_timestamp{{source="{stat['source']}"}} """
                    f"""{int(stat['updated'].timestamp())}"""
                )

        return "\n".join(lines) + "\n"

    def _generate_last_error(self, status: Iterable[dict[str, Any]]) -> str:
        """
        Generate statistics about the time since last update
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        lines = [
            "# HELP irrd_last_error_seconds Seconds since the last mirroring error",
            "# TYPE irrd_last_error_seconds gauge",
        ]
        for stat in status:
            if stat.get("last_error_timestamp"):
                diff = now - stat["last_error_timestamp"]
                lines.append(
                    f"""irrd_last_error_seconds{{source="{stat['source']}"}} """
                    f"""{int(diff.total_seconds())}"""
                )

        lines += [
            "",
            (
                "# HELP irrd_last_error_timestamp Timestamp of the last mirroring error in seconds since UNIX"
                " epoch"
            ),
            "# TYPE irrd_last_error_timestamp gauge",
        ]
        for stat in status:
            if stat.get("last_error_timestamp"):
                lines.append(
                    f"""irrd_last_error_timestamp{{source="{stat['source']}"}} """
                    f"""{int(stat['last_error_timestamp'].timestamp())}"""
                )

        return "\n".join(lines) + "\n"

    def _generate_field(self, status: Iterable[dict[str, Any]], status_key, metric_key, help_text) -> str:
        """
        Generate simple statistics for various fields
        """
        lines = []
        for stat in status:
            if stat.get(status_key):
                lines.append(f"""{metric_key}{{source="{stat['source']}"}} {stat[status_key]}""")

        return textwrap.dedent(f"""
        # HELP {metric_key} {help_text}
        # TYPE {metric_key} gauge
        """).lstrip() + "\n".join(lines) + "\n"
