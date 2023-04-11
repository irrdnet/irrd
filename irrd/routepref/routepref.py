import logging
from typing import Dict, Iterable, List, Optional, Tuple

import radix
from IPy import IP
from radix.radix import RadixNode

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery

from .status import RoutePreferenceStatus

logger = logging.getLogger(__name__)
MAX_FILTER_PREFIX_LEN = 5000


class RoutePreferenceValidator:
    """
    The route preference validator determines which route objects
    need their state updated. It operates on an iterable of objects,
    which may be all objects in the database, or a subset for certain
    prefixes. Based on the current preference setting, the validator
    determines new states based on the given set of routes, which
    means for, e.g. a change to a few route objects, you must pass
    the changed objects and any overlapping route objects.
    """

    def __init__(self, existing_route_objects: Iterable[Dict[str, str]]):
        """
        Initialise the validator with an iterable of route objects as dicts.
        The route object dict must have prefix, source, pk and route_preference_status columns.
        """
        self.source_preferences = {
            source_name: int(source_data.get("route_object_preference"))
            for source_name, source_data in get_setting("sources", {}).items()
            if source_data.get("route_object_preference") is not None
        }
        self.max_preference = max(self.source_preferences.values()) if self.source_preferences else None

        self.rtree = radix.Radix()
        self.excluded_currently_suppressed: List[str] = []
        self._build_tree(existing_route_objects)

    def _build_tree(self, route_objects: Iterable[Dict[str, str]]) -> None:
        """
        Build the tree of route objects and their preferences.
        Also sets self.excluded_currently_suppressed as a side effect.
        """
        for route_object in route_objects:
            try:
                preference = self.source_preferences[route_object["source"]]
            except KeyError:
                if route_object["route_preference_status"] != RoutePreferenceStatus.visible:
                    self.excluded_currently_suppressed.append(route_object["pk"])
                continue

            rnode = self.rtree.add(route_object["prefix"])
            if not rnode.data:
                rnode.data = {}
            rnode.data[route_object["pk"]] = (preference, route_object["route_preference_status"])

    def validate_known_routes(self) -> Tuple[List[str], List[str]]:
        """
        Validate all routes known to this validator, based on the
        previously built tree. Returns a tuple of two lists:
        pks of "currently suppressed, should be visible" and vice versa.
        """
        if not self.source_preferences:
            # All objects should be visible if there is no setting,
            # which in that case is caught in self.excluded_currently_suppressed
            # by _build_tree, meaning there is no action here.
            return [], []
        to_be_visible = []
        to_be_suppressed = []
        for evaluated_node in self.rtree:
            search_args = {"packed": evaluated_node.packed, "masklen": evaluated_node.prefixlen}
            overlapping_nodes = self.rtree.search_covered(**search_args) + self.rtree.search_covering(
                **search_args
            )

            for evaluated_key, (evaluated_preference, current_status) in evaluated_node.data.items():
                new_status = self._evaluate_route(evaluated_preference, overlapping_nodes)
                if new_status != current_status:
                    if new_status == RoutePreferenceStatus.suppressed:
                        to_be_suppressed.append(evaluated_key)
                    elif new_status == RoutePreferenceStatus.visible:
                        to_be_visible.append(evaluated_key)
        return to_be_visible, to_be_suppressed

    def _evaluate_route(
        self, route_preference: int, overlapping_nodes: List[RadixNode]
    ) -> RoutePreferenceStatus:
        """
        Given a preference, evaluate the correct state of a route based
        on a given list of overlapping nodes.
        """
        if route_preference == self.max_preference:
            return RoutePreferenceStatus.visible

        for overlapping_node in overlapping_nodes:
            for overlapping_preference, _ in overlapping_node.data.values():
                if overlapping_preference > route_preference:
                    return RoutePreferenceStatus.suppressed
        return RoutePreferenceStatus.visible


def build_validator(
    database_handler: DatabaseHandler, filter_prefixes: Optional[Iterable[IP]] = None
) -> RoutePreferenceValidator:
    """
    Build a RouteValidator instance given a database handler
    and an optional set of prefixes to limit the query.
    """
    columns = ["prefix", "source", "pk", "route_preference_status"]
    object_classes = ["route", "route6"]

    if not filter_prefixes:
        q = RPSLDatabaseQuery(column_names=columns, ordered_by_sources=False).object_classes(object_classes)
        return RoutePreferenceValidator(database_handler.execute_query(q))
    else:
        rows = []
        for filter_prefix in filter_prefixes:
            q = (
                RPSLDatabaseQuery(column_names=columns, ordered_by_sources=False)
                .object_classes(object_classes)
                .ip_any(filter_prefix)
            )
            rows += list(database_handler.execute_query(q))
        return RoutePreferenceValidator(rows)


def update_route_preference_status(
    database_handler: DatabaseHandler, filter_prefixes: Optional[List[IP]] = None
) -> None:
    """
    Update the route preference status, given a database handler
    and an optional set of prefixes to limit the evaluation.
    Results are saved to the database and counters are logged.
    """
    if filter_prefixes and len(filter_prefixes) > MAX_FILTER_PREFIX_LEN:
        filter_prefixes = None

    validator = build_validator(database_handler, filter_prefixes)
    pks_to_be_visible, pks_to_be_suppressed = validator.validate_known_routes()
    pks_to_become_visible = pks_to_be_visible + validator.excluded_currently_suppressed

    objs_to_become_visible = enrich_pks(database_handler, pks_to_become_visible)
    objs_to_be_suppressed = enrich_pks(database_handler, pks_to_be_suppressed)
    database_handler.update_route_preference_status(objs_to_become_visible, objs_to_be_suppressed)

    common_log = (
        f"{len(pks_to_be_visible)} regular objects made visible, "
        f"{len(pks_to_be_suppressed)} regular objects suppressed, "
        f"{len(validator.excluded_currently_suppressed)} objects from excluded sources made visible"
    )
    if not filter_prefixes:
        logger.info(f"route preference updated for all routes: {common_log}")
    else:
        logger.info(
            f"route preference updated for a subset of {len(filter_prefixes)} added/removed/changed routes:"
            f" {common_log}"
        )


def enrich_pks(database_handler: DatabaseHandler, pks_to_enrich: List[str]):
    """
    Enrich objects based on a set of row PKs.
    This is used for early retrieval of a subset of columns to analyse,
    then enrich the data that needs its state changed, which requires
    journal entries with additional columns.
    """
    columns = [
        "pk",
        "object_text",
        "rpsl_pk",
        "source",
        "prefix",
        "origin",
        "object_class",
        "scopefilter_status",
        "rpki_status",
    ]
    query = RPSLDatabaseQuery(columns, enable_ordering=False).pks(pks_to_enrich)
    return database_handler.execute_query(query)
