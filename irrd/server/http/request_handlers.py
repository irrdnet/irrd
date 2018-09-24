import datetime
import logging
import socket
import textwrap
from typing import Optional

from beautifultable import BeautifulTable
from twisted.internet import reactor

from irrd import __version__
from irrd.conf import get_setting
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.storage.api import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery
from irrd.utils.whois_client import whois_query_source_status

logger = logging.getLogger(__name__)


class DatabaseStatusRequest:

    def generate_status(self) -> str:
        database_handler = DatabaseHandler()

        statistics_query = RPSLDatabaseObjectStatisticsQuery()
        self.statistics_results = list(database_handler.execute_query(statistics_query))
        status_query = RPSLDatabaseStatusQuery()
        self.status_results = list(database_handler.execute_query(status_query))

        results = [self._generate_header(), self._generate_statistics_table(), self._generate_mirror_detail()]
        database_handler.close()
        return '\n\n'.join(results)

    def _generate_header(self) -> str:
        return textwrap.dedent(f"""
        IRRD version {__version__}
        Listening on {get_setting("server.whois.interface")} port {get_setting("server.whois.port")}
        Next mirror update: in {self._next_mirror_update()}
        """).lstrip()

    def _generate_statistics_table(self) -> str:
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
            last_export = status_result['serial_last_dump']
            if not last_export:
                last_export = ''
            table.append_row([source, total_obj, route_obj, autnum_obj, serial, last_export])

        total_obj, route_obj, autnum_obj = self._statistics_for_source(None)
        table.append_row(['TOTAL', total_obj, route_obj, autnum_obj, '', ''])

        return str(table)

    def _statistics_for_source(self, source: Optional[str]):
        if source:
            source_statistics = [s for s in self.statistics_results if s['source'] == source]
        else:
            source_statistics = self.statistics_results

        total_obj = sum([s['count'] for s in source_statistics])
        route_obj = sum([s['count'] for s in source_statistics if s['object_class'] == 'route'])
        autnum_obj = sum([s['count'] for s in source_statistics if s['object_class'] == 'aut-num'])
        return total_obj, route_obj, autnum_obj

    def _generate_mirror_detail(self) -> str:
        result_txt = ''
        for status_result in self.status_results:
            source = status_result['source'].upper()
            keep_journal = 'Yes' if get_setting(f'sources.{source}.keep_journal') else 'No'
            authoritative = 'Yes' if get_setting(f'sources.{source}.authoritative') else 'No'
            object_class_filter = get_setting(f'sources.{source}.object_class_filter')
            nrtm_host = get_setting(f'sources.{source}.nrtm_host')
            nrtm_port = get_setting(f'sources.{source}.nrtm_port')

            if nrtm_host and nrtm_port:
                try:
                    source_status = whois_query_source_status(nrtm_host, nrtm_port, source)
                    mirrorable, mirror_serial_oldest, mirror_serial_newest, mirror_dump_serial = source_status
                    mirrorable_str = 'Yes' if mirrorable else 'No'
                    remote_information = textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Mirrorable: {mirrorable_str}
                    Oldest journal serial number: {mirror_serial_oldest}
                    Newest journal serial number: {mirror_serial_newest}
                    Last export at serial number: {mirror_dump_serial}
                    """)
                except ValueError:
                    remote_information = textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Remote status query unsupported
                    """)
                except socket.timeout:
                    remote_information = textwrap.dedent(f"""
                    NRTM host: {nrtm_host} port {nrtm_port}
                    Unable to reach remote server for status query
                    """)
            else:
                remote_information = textwrap.dedent(f"""
                No NRTM host configured.
                """)

            remote_information = textwrap.indent(remote_information, ' ' * 16)
            result_txt += textwrap.dedent(f"""
            Status for {source}
            -------------------
            Local information:
                Authoritative: {authoritative}
                Object class filter: {object_class_filter}
                Oldest serial seen: {status_result['serial_oldest_seen']}
                Newest serial seen: {status_result['serial_newest_seen']}
                Oldest journal serial number: {status_result['serial_oldest_journal']}
                Newest journal serial number: {status_result['serial_newest_journal']}
                Last export at serial number: {status_result['serial_last_dump']}
                Last update: {status_result['updated']}
                Local journal kept: {keep_journal}
                Last import error occurred at: {status_result['last_error_timestamp']}

            Remote information:{remote_information}
            """)
        return result_txt

    def _next_mirror_update(self) -> str:  # pragma: no cover
        next_mirror_update: Optional[int] = None
        for call in reactor.getDelayedCalls():
            try:
                if call.func.f.__func__ == MirrorScheduler.run:
                    next_mirror_update = int(call.getTime() - reactor.seconds())
            except AttributeError:
                pass
        if not next_mirror_update:
            return 'unknown'
        if next_mirror_update < 60:
            return f'{next_mirror_update} seconds'
        return str(datetime.timedelta(seconds=next_mirror_update))
