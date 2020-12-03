import logging
import socket
import textwrap
from typing import Optional

from beautifultable import BeautifulTable

from irrd import __version__
from irrd.conf import get_setting
from irrd.conf.defaults import DEFAULT_SOURCE_NRTM_PORT
from irrd.storage.database_handler import DatabaseHandler, is_serial_synchronised
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery
from irrd.utils.whois_client import whois_query_source_status

logger = logging.getLogger(__name__)


class StatusGenerator:

    def generate_status(self) -> str:
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
            self._generate_source_detail(database_handler)
        ]
        database_handler.close()
        return '\n\n'.join(results)

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
        table.column_headers = ['source', 'total obj', 'rt obj', 'aut-num obj', 'serial', 'last export']
        table.column_alignments['source'] = BeautifulTable.ALIGN_LEFT
        table.left_border_char = table.right_border_char = ''
        table.right_border_char = table.bottom_border_char = ''
        table.row_separator_char = ''
        table.column_separator_char = '  '

        for status_result in self.status_results:
            source = status_result['source'].upper()
            total_obj, route_obj, autnum_obj = self._statistics_for_source(source)
            serial = status_result['serial_newest_seen']
            last_export = status_result['serial_last_export']
            if not last_export:
                last_export = ''
            table.append_row([source, total_obj, route_obj, autnum_obj, serial, last_export])

        total_obj, route_obj, autnum_obj = self._statistics_for_source(None)
        table.append_row(['TOTAL', total_obj, route_obj, autnum_obj, '', ''])

        return str(table)

    def _statistics_for_source(self, source: Optional[str]):
        """
        Extract counts of total objects, route objects and aut-num objects,
        from the results of a previous SQL query.
        If source is None, all sources are counted.
        """
        if source:
            source_statistics = [s for s in self.statistics_results if s['source'] == source]
        else:
            source_statistics = self.statistics_results

        total_obj = sum([s['count'] for s in source_statistics])
        route_obj = sum([s['count'] for s in source_statistics if s['object_class'] == 'route'])
        autnum_obj = sum([s['count'] for s in source_statistics if s['object_class'] == 'aut-num'])
        return total_obj, route_obj, autnum_obj

    def _generate_source_detail(self, database_handler: DatabaseHandler) -> str:
        """
        Generate status details for each database.

        This includes local configuration, local database status metadata,
        and serial information queried from the remote NRTM host,
        queried by _generate_remote_status_info().
        :param database_handler:
        """
        result_txt = ''
        for status_result in self.status_results:
            source = status_result['source'].upper()
            keep_journal = 'Yes' if get_setting(f'sources.{source}.keep_journal') else 'No'
            authoritative = 'Yes' if get_setting(f'sources.{source}.authoritative') else 'No'
            object_class_filter = get_setting(f'sources.{source}.object_class_filter')
            rpki_enabled = get_setting('rpki.roa_source') and not get_setting(f'sources.{source}.rpki_excluded')
            rpki_enabled_str = 'Yes' if rpki_enabled else 'No'
            scopefilter_enabled = get_setting('scopefilter') and not get_setting(f'sources.{source}.scopefilter_excluded')
            scopefilter_enabled_str = 'Yes' if scopefilter_enabled else 'No'
            synchronised_serials_str = 'Yes' if is_serial_synchronised(database_handler, source) else 'No'

            nrtm_host = get_setting(f'sources.{source}.nrtm_host')
            nrtm_port = int(get_setting(f'sources.{source}.nrtm_port', DEFAULT_SOURCE_NRTM_PORT))

            remote_information = self._generate_remote_status_info(nrtm_host, nrtm_port, source)
            remote_information = textwrap.indent(remote_information, ' ' * 16)

            result_txt += textwrap.dedent(f"""
            Status for {source}
            -------------------
            Local information:
                Authoritative: {authoritative}
                Object class filter: {object_class_filter}
                Oldest serial seen: {status_result['serial_oldest_seen']}
                Newest serial seen: {status_result['serial_newest_seen']}
                Oldest local journal serial number: {status_result['serial_oldest_journal']}
                Newest local journal serial number: {status_result['serial_newest_journal']}
                Last export at serial number: {status_result['serial_last_export']}
                Newest serial number mirrored: {status_result['serial_newest_mirror']}
                Synchronised NRTM serials: {synchronised_serials_str}
                Last update: {status_result['updated']}
                Local journal kept: {keep_journal}
                Last import error occurred at: {status_result['last_error_timestamp']}
                RPKI validation enabled: {rpki_enabled_str}
                Scope filter enabled: {scopefilter_enabled_str}

            Remote information:{remote_information}
            """)
        return result_txt

    def _generate_remote_status_info(self, nrtm_host: Optional[str], nrtm_port: int, source: str) -> str:
        """
        Determine the remote status.

        If NRTM is configured, this will include querying the NRTM
        source for serial information. Various error states will produce
        an appropriate remote status message for the report.
        """
        if nrtm_host:
            try:
                source_status = whois_query_source_status(nrtm_host, nrtm_port, source)
                mirrorable, mirror_serial_oldest, mirror_serial_newest, mirror_export_serial = source_status
                mirrorable_str = 'Yes' if mirrorable else 'No'

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
            except (socket.timeout, ConnectionError):
                return textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Unable to reach remote server for status query
                    """)
        else:
            return textwrap.dedent("""
                No NRTM host configured.
                """)
