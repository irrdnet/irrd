import logging
import re
from typing import Optional

import ujson
from IPy import IP
from ordered_set import OrderedSet

from irrd import __version__
from irrd.conf import get_setting, RPKI_IRR_PSEUDO_SOURCE, SOCKET_DEFAULT_TIMEOUT
from irrd.mirroring.nrtm_generator import NRTMGenerator, NRTMGeneratorException
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import (OBJECT_CLASS_MAPPING, RPKI_RELEVANT_OBJECT_CLASSES)
from irrd.server.query_resolver import QueryResolver, RouteLookupType, InvalidQueryException
from irrd.storage.database_handler import DatabaseHandler, RPSLDatabaseResponse
from irrd.storage.preload import Preloader
from irrd.storage.queries import DatabaseStatusQuery
from irrd.utils.validators import parse_as_number, ValidationError
from .query_response import WhoisQueryResponseType, WhoisQueryResponseMode, WhoisQueryResponse
from ..access_check import is_client_permitted

logger = logging.getLogger(__name__)


class WhoisQueryParser:
    """
    Parser for all whois-style queries.

    This parser distinguishes RIPE-style, e.g. '-K 192.0.2.1' or '-i mnt-by FOO'
    from IRRD-style, e.g. '!oFOO'. Query processing is mostly handled by
    QueryResolver, with a few exceptions that are whois-specific.

    Some query flags, particularly -k/!! and -s/!s retain state across queries,
    so a single instance of this object should be created per session, with
    handle_query() being called for each individual query.
    """

    def __init__(self, client_ip: str, client_str: str, preloader: Preloader,
                 database_handler: DatabaseHandler) -> None:
        self.multiple_command_mode = False
        self.timeout = SOCKET_DEFAULT_TIMEOUT
        self.key_fields_only = False
        self.client_ip = client_ip
        self.client_str = client_str
        self.database_handler = database_handler
        self.query_resolver = QueryResolver(
            preloader=preloader,
            database_handler=database_handler,
        )

    def handle_query(self, query: str) -> WhoisQueryResponse:
        """
        Process a single query. Always returns a WhoisQueryResponse object.
        Not thread safe - only one call must be made to this method at the same time.
        """
        self.key_fields_only = False

        if query.startswith('!'):
            try:
                return self.handle_irrd_command(query[1:])
            except InvalidQueryException as exc:
                logger.info(f'{self.client_str}: encountered parsing error while parsing query "{query}": {exc}')
                return WhoisQueryResponse(
                    response_type=WhoisQueryResponseType.ERROR_USER,
                    mode=WhoisQueryResponseMode.IRRD,
                    result=str(exc)
                )
            except Exception as exc:
                logger.error(f'An exception occurred while processing whois query "{query}": {exc}', exc_info=exc)
                return WhoisQueryResponse(
                    response_type=WhoisQueryResponseType.ERROR_INTERNAL,
                    mode=WhoisQueryResponseMode.IRRD,
                    result='An internal error occurred while processing this query.'
                )

        try:
            return self.handle_ripe_command(query)
        except InvalidQueryException as exc:
            logger.info(f'{self.client_str}: encountered parsing error while parsing query "{query}": {exc}')
            return WhoisQueryResponse(
                response_type=WhoisQueryResponseType.ERROR_USER,
                mode=WhoisQueryResponseMode.RIPE,
                result=str(exc)
            )
        except Exception as exc:
            logger.error(f'An exception occurred while processing whois query "{query}": {exc}', exc_info=exc)
            return WhoisQueryResponse(
                response_type=WhoisQueryResponseType.ERROR_INTERNAL,
                mode=WhoisQueryResponseMode.RIPE,
                result='An internal error occurred while processing this query.'
            )

    def handle_irrd_command(self, full_command: str) -> WhoisQueryResponse:
        """Handle an IRRD-style query. full_command should not include the first exclamation mark. """
        if not full_command:
            raise InvalidQueryException('Missing IRRD command')
        command = full_command[0]
        parameter = full_command[1:]
        response_type = WhoisQueryResponseType.SUCCESS
        result = None

        # A is not tested here because it is already handled in handle_irrd_routes_for_as_set
        queries_with_parameter = list('tg6ijmnors')
        if command in queries_with_parameter and not parameter:
            raise InvalidQueryException(f'Missing parameter for {command} query')

        if command == '!':
            self.multiple_command_mode = True
            result = None
            response_type = WhoisQueryResponseType.NO_RESPONSE
        elif full_command.upper() == 'FNO-RPKI-FILTER':
            self.query_resolver.disable_rpki_filter()
            result = 'Filtering out RPKI invalids is disabled for !r and RIPE style ' \
                     'queries for the rest of this connection.'
        elif full_command.upper() == 'FNO-SCOPE-FILTER':
            self.query_resolver.disable_out_of_scope_filter()
            result = 'Filtering out out-of-scope objects is disabled for !r and RIPE style ' \
                     'queries for the rest of this connection.'
        elif command == 'v':
            result = self.handle_irrd_version()
        elif command == 't':
            self.handle_irrd_timeout_update(parameter)
        elif command == 'g':
            result = self.handle_irrd_routes_for_origin_v4(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == '6':
            result = self.handle_irrd_routes_for_origin_v6(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'a':
            result = self.handle_irrd_routes_for_as_set(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'i':
            result = self.handle_irrd_set_members(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'j':
            result = self.handle_irrd_database_serial_range(parameter)
        elif command == 'J':
            result = self.handle_irrd_database_status(parameter)
        elif command == 'm':
            result = self.handle_irrd_exact_key(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'n':
            self.handle_user_agent(parameter)
        elif command == 'o':
            result = self.handle_inverse_attr_search('mnt-by', parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'r':
            result = self.handle_irrd_route_search(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 's':
            result = self.handle_irrd_sources_list(parameter)
        else:
            raise InvalidQueryException(f'Unrecognised command: {command}')

        return WhoisQueryResponse(
            response_type=response_type,
            mode=WhoisQueryResponseMode.IRRD,
            result=result,
        )

    def handle_irrd_timeout_update(self, timeout: str) -> None:
        """!timeout query - update timeout in connection"""
        try:
            timeout_value = int(timeout)
        except ValueError:
            raise InvalidQueryException(f'Invalid value for timeout: {timeout}')

        if timeout_value > 0 and timeout_value <= 1000:
            self.timeout = timeout_value
        else:
            raise InvalidQueryException(f'Invalid value for timeout: {timeout}')

    def handle_irrd_routes_for_origin_v4(self, origin: str) -> str:
        """!g query - find all originating IPv4 prefixes from an origin, e.g. !gAS65537"""
        return self._routes_for_origin(origin, 4)

    def handle_irrd_routes_for_origin_v6(self, origin: str) -> str:
        """!6 query - find all originating IPv6 prefixes from an origin, e.g. !6as65537"""
        return self._routes_for_origin(origin, 6)

    def _routes_for_origin(self, origin: str, ip_version: Optional[int]=None) -> str:
        """
        Resolve all route(6)s prefixes for an origin, returning a space-separated list
        of all originating prefixes, not including duplicates.
        """
        try:
            origin_formatted, _ = parse_as_number(origin)
        except ValidationError as ve:
            raise InvalidQueryException(str(ve))

        prefixes = self.query_resolver.routes_for_origin(origin_formatted, ip_version)
        return ' '.join(prefixes)

    def handle_irrd_routes_for_as_set(self, set_name: str) -> str:
        """
        !a query - find all originating prefixes for all members of an AS-set, e.g. !a4AS-FOO or !a6AS-FOO
        """
        ip_version: Optional[int] = None
        if set_name.startswith('4'):
            set_name = set_name[1:]
            ip_version = 4
        elif set_name.startswith('6'):
            set_name = set_name[1:]
            ip_version = 6

        if not set_name:
            raise InvalidQueryException('Missing required set name for A query')

        prefixes = self.query_resolver.routes_for_as_set(set_name, ip_version)
        return ' '.join(prefixes)

    def handle_irrd_set_members(self, parameter: str) -> str:
        """
        !i query - find all members of an as-set or route-set, possibly recursively.
        e.g. !iAS-FOO for non-recursive, !iAS-FOO,1 for recursive
        """
        recursive = False
        if parameter.endswith(',1'):
            recursive = True
            parameter = parameter[:-2]

        members = self.query_resolver.members_for_set(parameter, recursive=recursive)
        return ' '.join(members)

    def handle_irrd_database_serial_range(self, parameter: str) -> str:
        """
        !j query - database serial range
        This query is legacy and only available in whois, so resolved
        directly here instead of in the query resolver.
        """
        if parameter == '-*':
            sources = self.query_resolver.sources_default if self.query_resolver.sources_default else self.query_resolver.all_valid_sources
        else:
            sources = [s.upper() for s in parameter.split(',')]
        invalid_sources = [s for s in sources if s not in self.query_resolver.all_valid_sources]
        query = DatabaseStatusQuery().sources(sources)
        query_results = self.database_handler.execute_query(query, refresh_on_error=True)

        result_txt = ''
        for query_result in query_results:
            source = query_result['source'].upper()
            keep_journal = 'Y' if get_setting(f'sources.{source}.keep_journal') else 'N'
            serial_newest = query_result['serial_newest_mirror']
            fields = [
                source,
                keep_journal,
                f'0-{serial_newest}' if serial_newest else '-',
            ]
            if query_result['serial_last_export']:
                fields.append(str(query_result['serial_last_export']))
            result_txt += ':'.join(fields) + '\n'

        for invalid_source in invalid_sources:
            result_txt += f'{invalid_source.upper()}:X:Database unknown\n'
        return result_txt.strip()

    def handle_irrd_database_status(self, parameter: str) -> str:
        """!J query - database status"""
        if parameter == '-*':
            sources = None
        else:
            sources = [s.upper() for s in parameter.split(',')]
        results = self.query_resolver.database_status(sources)
        return ujson.dumps(results, indent=4)

    def handle_irrd_exact_key(self, parameter: str):
        """!m query - exact object key lookup, e.g. !maut-num,AS65537"""
        try:
            object_class, rpsl_pk = parameter.split(',', maxsplit=1)
        except ValueError:
            raise InvalidQueryException(f'Invalid argument for object lookup: {parameter}')

        if object_class in ['route', 'route6']:
            rpsl_pk = rpsl_pk.upper().replace(' ', '').replace('-', '')
        query = self.query_resolver.key_lookup(object_class, rpsl_pk)
        return self._flatten_query_output(query)

    def handle_irrd_route_search(self, parameter: str):
        """
        !r query - route search with various options:
           !r192.0.2.0/24 returns all exact matching objects
           !r192.0.2.0/24,o returns space-separated origins of all exact matching objects
           !r192.0.2.0/24,l returns all one-level less specific objects, not including exact
           !r192.0.2.0/24,L returns all less specific objects, including exact
           !r192.0.2.0/24,M returns all more specific objects, not including exact
        """
        option: Optional[str] = None
        if ',' in parameter:
            address, option = parameter.split(',')
        else:
            address = parameter
        try:
            address = IP(address)
        except ValueError:
            raise InvalidQueryException(f'Invalid input for route search: {parameter}')

        lookup_types = {
            None: RouteLookupType.EXACT,
            'o': RouteLookupType.EXACT,
            'l': RouteLookupType.LESS_SPECIFIC_ONE_LEVEL,
            'L': RouteLookupType.LESS_SPECIFIC_WITH_EXACT,
            'M': RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT,
        }
        try:
            lookup_type = lookup_types[option]
        except KeyError:
            raise InvalidQueryException(f'Invalid route search option: {option}')

        result = self.query_resolver.route_search(address, lookup_type)
        if option == 'o':
            prefixes = [r['parsed_data']['origin'] for r in result]
            return ' '.join(prefixes)
        return self._flatten_query_output(result)

    def handle_irrd_sources_list(self, parameter: str) -> Optional[str]:
        """
        !s query - set used sources
           !s-lc returns all enabled sources, space separated
           !sripe,nttcom limits sources to ripe and nttcom
        """
        if parameter == '-lc':
            return ','.join(self.query_resolver.sources)

        sources = parameter.upper().split(',')
        self.query_resolver.set_query_sources(sources)
        return None

    def handle_irrd_version(self):
        """!v query - return version"""
        return f'IRRd -- version {__version__}'

    def handle_ripe_command(self, full_query: str) -> WhoisQueryResponse:
        """
        Process RIPE-style queries. Any query that is not explicitly an IRRD-style
        query (i.e. starts with exclamation mark) is presumed to be a RIPE query.
        """
        full_query = re.sub(' +', ' ', full_query)
        components = full_query.strip().split(' ')
        result = None
        response_type = WhoisQueryResponseType.SUCCESS
        remove_auth_hashes = True

        while len(components):
            component = components.pop(0)
            if component.startswith('-'):
                command = component[1:]
                try:
                    if command == 'k':
                        self.multiple_command_mode = True
                    elif command in ['l', 'L', 'M', 'x']:
                        result = self.handle_ripe_route_search(command, components.pop(0))
                        if not result:
                            response_type = WhoisQueryResponseType.KEY_NOT_FOUND
                        break
                    elif command == 'i':
                        result = self.handle_inverse_attr_search(components.pop(0), components.pop(0))
                        if not result:
                            response_type = WhoisQueryResponseType.KEY_NOT_FOUND
                        break
                    elif command == 's':
                        self.handle_ripe_sources_list(components.pop(0))
                    elif command == 'a':
                        self.handle_ripe_sources_list(None)
                    elif command == 'T':
                        self.handle_ripe_restrict_object_class(components.pop(0))
                    elif command == 't':
                        result = self.handle_ripe_request_object_template(components.pop(0))
                        break
                    elif command == 'K':
                        self.handle_ripe_key_fields_only()
                    elif command == 'V':
                        self.handle_user_agent(components.pop(0))
                    elif command == 'g':
                        result = self.handle_nrtm_request(components.pop(0))
                        remove_auth_hashes = False
                    elif command in ['F', 'r']:
                        continue  # These flags disable recursion, but IRRd never performs recursion anyways
                    else:
                        raise InvalidQueryException(f'Unrecognised flag/search: {command}')
                except IndexError:
                    raise InvalidQueryException(f'Missing argument for flag/search: {command}')
            else:  # assume query to be a free text search
                result = self.handle_ripe_text_search(component)

        return WhoisQueryResponse(
            response_type=response_type,
            mode=WhoisQueryResponseMode.RIPE,
            result=result,
            remove_auth_hashes=remove_auth_hashes,
        )

    def handle_ripe_route_search(self, command: str, parameter: str) -> str:
        """
        -l/L/M/x query - route search for:
           -x 192.0.2.0/2 returns all exact matching objects
           -l 192.0.2.0/2 returns all one-level less specific objects, not including exact
           -L 192.0.2.0/2 returns all less specific objects, including exact
           -M 192.0.2.0/2 returns all more specific objects, not including exact
        """
        try:
            address = IP(parameter)
        except ValueError:
            raise InvalidQueryException(f'Invalid input for route search: {parameter}')

        lookup_types = {
            'x': RouteLookupType.EXACT,
            'l': RouteLookupType.LESS_SPECIFIC_ONE_LEVEL,
            'L': RouteLookupType.LESS_SPECIFIC_WITH_EXACT,
            'M': RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT,
        }
        lookup_type = lookup_types[command]
        result = self.query_resolver.route_search(address, lookup_type)
        return self._flatten_query_output(result)

    def handle_ripe_sources_list(self, sources_list: Optional[str]) -> None:
        """-s/-a parameter - set sources list. Empty list enables all sources. """
        if sources_list:
            sources = sources_list.upper().split(',')
            self.query_resolver.set_query_sources(sources)
        else:
            self.query_resolver.set_query_sources(None)

    def handle_ripe_restrict_object_class(self, object_classes) -> None:
        """-T parameter - restrict object classes for this query, comma-seperated"""
        self.query_resolver.set_object_class_filter_next_query(object_classes.split(','))

    def handle_ripe_request_object_template(self, object_class) -> str:
        """-t query - return the RPSL template for an object class"""
        return self.query_resolver.rpsl_object_template(object_class)

    def handle_ripe_key_fields_only(self) -> None:
        """-K paramater - only return primary key and members fields"""
        self.key_fields_only = True

    def handle_ripe_text_search(self, value: str) -> str:
        result = self.query_resolver.rpsl_text_search(value)
        return self._flatten_query_output(result)

    def handle_user_agent(self, user_agent: str):
        """-V/!n parameter/query - set a user agent for the client"""
        self.query_resolver.user_agent = user_agent
        logger.info(f'{self.client_str}: user agent set to: {user_agent}')

    def handle_nrtm_request(self, param):
        try:
            source, version, serial_range = param.split(':')
        except ValueError:
            raise InvalidQueryException('Invalid parameter: must contain three elements')

        try:
            serial_start, serial_end = serial_range.split('-')
            serial_start = int(serial_start)
            if serial_end == 'LAST':
                serial_end = None
            else:
                serial_end = int(serial_end)
        except ValueError:
            raise InvalidQueryException(f'Invalid serial range: {serial_range}')

        if version not in ['1', '3']:
            raise InvalidQueryException(f'Invalid NRTM version: {version}')

        source = source.upper()
        if source not in self.query_resolver.all_valid_sources:
            raise InvalidQueryException(f'Unknown source: {source}')

        in_access_list = is_client_permitted(self.client_ip, f'sources.{source}.nrtm_access_list', log=False)
        in_unfiltered_access_list = is_client_permitted(self.client_ip, f'sources.{source}.nrtm_access_list_unfiltered', log=False)
        if not in_access_list and not in_unfiltered_access_list:
            raise InvalidQueryException('Access denied')

        try:
            return NRTMGenerator().generate(
                source, version, serial_start, serial_end, self.database_handler,
                remove_auth_hashes=not in_unfiltered_access_list)
        except NRTMGeneratorException as nge:
            raise InvalidQueryException(str(nge))

    def handle_inverse_attr_search(self, attribute: str, value: str) -> str:
        """
        -i/!o query - inverse search for attribute values
        e.g. `-i mnt-by FOO` finds all objects where (one of the) maintainer(s) is FOO,
        as does `!oFOO`. Restricted to designated lookup fields.
        """
        result = self.query_resolver.rpsl_attribute_search(attribute, value)
        return self._flatten_query_output(result)

    def _flatten_query_output(self, query_response: RPSLDatabaseResponse) -> str:
        """
        Flatten an RPSL database response into a string with object text
        for easy passing to a WhoisQueryResponse.
        """
        if self.key_fields_only:
            result = self._filter_key_fields(query_response)
        else:
            result = ''
            for obj in query_response:
                result += obj['object_text']
                if (
                        self.query_resolver.rpki_aware and
                        obj['source'] != RPKI_IRR_PSEUDO_SOURCE and
                        obj['object_class'] in RPKI_RELEVANT_OBJECT_CLASSES
                ):
                    comment = ''
                    if obj['rpki_status'] == RPKIStatus.not_found:
                        comment = ' # No ROAs found, or RPKI validation not enabled for source'
                    result += f'rpki-ov-state:  {obj["rpki_status"].name}{comment}\n'
                result += '\n'
        return result.strip('\n\r')

    def _filter_key_fields(self, query_response) -> str:
        results: OrderedSet[str] = OrderedSet()
        for obj in query_response:
            result = ''
            rpsl_object_class = OBJECT_CLASS_MAPPING[obj['object_class']]
            fields_included = rpsl_object_class.pk_fields + ['members', 'mp-members']

            for field_name in fields_included:
                field_data = obj['parsed_data'].get(field_name)
                if field_data:
                    if isinstance(field_data, list):
                        for item in field_data:
                            result += f'{field_name}: {item}\n'
                    else:
                        result += f'{field_name}: {field_data}\n'
            results.add(result)
        return '\n'.join(results)
