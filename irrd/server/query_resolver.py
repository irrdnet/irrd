import logging
from collections import OrderedDict
from enum import Enum
from typing import Any, Optional

from IPy import IP
from ordered_set import OrderedSet
from pytz import timezone

from irrd.conf import (
    RPKI_IRR_PSEUDO_SOURCE,
    get_object_class_filter_for_source,
    get_setting,
)
from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING, lookup_field_names
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.database_handler import (
    DatabaseHandler,
    RPSLDatabaseResponse,
    is_serial_synchronised,
)
from irrd.storage.preload import Preloader
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseQuery
from irrd.utils.validators import parse_as_number

logger = logging.getLogger(__name__)


class InvalidQueryException(ValueError):
    pass


class RouteLookupType(Enum):
    EXACT = "EXACT"
    LESS_SPECIFIC_ONE_LEVEL = "LESS_SPECIFIC_ONE_LEVEL"
    LESS_SPECIFIC_WITH_EXACT = "LESS_SPECIFIC_WITH_EXACT"
    MORE_SPECIFIC_WITHOUT_EXACT = "MORE_SPECIFIC_WITHOUT_EXACT"


class QuerySourceManager:
    """
    The QuerySourceManager manages the source availability and selection.
    Other than looking at the sources setting, this considers whether RPKI
    is enabled and any configured aliases.
    """

    def __init__(self):
        self.all_valid_real_sources = list(get_setting("sources", {}).keys())
        if get_setting("rpki.roa_source"):
            self.all_valid_real_sources.append(RPKI_IRR_PSEUDO_SOURCE)
        self.all_valid_aliases = dict(get_setting("source_aliases", {}))
        self.all_valid_sources = self.all_valid_real_sources + list(self.all_valid_aliases.keys())
        self.sources_default = list(get_setting("sources_default", []))
        self.sources: list[str] = self.sources_default if self.sources_default else self.all_valid_sources

    def set_query_sources(self, sources: Optional[list[str]]) -> None:
        """Set the sources for future queries.
        If sources is None, default source list is set.
        May include alias names."""
        if sources is None:
            sources = self.sources_default if self.sources_default else self.all_valid_sources
        elif not all([source in self.all_valid_sources for source in sources]):
            raise InvalidQueryException("One or more selected sources are unavailable.")
        self.sources = sources

    @property
    def sources_resolved(self) -> list[str]:
        """
        Returns a list of all resolved source names, i.e. real names
        with aliases resolved into their individual sources.
        Names are guaranteed to be unique.
        """
        sources: OrderedSet[str] = OrderedSet()
        for source in self.sources:
            if source in self.all_valid_real_sources:
                sources.add(source)
            if source in get_setting("source_aliases", {}):
                sources.update(get_setting(f"source_aliases.{source}"))

        return list(sources)


class QueryResolver:
    """
    Resolver for all RPSL queries.

    Some aspects like setting sources retain state, so a single instance
    should not be shared across unrelated query sessions.
    """

    lookup_field_names = lookup_field_names()
    database_handler: DatabaseHandler
    _current_set_root_object_class: Optional[str]

    def __init__(self, preloader: Preloader, database_handler: DatabaseHandler) -> None:
        self.source_manager = QuerySourceManager()
        self.object_class_filter: list[str] = []
        self.rpki_aware = bool(get_setting("rpki.roa_source"))
        self.rpki_invalid_filter_enabled = self.rpki_aware
        self.out_scope_filter_enabled = True
        self.route_preference_filter_enabled = True
        self.user_agent: Optional[str] = None
        self.preloader = preloader
        self.database_handler = database_handler
        self.sql_queries: list[str] = []
        self.sql_trace = False

    def set_query_sources(self, sources: Optional[list[str]]) -> None:
        self.source_manager.set_query_sources(sources)

    def disable_rpki_filter(self) -> None:
        self.rpki_invalid_filter_enabled = False

    def disable_out_of_scope_filter(self) -> None:
        self.out_scope_filter_enabled = False

    def disable_route_preference_filter(self) -> None:
        self.route_preference_filter_enabled = False

    def set_object_class_filter_next_query(self, object_classes: list[str]) -> None:
        """Restrict object classes for the next query, comma-seperated"""
        self.object_class_filter = object_classes

    def key_lookup(self, object_class: str, rpsl_pk: str) -> RPSLDatabaseResponse:
        """RPSL exact key lookup."""
        query = self._prepare_query().object_classes([object_class]).rpsl_pk(rpsl_pk).first_only()
        return self._execute_query(query)

    def rpsl_text_search(self, value: str) -> RPSLDatabaseResponse:
        query = self._prepare_query(ordered_by_sources=False).text_search(value)
        return self._execute_query(query)

    def route_search(self, address: IP, lookup_type: RouteLookupType):
        """Route(6) object search for an address, supporting exact/less/more specific."""
        query = self._prepare_query(ordered_by_sources=False).object_classes(["route", "route6"])
        lookup_queries = {
            RouteLookupType.EXACT: query.ip_exact,
            RouteLookupType.LESS_SPECIFIC_ONE_LEVEL: query.ip_less_specific_one_level,
            RouteLookupType.LESS_SPECIFIC_WITH_EXACT: query.ip_less_specific,
            RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT: query.ip_more_specific,
        }
        query = lookup_queries[lookup_type](address)
        return self._execute_query(query)

    def rpsl_attribute_search(self, attribute: str, value: str) -> RPSLDatabaseResponse:
        """
        -i/!o query - inverse search for attribute values
        e.g. `-i mnt-by FOO` finds all objects where (one of the) maintainer(s) is FOO,
        as does `!oFOO`. Restricted to designated lookup fields.
        """
        if attribute not in self.lookup_field_names:
            readable_lookup_field_names = ", ".join(self.lookup_field_names)
            msg = (
                f"Inverse attribute search not supported for {attribute},"
                + f"only supported for attributes: {readable_lookup_field_names}"
            )
            raise InvalidQueryException(msg)
        query = self._prepare_query(ordered_by_sources=False).lookup_attr(attribute, value)
        return self._execute_query(query)

    def routes_for_origin(self, origin: str, ip_version: Optional[int] = None) -> set[str]:
        """
        Resolve all route(6)s prefixes for an origin, returning a set
        of all prefixes. Origin must be in 'ASxxx' format.
        """
        prefixes = self.preloader.routes_for_origins(
            [origin], self.source_manager.sources_resolved, ip_version=ip_version
        )
        return prefixes

    def routes_for_as_set(
        self, set_name: str, ip_version: Optional[int] = None, exclude_sets: Optional[set[str]] = None
    ) -> set[str]:
        """
        Find all originating prefixes for all members of an AS-set. May be restricted
        to IPv4 or IPv6. Returns a set of all prefixes.
        """
        self._current_set_root_object_class = "as-set"
        self._current_excluded_sets = exclude_sets if exclude_sets else set()
        self._current_set_maximum_depth = 0
        members = self._recursive_set_resolve({set_name})
        return self.preloader.routes_for_origins(
            members, self.source_manager.sources_resolved, ip_version=ip_version
        )

    def members_for_set_per_source(
        self, parameter: str, exclude_sets: Optional[set[str]] = None, depth=0, recursive=False
    ) -> dict[str, list[str]]:
        """
        Find all members of an as-set or route-set, possibly recursively, distinguishing
        between multiple root objects in different sources with the same name.
        Returns a dict with sources as keys, list of all members, including leaf members,
        as values.
        """
        query = self._prepare_query(column_names=["source"])
        object_classes = ["as-set", "route-set"]
        query = query.object_classes(object_classes).rpsl_pk(parameter)
        set_sources = [row["source"] for row in self._execute_query(query)]

        return {
            source: self.members_for_set(
                parameter=parameter,
                exclude_sets=exclude_sets,
                depth=depth,
                recursive=recursive,
                root_source=source,
            )
            for source in set_sources
        }

    def members_for_set(
        self,
        parameter: str,
        exclude_sets: Optional[set[str]] = None,
        depth=0,
        recursive=False,
        root_source: Optional[str] = None,
    ) -> list[str]:
        """
        Find all members of an as-set or route-set, possibly recursively.
        Returns a list of all members, including leaf members.
        If root_source is set, the root object is only looked for in that source -
        resolving is then continued using the currently set sources.
        """
        self._current_set_root_object_class = None
        self._current_excluded_sets = exclude_sets if exclude_sets else set()
        self._current_set_maximum_depth = depth
        if not recursive:
            members, leaf_members = self._find_set_members({parameter}, limit_source=root_source)
            members.update(leaf_members)
        else:
            members = self._recursive_set_resolve({parameter}, root_source=root_source)
        if parameter in members:
            members.remove(parameter)

        if get_setting("compatibility.ipv4_only_route_set_members"):
            original_members = set(members)
            for member in original_members:
                try:
                    IP(member)
                except ValueError:
                    continue  # This is not a prefix, ignore.
                try:
                    IP(member, ipversion=4)
                except ValueError:
                    # This was a valid prefix, but not a valid IPv4 prefix,
                    # and should be removed.
                    members.remove(member)

        return sorted(members)

    def _recursive_set_resolve(
        self, members: set[str], sets_seen=None, root_source: Optional[str] = None
    ) -> set[str]:
        """
        Resolve all members of a number of sets, recursively.

        For each set in members, determines whether it has been seen already (to prevent
        infinite recursion), ignores it if already seen, and then either adds
        it directly or adds it to a set that requires further resolving.
        If root_source is set, the root object is only looked for in that source -
        resolving is then continued using the currently set sources.
        """
        if not sets_seen:
            sets_seen = set()

        if all([member in sets_seen for member in members]):
            return set()
        sets_seen.update(members)

        set_members = set()

        resolved_as_members = set()
        sub_members, leaf_members = self._find_set_members(members, limit_source=root_source)

        for sub_member in sub_members:
            if (
                self._current_set_root_object_class is None
                or self._current_set_root_object_class == "route-set"
            ):
                try:
                    IP(sub_member.split("^")[0])
                    set_members.add(sub_member)
                    continue
                except ValueError:
                    pass
            # AS numbers are permitted in route-sets and as-sets, per RFC 2622 5.3.
            # When an AS number is encountered as part of route-set resolving,
            # the prefixes originating from that AS should be added to the response.
            try:
                as_number_formatted, _ = parse_as_number(sub_member)
                if self._current_set_root_object_class == "route-set":
                    set_members.update(
                        self.preloader.routes_for_origins(
                            [as_number_formatted], self.source_manager.sources_resolved
                        )
                    )
                    resolved_as_members.add(sub_member)
                else:
                    set_members.add(sub_member)
                continue
            except ValueError:
                pass

        self._current_set_maximum_depth -= 1
        if self._current_set_maximum_depth == 0:
            return set_members | sub_members | leaf_members

        further_resolving_required = (
            sub_members - set_members - sets_seen - resolved_as_members - self._current_excluded_sets
        )
        new_members = self._recursive_set_resolve(further_resolving_required, sets_seen)
        set_members.update(new_members)

        return set_members

    def _find_set_members(
        self, set_names: set[str], limit_source: Optional[str] = None
    ) -> tuple[set[str], set[str]]:
        """
        Find all members of a number of route-sets or as-sets. Includes both
        direct members listed in members attribute, but also
        members included by mbrs-by-ref/member-of.
        If limit_source is set, the set_names are only looked for in that source.

        Returns a tuple of two sets:
        - members found of the sets included in set_names, both
          references to other sets and direct AS numbers, etc.
        - leaf members that were included in set_names, i.e.
          names for which no further data could be found - for
          example references to non-existent other sets
        """
        members: set[str] = set()
        leaf_members = set()

        sources = self.source_manager.sources_resolved if not limit_source else [limit_source]
        # Per RFC 2622 5.3, route-sets can refer to as-sets,
        # but as-sets can only refer to other as-sets.
        if self._current_set_root_object_class == "as-set":
            object_classes = [self._current_set_root_object_class]
        else:
            object_classes = ["route-set", "as-set"]

        for set_name in set_names:
            set_members = self.preloader.set_members(set_name, sources, object_classes)
            if set_members is None:
                leaf_members.add(set_name)
            else:
                members.update(set_members.members)
                if not self._current_set_root_object_class:
                    self._current_set_root_object_class = set_members.object_class

        return members, leaf_members

    def database_status(
        self, sources: Optional[list[str]] = None
    ) -> "OrderedDict[str, OrderedDict[str, Any]]":
        """Database status. If sources is None, return all valid sources."""
        if sources is None:
            sources = self.source_manager.all_valid_sources
        invalid_sources = [s for s in sources if s not in self.source_manager.all_valid_sources]
        query = DatabaseStatusQuery().sources(sources)
        query_results = self._execute_query(query)

        results: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
        for query_result in query_results:
            source = query_result["source"].upper()
            results[source] = OrderedDict()
            results[source]["source_type"] = "regular"
            results[source]["authoritative"] = get_setting(f"sources.{source}.authoritative", False)
            results[source]["object_class_filter"] = get_object_class_filter_for_source(source)
            results[source]["rpki_rov_filter"] = bool(
                get_setting("rpki.roa_source") and not get_setting(f"sources.{source}.rpki_excluded")
            )
            results[source]["scopefilter_enabled"] = bool(get_setting("scopefilter")) and not get_setting(
                f"sources.{source}.scopefilter_excluded"
            )
            results[source]["route_preference"] = get_setting(f"sources.{source}.route_object_preference")
            results[source]["local_journal_kept"] = get_setting(f"sources.{source}.keep_journal", False)
            results[source]["serial_oldest_journal"] = query_result["serial_oldest_journal"]
            results[source]["serial_newest_journal"] = query_result["serial_newest_journal"]
            results[source]["serial_last_export"] = query_result["serial_last_export"]
            results[source]["serial_newest_mirror"] = query_result["serial_newest_mirror"]
            results[source]["nrtm4_client_session_id"] = (
                str(query_result["nrtm4_client_session_id"])
                if query_result["nrtm4_client_session_id"]
                else None
            )
            results[source]["nrtm4_client_version"] = query_result["nrtm4_client_version"]
            results[source]["nrtm4_server_session_id"] = (
                str(query_result["nrtm4_server_session_id"])
                if query_result["nrtm4_server_session_id"]
                else None
            )
            results[source]["nrtm4_server_version"] = query_result["nrtm4_server_version"]
            results[source]["nrtm4_server_last_update_notification_file_update"] = (
                query_result["nrtm4_server_last_update_notification_file_update"]
                .astimezone(timezone("UTC"))
                .isoformat()
                if query_result["nrtm4_server_last_update_notification_file_update"]
                else None
            )
            results[source]["nrtm4_server_last_snapshot_version"] = query_result[
                "nrtm4_server_last_snapshot_version"
            ]
            results[source]["rpsl_data_updated"] = (
                query_result["rpsl_data_updated"].astimezone(timezone("UTC")).isoformat()
            )
            results[source]["last_update"] = query_result["updated"].astimezone(timezone("UTC")).isoformat()
            results[source]["synchronised_serials"] = is_serial_synchronised(self.database_handler, source)

        results.update(
            {
                s: OrderedDict(
                    source_type="alias", aliased_sources=list(self.source_manager.all_valid_aliases[s])
                )
                for s in sources
                if s in self.source_manager.all_valid_aliases
            }
        )
        for invalid_source in invalid_sources:
            results[invalid_source.upper()] = OrderedDict({"error": "Unknown source"})
        return results

    def rpsl_object_template(self, object_class) -> str:
        """Return the RPSL template for an object class"""
        try:
            return OBJECT_CLASS_MAPPING[object_class]().generate_template()
        except KeyError:
            raise InvalidQueryException(f"Unknown object class: {object_class}")

    def enable_sql_trace(self):
        self.sql_trace = True

    def retrieve_sql_trace(self) -> list[str]:
        trace = self.sql_queries
        self.sql_trace = False
        self.sql_queries = []
        return trace

    def _prepare_query(self, column_names=None, ordered_by_sources=True) -> RPSLDatabaseQuery:
        """Prepare an RPSLDatabaseQuery by applying relevant sources/class filters."""
        query = RPSLDatabaseQuery(column_names, ordered_by_sources)
        if self.source_manager.sources_resolved:
            query.sources(self.source_manager.sources_resolved)
        if self.object_class_filter:
            query.object_classes(self.object_class_filter)
        if self.rpki_invalid_filter_enabled:
            query.rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
        if self.out_scope_filter_enabled:
            query.scopefilter_status([ScopeFilterStatus.in_scope])
        if self.route_preference_filter_enabled:
            query.route_preference_status([RoutePreferenceStatus.visible])
        self.object_class_filter = []
        return query

    def _execute_query(self, query) -> RPSLDatabaseResponse:
        if self.sql_trace:
            self.sql_queries.append(repr(query))
        return self.database_handler.execute_query(query, refresh_on_error=True)
