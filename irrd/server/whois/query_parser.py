import logging
import re
import threading
from orderedset import OrderedSet
from typing import Optional, List, Set, Tuple

from IPy import IP

from irrd import __version__
from irrd.conf import get_setting
from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING, lookup_field_names
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, DatabaseStatusQuery
from irrd.utils.validators import parse_as_number, ValidationError
from .query_response import WhoisQueryResponseType, WhoisQueryResponseMode, WhoisQueryResponse

logger = logging.getLogger(__name__)


class WhoisQueryParserException(ValueError):
    """
    This exception can be thrown by parsers of individual commands, and
    is handled in WhoisQueryParser.handle_query to be turned into a
    WhoisQueryResponse with a suitable error message.
    """
    pass


class WhoisQueryParser:
    """
    Parser for all whois-style queries.

    This parser distinguishes RIPE-style, e.g. "-K 192.0.2.1" or "-i mnt-by FOO"
    from IRRD-style, e.g. "!oFOO".

    Some query flags, particularly -k/!! and -s/!s retain state across queries,
    so a single instance of this object should be created per session, with
    handle_query() being called for each individual query.
    """
    lookup_field_names = lookup_field_names()
    database_handler: DatabaseHandler

    def __init__(self, peer: str) -> None:
        self.all_valid_sources = list(get_setting('sources').keys())
        self.sources: List[str] = []
        self.object_classes: List[str] = []
        self.user_agent: Optional[str] = None
        self.multiple_command_mode = False
        self.key_fields_only = False
        self.peer = peer

        # The WhoisQueryParser itself should not run concurrently,
        # as answers could arrive out of order.
        self.safe_to_run_query = threading.Event()
        self.safe_to_run_query.set()

    def handle_query(self, query: str) -> WhoisQueryResponse:
        """Process a single query. Always returns a WhoisQueryResponse object."""
        # These flags are reset with every query.
        self.safe_to_run_query.wait()
        self.safe_to_run_query.clear()
        self.database_handler = DatabaseHandler()
        self.key_fields_only = False
        self.object_classes = []

        if query.startswith('!'):
            try:
                return self.handle_irrd_command(query[1:])
            except WhoisQueryParserException as exc:
                logger.info(f'{self.peer}: encountered parsing error while parsing query "{query}": {exc}')
                return WhoisQueryResponse(
                    response_type=WhoisQueryResponseType.ERROR,
                    mode=WhoisQueryResponseMode.IRRD,
                    result=str(exc)
                )
            except Exception as exc:
                logger.critical(f'An exception occurred while processing whois query "{query}": {exc}', exc_info=exc)
                return WhoisQueryResponse(
                    response_type=WhoisQueryResponseType.ERROR,
                    mode=WhoisQueryResponseMode.IRRD,
                    result='An internal error occurred while processing this query.'
                )
            finally:
                self.database_handler.close()
                self.safe_to_run_query.set()

        try:
            return self.handle_ripe_command(query)
        except WhoisQueryParserException as exc:
            logger.info(f'{self.peer}: encountered parsing error while parsing query "{query}": {exc}')
            return WhoisQueryResponse(
                response_type=WhoisQueryResponseType.ERROR,
                mode=WhoisQueryResponseMode.RIPE,
                result=str(exc)
            )
        except Exception as exc:
            logger.critical(f'An exception occurred while processing whois query "{query}": {exc}', exc_info=exc)
            return WhoisQueryResponse(
                response_type=WhoisQueryResponseType.ERROR,
                mode=WhoisQueryResponseMode.RIPE,
                result='An internal error occurred while processing this query.'
            )
        finally:
            self.database_handler.close()
            self.safe_to_run_query.set()

    def handle_irrd_command(self, full_command: str) -> WhoisQueryResponse:
        """Handle an IRRD-style query. full_command should not include the first exclamation mark. """
        if not full_command:
            raise WhoisQueryParserException(f'Missing IRRD command')
        command = full_command[0].upper()
        parameter = full_command[1:]
        response_type = WhoisQueryResponseType.SUCCESS
        result = None

        if command == '!':
            self.multiple_command_mode = True
            result = None
        elif command == 'G':
            result = self.handle_irrd_routes_for_origin_v4(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == '6':
            result = self.handle_irrd_routes_for_origin_v6(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'I':
            result = self.handle_irrd_set_members(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'J':
            result = self.handle_irrd_database_serial_range(parameter)
        elif command == 'M':
            result = self.handle_irrd_exact_key(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'N':
            self.handle_user_agent(parameter)
        elif command == 'O':
            result = self.handle_inverse_attr_search('mnt-by', parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'R':
            result = self.handle_irrd_route_search(parameter)
            if not result:
                response_type = WhoisQueryResponseType.KEY_NOT_FOUND
        elif command == 'S':
            result = self.handle_irrd_sources_list(parameter)
        elif command == 'V':
            result = self.handle_irrd_version()
        else:
            raise WhoisQueryParserException(f'Unrecognised command: {command}')

        return WhoisQueryResponse(
            response_type=response_type,
            mode=WhoisQueryResponseMode.IRRD,
            result=result,
        )

    def handle_irrd_routes_for_origin_v4(self, origin: str) -> str:
        """!g query - find all originating IPv4 prefixes from an origin, e.g. !gAS65537"""
        return self._routes_for_origin('route', origin)

    def handle_irrd_routes_for_origin_v6(self, origin: str) -> str:
        """!6 query - find all originating IPv6 prefixes from an origin, e.g. !6as65537"""
        return self._routes_for_origin('route6', origin)

    def _routes_for_origin(self, object_class: str, origin: str) -> str:
        """
        Resolve all route(6)s for an origin, returning a space-separated list
        of all originating prefixes, not including duplicates.
        """
        try:
            _, asn = parse_as_number(origin)
        except ValidationError as ve:
            raise WhoisQueryParserException(str(ve))

        query = self._prepare_query().object_classes([object_class]).asn(asn)
        query_result = self.database_handler.execute_query(query)

        prefixes = [r['parsed_data'][object_class] for r in query_result]
        return ' '.join(OrderedSet(prefixes))

    def handle_irrd_set_members(self, parameter: str) -> str:
        """
        !i query - find all members of an as-set or route-set, possibly recursively.
        e.g. !iAS-FOO for non-recursive, !iAS-FOO,1 for recursive
        """
        recursive = False
        if parameter.endswith(',1'):
            recursive = True
            parameter = parameter[:-2]

        self._current_set_priority_source = None
        if not recursive:
            members, leaf_members = self._find_set_members({parameter})
            members.update(leaf_members)
        else:
            members = self._recursive_set_resolve({parameter})
        if parameter in members:
            members.remove(parameter)
        return ' '.join(sorted(members))

    def _recursive_set_resolve(self, members: Set[str], sets_seen=None) -> Set[str]:
        """
        Resolve all members of a number of sets, recursively.

        For each set in members, determines whether it has been seen already (to prevent
        infinite recursion), ignores it if already seen, and then either adds
        it directly or adds it to a set that requires further resolving.
        """
        if not sets_seen:
            sets_seen = set()

        if all([member in sets_seen for member in members]):
            return set()
        sets_seen.update(members)

        set_members = set()
        sub_members, leaf_members = self._find_set_members(members)

        for sub_member in sub_members:
            try:
                IP(sub_member)
                set_members.add(sub_member)
                continue
            except ValueError:
                pass
            try:
                parse_as_number(sub_member)
                set_members.add(sub_member)
                continue
            except ValueError:
                pass

        further_resolving_required = sub_members - set_members - sets_seen
        new_members = self._recursive_set_resolve(further_resolving_required, sets_seen)
        set_members.update(new_members)

        return set_members

    def _find_set_members(self, set_names: Set[str]) -> Tuple[Set[str], Set[str]]:
        """
        Find all members of a number of route-sets or as-sets. Includes both
        direct members listed in members attribute, but also
        members included by mbrs-by-ref/member-of.

        Returns a tuple of two sets:
        - members found of the sets included in set_names, both
          references to other sets and direct AS numbers, etc.
        - leaf members that were included in set_names, i.e.
          names for which no further data could be found - for
          example references to non-existent other sets
        """
        members: Set[str] = set()
        sets_already_resolved: Set[str] = set()

        query = self._prepare_query().object_classes(['as-set', 'route-set']).rpsl_pks(set_names)
        if self._current_set_priority_source:
            query.prioritise_source(self._current_set_priority_source)
        query_result = list(self.database_handler.execute_query(query))

        if not query_result:
            # No sub-members are found, and apparantly all inputs were leaf members.
            return set(), set_names

        # Track the source of the root object set
        if not self._current_set_priority_source:
            self._current_set_priority_source = query_result[0]['source']

        for result in query_result:
            rpsl_pk = result['rpsl_pk']

            # The same PK may occur in multiple sources, but we are
            # only interested in the first matching object, prioritised
            # to look for the same source as the root object. This priority
            # is part of the query ORDER BY, so basically we only process
            # an RPSL pk once.
            if rpsl_pk in sets_already_resolved:
                continue
            sets_already_resolved.add(rpsl_pk)

            object_class = result['object_class']
            object_data = result['parsed_data']
            mbrs_by_ref = object_data.get('mbrs-by-ref', None)
            for members_attr in ['members', 'mp-members']:
                if members_attr in object_data:
                    members.update(set(object_data[members_attr]))

            if not rpsl_pk or not object_class or not mbrs_by_ref:
                continue

            # If mbrs-by-ref is set, find any objects with member-of pointing to the route/as-set
            # under query, and include a maintainer listed in mbrs-by-ref, unless mbrs-by-ref
            # is set to ANY.
            query_object_class = ['route', 'route6'] if object_class == 'route-set' else ['aut-num']
            query = self._prepare_query().object_classes(query_object_class)
            query = query.lookup_attrs_in(['member-of'], [rpsl_pk])

            if 'ANY' not in [m.strip().upper() for m in mbrs_by_ref]:
                query = query.lookup_attrs_in(['mnt-by'], mbrs_by_ref)

            referring_objects = self.database_handler.execute_query(query)

            for result in referring_objects:
                member_object_class = result['object_class']
                members.add(result['parsed_data'][member_object_class])

        leaf_members = set_names - sets_already_resolved
        return members, leaf_members

    def handle_irrd_database_serial_range(self, parameter: str) -> str:
        """!j query - database serial range"""
        if parameter == '-*':
            default = get_setting('sources_default')
            sources = default if default else self.all_valid_sources
        else:
            sources = [s.upper() for s in parameter.split(',')]
        invalid_sources = [s for s in sources if s not in self.all_valid_sources]
        query = DatabaseStatusQuery().sources(sources)
        query_results = self.database_handler.execute_query(query)

        result_txt = ''
        for query_result in query_results:
            source = query_result['source'].upper()
            keep_journal = 'Y' if get_setting(f'sources.{source}.keep_journal') else 'N'
            serial_oldest = query_result['serial_oldest_journal']
            serial_newest = query_result['serial_newest_journal']
            fields = [
                source,
                keep_journal,
                f'{serial_oldest}-{serial_newest}' if serial_oldest and serial_newest else '-',
            ]
            if query_result['serial_last_export']:
                fields.append(str(query_result['serial_last_export']))
            result_txt += ':'.join(fields) + '\n'

        for invalid_source in invalid_sources:
            result_txt += f'{invalid_source.upper()}:X:Database unknown\n'
        return result_txt.strip()

    def handle_irrd_exact_key(self, parameter: str):
        """!m query - exact object key lookup, e.g. !maut-num,AS65537"""
        try:
            object_class, rpsl_pk = parameter.split(',', maxsplit=1)
        except ValueError:
            raise WhoisQueryParserException(f'Invalid argument for object lookup: {parameter}')
        query = self._prepare_query().object_classes([object_class]).rpsl_pk(rpsl_pk).first_only()
        return self._execute_query_flatten_output(query)

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
            raise WhoisQueryParserException(f'Invalid input for route search: {parameter}')

        query = self._prepare_query().object_classes(['route', 'route6'])
        if option is None or option == 'o':
            query = query.ip_exact(address)
        elif option == 'l':
            query = query.ip_less_specific_one_level(address)
        elif option == 'L':
            query = query.ip_less_specific(address)
        elif option == 'M':
            query = query.ip_more_specific(address)
        else:
            raise WhoisQueryParserException(f'Invalid route search option: {option}')

        if option == 'o':
            query_result = self.database_handler.execute_query(query)
            prefixes = [r['parsed_data']['origin'] for r in query_result]
            return ' '.join(prefixes)
        return self._execute_query_flatten_output(query)

    def handle_irrd_sources_list(self, parameter: str) -> Optional[str]:
        """
        !s query - set used sources
           !s-lc returns all enabled sources, space separated
           !sripe,nttcom limits sources to ripe and nttcom
        """
        if parameter == '-lc':
            default = get_setting('sources_default')
            sources_selected = default if default else self.all_valid_sources
            return ','.join(sources_selected)
        if parameter:
            sources = parameter.upper().split(',')
            if not all([source in self.all_valid_sources for source in sources]):
                raise WhoisQueryParserException("One or more selected sources are unavailable.")
            self.sources = sources
        else:
            raise WhoisQueryParserException("One or more selected sources are unavailable.")
        return None

    def handle_irrd_version(self):
        """!v query - return version"""
        return f'IRRD -- version {__version__}'

    def handle_ripe_command(self, full_query: str) -> WhoisQueryResponse:
        """
        Process RIPE-style queries. Any query that is not explicitly an IRRD-style
        query (i.e. starts with exclamation mark) is presumed to be a RIPE query.
        """
        full_query = re.sub(' +', ' ', full_query)
        components = full_query.strip().split(' ')
        result = None
        response_type = WhoisQueryResponseType.SUCCESS

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
                    elif command in ['F', 'r']:
                        continue  # These flags disable recursion, but IRRd never performs recursion anyways
                    else:
                        raise WhoisQueryParserException(f'Unrecognised flag/search: {command}')
                except IndexError:
                    raise WhoisQueryParserException(f'Missing argument for flag/search: {command}')
            else:  # assume query to be a free text search
                result = self.handle_ripe_text_search(component)

        return WhoisQueryResponse(
            response_type=response_type,
            mode=WhoisQueryResponseMode.RIPE,
            result=result,
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
            raise WhoisQueryParserException(f'Invalid input for route search: {parameter}')

        query = self._prepare_query().object_classes(['route', 'route6'])
        if command == 'x':
            query = query.ip_exact(address)
        elif command == 'l':
            query = query.ip_less_specific_one_level(address)
        elif command == 'L':
            query = query.ip_less_specific(address)
        elif command == 'M':
            query = query.ip_more_specific(address)

        return self._execute_query_flatten_output(query)

    def handle_ripe_sources_list(self, sources_list: Optional[str]) -> None:
        """-s/-a parameter - set sources list. Empty list enables all sources. """
        if sources_list:
            sources = sources_list.upper().split(',')
            if not all([source in self.all_valid_sources for source in sources]):
                raise WhoisQueryParserException("One or more selected sources are unavailable.")
            self.sources = sources
        else:
            self.sources = []

    def handle_ripe_restrict_object_class(self, object_classes) -> None:
        """-T parameter - restrict object classes for this query, comma-seperated"""
        self.object_classes = object_classes.split(',')

    def handle_ripe_request_object_template(self, object_class) -> str:
        """-t query - return the RPSL template for an object class"""
        try:
            return OBJECT_CLASS_MAPPING[object_class]().generate_template()
        except KeyError:
            raise WhoisQueryParserException(f'Unknown object class: {object_class}')

    def handle_ripe_key_fields_only(self) -> None:
        """-K paramater - only return primary key and members fields"""
        self.key_fields_only = True

    def handle_ripe_text_search(self, value: str) -> str:
        query = self._prepare_query().text_search(value)
        return self._execute_query_flatten_output(query)

    def handle_user_agent(self, user_agent: str):
        """-V/!n parameter/query - set a user agent for the client"""
        self.user_agent = user_agent
        logger.info(f'{self.peer}: user agent set to: {user_agent}')

    def handle_inverse_attr_search(self, attribute: str, value: str) -> str:
        """
        -i/!o query - inverse search for attribute values
        e.g. `-i mnt-by FOO` finds all objects where (one of the) maintainer(s) is FOO,
        as does `!oFOO`. Restricted to designated lookup fields.
        """
        if attribute not in self.lookup_field_names:
            readable_lookup_field_names = ", ".join(self.lookup_field_names)
            msg = (f'Inverse attribute search not supported for {attribute},' +
                   f'only supported for attributes: {readable_lookup_field_names}')
            raise WhoisQueryParserException(msg)
        query = self._prepare_query().lookup_attr(attribute, value)
        return self._execute_query_flatten_output(query)

    def _prepare_query(self) -> RPSLDatabaseQuery:
        """Prepare an RPSLDatabaseQuery by applying relevant sources/class filters."""
        query = RPSLDatabaseQuery()
        if self.sources:
            query.sources(self.sources)
        else:
            default = get_setting('sources_default')
            if default:
                query.sources(list(default))
        if self.object_classes:
            query.object_classes(self.object_classes)
        return query

    def _execute_query_flatten_output(self, query: RPSLDatabaseQuery) -> str:
        """
        Execute an RPSLDatabaseQuery, and flatten the output into a string with object text
        for easy passing to a WhoisQueryResponse.
        """
        query_response = self.database_handler.execute_query(query)
        if self.key_fields_only:
            result = self._filter_key_fields(query_response)
        else:
            result = ''
            for obj in query_response:
                result += obj['object_text'] + '\n'
        return result.strip('\n\r')

    def _filter_key_fields(self, query_response) -> str:
        results = OrderedSet()
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
