import logging
import textwrap

from beautifultable import BeautifulTable

from irrd import __version__
from irrd.conf import get_object_class_filter_for_source, get_setting
from irrd.conf.defaults import DEFAULT_SOURCE_NRTM_PORT
from irrd.storage.database_handler import DatabaseHandler, is_serial_synchronised
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery
from irrd.utils.whois_client import whois_query_source_status

logger = logging.getLogger(__name__)


class StatusGenerator:
    def generate(self) -> str:
        """
        Generate a human-readable overview of database status.
        """
        database_handler = DatabaseHandler()

        statistics_query = RPSLDatabaseObjectStatisticsQuery()
        self.statistics_results = list(database_handler.execute_query(statistics_query))
        status_query = DatabaseStatusQuery()
        self.status_results = list(database_handler.execute_query(status_query))

        results = [
            self._generate_header(),
            self._generate_statistics_table(),
            self._generate_source_detail(database_handler),
        ]
        database_handler.close()
        return "\n\n".join(results)

    def _generate_header(self) -> str:
        """
        Generate the header of the report, containing basic info like version
        and time until the next mirror update.
        """
        return textwrap.dedent(f"""
        IRRD version {__version__}
        Listening on {get_setting('server.whois.interface')} port {get_setting('server.whois.port')}
        """).lstrip()

    def _generate_statistics_table(self) -> str:
        """
        Generate a table with an overview of basic stats for each database.
        """
        table = BeautifulTable(default_alignment=BeautifulTable.ALIGN_RIGHT)
        table.column_headers = ["source", "total obj", "rt obj", "aut-num obj", "serial", "last export"]
        table.column_alignments["source"] = BeautifulTable.ALIGN_LEFT
        table.left_border_char = table.right_border_char = ""
        table.right_border_char = table.bottom_border_char = ""
        table.row_separator_char = ""
        table.column_separator_char = "  "

        for status_result in self.status_results:
            source = status_result["source"].upper()
            total_obj, route_obj, autnum_obj = self._statistics_for_source(source)
            serial = status_result["serial_newest_seen"]
            last_export = status_result["serial_last_export"]
            if not last_export:
                last_export = ""
            table.append_row([source, total_obj, route_obj, autnum_obj, serial, last_export])

        total_obj, route_obj, autnum_obj = self._statistics_for_source(None)
        table.append_row(["TOTAL", total_obj, route_obj, autnum_obj, "", ""])

        return str(table)

    def _statistics_for_source(self, source: str | None):
        """
        Extract counts of total objects, route objects and aut-num objects,
        from the results of a previous SQL query.
        If source is None, all sources are counted.
        """
        if source:
            source_statistics = [s for s in self.statistics_results if s["source"] == source]
        else:
            source_statistics = self.statistics_results

        total_obj = sum([s["count"] for s in source_statistics])
        route_obj = sum([s["count"] for s in source_statistics if s["object_class"] == "route"])
        autnum_obj = sum([s["count"] for s in source_statistics if s["object_class"] == "aut-num"])
        return total_obj, route_obj, autnum_obj

    def _generate_source_detail(self, database_handler: DatabaseHandler) -> str:
        """
        Generate status details for each database.

        This includes local configuration, local database status metadata,
        and serial information queried from the remote NRTM host,
        queried by _generate_remote_status_info().
        :param database_handler:
        """
        result_txt = ""
        for status_result in self.status_results:
            source = status_result["source"].upper()
            keep_journal = "Yes" if get_setting(f"sources.{source}.keep_journal") else "No"
            authoritative = "Yes" if get_setting(f"sources.{source}.authoritative") else "No"
            object_class_filter = get_object_class_filter_for_source(source)
            object_class_filter_str = ",".join(object_class_filter) if object_class_filter else "None"
            rpki_enabled = get_setting("rpki.roa_source") and not get_setting(
                f"sources.{source}.rpki_excluded"
            )
            rpki_enabled_str = "Yes" if rpki_enabled else "No"
            scopefilter_enabled = get_setting("scopefilter") and not get_setting(
                f"sources.{source}.scopefilter_excluded"
            )
            scopefilter_enabled_str = "Yes" if scopefilter_enabled else "No"
            synchronised_serials_str = "Yes" if is_serial_synchronised(database_handler, source) else "No"
            route_object_preference = get_setting(f"sources.{source}.route_object_preference")

            nrtm_host = get_setting(f"sources.{source}.nrtm_host")
            nrtm_port = int(get_setting(f"sources.{source}.nrtm_port", DEFAULT_SOURCE_NRTM_PORT))
            nrtm4_notification_file_url = get_setting(f"sources.{source}.nrtm4_client_notification_file_url")

            remote_information = self._generate_remote_status_info(
                nrtm_host, nrtm_port, nrtm4_notification_file_url, source
            )
            remote_information = textwrap.indent(remote_information, " " * 16)

            result_txt += textwrap.dedent(f"""
            Status for {source}
            -------------------
            Local information:
                Authoritative: {authoritative}
                Object class filter: {object_class_filter_str}
                Oldest serial seen: {status_result['serial_oldest_seen']}
                Newest serial seen: {status_result['serial_newest_seen']}
                Oldest local journal serial number: {status_result['serial_oldest_journal']}
                Newest local journal serial number: {status_result['serial_newest_journal']}
                Last export at serial number: {status_result['serial_last_export']}
                Newest serial number mirrored: {status_result['serial_newest_mirror']}
                NRTMv4 client: current session: {status_result['nrtm4_client_session_id']}
                NRTMv4 client: current version: {status_result['nrtm4_client_version']}
                NRTMv4 server: current session: {status_result['nrtm4_server_session_id']}
                NRTMv4 server: current version: {status_result['nrtm4_server_version']}
                NRTMv4 server: last Update Notification File update: {status_result['nrtm4_server_last_update_notification_file_update']}
                NRTMv4 server: last snapshot version: {status_result['nrtm4_server_last_snapshot_version']}
                NRTMv4 server: number of deltas: {len(status_result['nrtm4_server_previous_deltas'] or [])}
                Synchronised NRTM serials: {synchronised_serials_str}
                Last change to RPSL data: {status_result['rpsl_data_updated']}
                Last internal status update: {status_result['updated']}
                Local journal kept: {keep_journal}
                Last import error occurred at: {status_result['last_error_timestamp']}
                RPKI validation enabled: {rpki_enabled_str}
                Scope filter enabled: {scopefilter_enabled_str}
                Route object preference: {route_object_preference}

            Remote information:{remote_information}
            """)
        return result_txt

    def _generate_remote_status_info(
        self,
        nrtm_host: str | None,
        nrtm_port: int,
        nrtm4_notification_file_url: str | None,
        source: str,
    ) -> str:
        """
        Determine the remote status.

        If NRTM is configured, this will include querying the NRTM
        source for serial information. Various error states will produce
        an appropriate remote status message for the report.
        """
        if nrtm4_notification_file_url:
            return textwrap.dedent(f"""
                NRTMv4 client Update Notification File URL: {nrtm4_notification_file_url}
                """)
        elif nrtm_host:
            try:
                source_status = whois_query_source_status(nrtm_host, nrtm_port, source)
                mirrorable, mirror_serial_oldest, mirror_serial_newest, mirror_export_serial = source_status
                mirrorable_str = "Yes" if mirrorable else "No"

                return textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Mirrorable: {mirrorable_str}
                    Oldest journal serial number: {mirror_serial_oldest}
                    Newest journal serial number: {mirror_serial_newest}
                    Last export at serial number: {mirror_export_serial}
                    """)
            except ValueError:
                return textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Remote status query unsupported or query failed
                    """)
            except OSError:
                return textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Unable to reach remote server for status query
                    """)
        else:
            return textwrap.dedent("""
                No NRTM configured.
                """)
