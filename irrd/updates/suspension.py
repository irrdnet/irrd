import functools
import logging
from typing import Dict, List, Tuple

from irrd.conf import get_setting
from irrd.rpki.validators import SingleRouteROAValidator
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import JournalEntryOrigin
from irrd.storage.queries import RPSLDatabaseQuery, RPSLDatabaseSuspendedQuery

logger = logging.getLogger(__name__)


def suspend_for_mntner(
    database_handler: DatabaseHandler, suspended_mntner: RPSLMntner
) -> List[Dict[str, str]]:
    """
    Suspend all RPSL objects for a mntner and return details of suspended objects.

    This will move RPSL objects to the suspended table, where they are never
    included in query responses. RPSL objects suspended are:
    - The mntner with primary key and source of `suspended_mntner`
    - Any object in the same source, that has `suspended_mntner` as its only
      active mnt-by, i.e. there are no other entries in mnt-by or those mntners
      do not currently exist.

    Throws a ValueError if not authoritative for this source or suspended_mntner
    does not exist. Returns database rows for all suspended objects.
    """
    log_prelude = f"suspension {suspended_mntner.pk()}"
    source = suspended_mntner.source()
    if not get_setting(f"sources.{source}.authoritative"):
        raise ValueError(f"Not authoritative for source {source}")

    logger.info(f"{log_prelude}: Starting suspension for {suspended_mntner}")

    @functools.lru_cache(maxsize=50)
    def mntner_active(rpsl_pk: str):
        q = (
            RPSLDatabaseQuery(column_names=["pk"])
            .sources([source])
            .rpsl_pk(rpsl_pk)
            .object_classes(["mntner"])
        )
        return bool(list(database_handler.execute_query(q.first_only())))

    # This runs two queries, to account for the suspension of a mntner
    # who is not an mnt-by for itself. In that case, query1 will not retrieve it,
    # but query2 will.
    query1 = RPSLDatabaseQuery(column_names=["pk", "rpsl_pk", "object_class", "source", "parsed_data"])
    query1 = query1.sources([source]).lookup_attr("mnt-by", suspended_mntner.pk())
    query1_result = list(database_handler.execute_query(query1))
    query2 = RPSLDatabaseQuery(column_names=["pk", "rpsl_pk", "object_class", "source", "parsed_data"])
    query2 = query2.sources([source]).rpsl_pk(suspended_mntner.pk()).object_classes(["mntner"])
    query2_result = list(database_handler.execute_query(query2))

    if not query2_result:
        msg = f"mntner {suspended_mntner.pk()} does not exist in {source} (or may already be suspended)"
        logger.info(f"{log_prelude}: error: {msg}")
        raise ValueError(msg)

    suspended_objects = []

    for row in query1_result + query2_result:
        if row in suspended_objects:
            continue

        mntners_active = [
            m for m in set(row["parsed_data"]["mnt-by"]) if m != suspended_mntner.pk() and mntner_active(m)
        ]
        if row["rpsl_pk"] != suspended_mntner.pk() and mntners_active:
            logger.info(
                f"{log_prelude}: Skipping suspension of {row['object_class']}/{row['rpsl_pk']} because of"
                f" remaining active mntners {mntners_active}"
            )
            continue

        logger.info(f"{log_prelude}: Suspending {row['object_class']}/{row['rpsl_pk']}")
        database_handler.suspend_rpsl_object(row["pk"])
        suspended_objects.append(row)
    return suspended_objects


def reactivate_for_mntner(
    database_handler: DatabaseHandler, reactivated_mntner: RPSLMntner
) -> Tuple[List[RPSLObject], List[str]]:
    """
    Reactivate previously suspended mntners and return the restored objects.

    Revives objects that were previously suspended with suspend_for_mntner.
    All RPSL objects that had `reactivated_mntner` as one of their mnt-by's at
    the time of suspension are restored. Note that this is potentially different
    from "all objects that were suspended at the time `reactivated_mntner` was
    suspended". Reactivated objects are removed from the suspended store.

    If an object is to be reactivated, but there is already another RPSL object
    with the same class and primary key in the same source, the reactivation
    is skipped. The object remains in the suspended store.

    Throws a ValueError if not authoritative for this source or reactivated_mntner
    does not exist in the suspended store.
    Returns a tuple of all reactivated RPSL objects and a list
    of info messages about reactivated and skipped objects.
    """
    log_prelude = f"reactivation {reactivated_mntner.pk()}"
    source = reactivated_mntner.source()
    scopefilter_validator = ScopeFilterValidator()
    roa_validator = SingleRouteROAValidator(database_handler)

    if not get_setting(f"sources.{source}.authoritative"):
        raise ValueError(f"Not authoritative for source {source}")

    logger.info(f"{log_prelude}: Starting reactivation for for {reactivated_mntner}")

    def pk_exists(pk: str, rpsl_object_class: str) -> bool:
        existing_object_query = RPSLDatabaseQuery(column_names=["pk"]).sources([source])
        existing_object_query = existing_object_query.rpsl_pk(pk).object_classes([rpsl_object_class])
        return bool(list(database_handler.execute_query(existing_object_query)))

    if pk_exists(reactivated_mntner.pk(), "mntner"):
        msg = (
            f"source {source} has a currently active mntner {reactivated_mntner.pk()} - can not restore the"
            " suspended one"
        )
        logger.info(f"{log_prelude}: error: {msg}")
        raise ValueError(msg)

    # This is both a check to make sure the mntner is actually suspended,
    # but also to catch cases where a suspended mntner did not have itself as mnt-by.
    query = (
        RPSLDatabaseSuspendedQuery()
        .sources([source])
        .rpsl_pk(reactivated_mntner.pk())
        .object_classes(["mntner"])
    )
    results = list(database_handler.execute_query(query))

    if not results:
        msg = f"mntner {reactivated_mntner.pk()} not found in suspended store for source {source}"
        logger.info(f"{log_prelude}: error: {msg}")
        raise ValueError(msg)

    query = RPSLDatabaseSuspendedQuery().sources([source]).mntner(reactivated_mntner.pk())
    results += list(database_handler.execute_query(query))

    restored_row_pk_uuids = set()
    restored_objects = []
    info_messages: List[str] = []

    for result in results:
        if result["pk"] in restored_row_pk_uuids:
            continue

        reactivating_obj = rpsl_object_from_text(result["object_text"], strict_validation=False)

        if pk_exists(reactivating_obj.pk(), reactivating_obj.rpsl_object_class):
            msg = (
                f"Skipping restore of object {reactivating_obj} - an object already exists with the same key"
            )
            logger.info(f"{log_prelude}: {msg}")
            info_messages.append(msg)
            continue

        reactivating_obj.scopefilter_status, _ = scopefilter_validator.validate_rpsl_object(reactivating_obj)
        if get_setting("rpki.roa_source") and reactivating_obj.is_route and reactivating_obj.asn_first:
            reactivating_obj.rpki_status = roa_validator.validate_route(
                reactivating_obj.prefix, reactivating_obj.asn_first, source
            )

        database_handler.upsert_rpsl_object(
            reactivating_obj, JournalEntryOrigin.suspension, forced_created_value=result["original_created"]
        )
        restored_row_pk_uuids.add(result["pk"])
        restored_objects.append(reactivating_obj)
        logger.info(f"{log_prelude}: Restoring object {reactivating_obj}")

    database_handler.delete_suspended_rpsl_objects(restored_row_pk_uuids)
    return restored_objects, info_messages
