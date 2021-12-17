import logging
from typing import List, Set, Dict, Tuple
import functools

from irrd.storage.models import JournalEntryOrigin
from irrd.conf import config_init, get_setting
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, RPSLDatabaseSuspendedQuery
from irrd.rpsl.parser import RPSLObject
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.rpki.validators import SingleRouteROAValidator

logger = logging.getLogger(__name__)


def suspend_for_mntner(database_handler: DatabaseHandler, suspended_mntner: RPSLMntner) -> List[Dict[str, str]]:
    source = suspended_mntner.source()
    if not get_setting(f'sources.{source}.authoritative'):
        raise ValueError(f'Not authoritative for source {source}')

    logger.info(f"{suspended_mntner.pk()}: Starting suspension for {suspended_mntner}")

    @functools.lru_cache(maxsize=50)
    def mntner_active(rpsl_pk: str):
        q = RPSLDatabaseQuery(column_names=['pk']).sources([source]).rpsl_pk(rpsl_pk).object_classes(['mntner'])
        return bool(list(database_handler.execute_query(q.first_only())))

    suspended_mntner_rpsl_pk = suspended_mntner.pk()
    # This runs two queries, to account for the suspension of a mntner
    # who is not an mnt-by for itself. In that case, query1 will not retrieve it,
    # but query2 will.
    query1 = RPSLDatabaseQuery(column_names=['pk', 'rpsl_pk', 'object_class', 'source', 'parsed_data'])
    query1 = query1.sources([source]).lookup_attr('mnt-by', suspended_mntner_rpsl_pk)
    query1_result = list(database_handler.execute_query(query1))
    query2 = RPSLDatabaseQuery(column_names=['pk', 'rpsl_pk', 'object_class', 'source', 'parsed_data'])
    query2 = query2.sources([source]).rpsl_pk(suspended_mntner_rpsl_pk).object_classes(['mntner'])
    query2_result = list(database_handler.execute_query(query2))

    if not query2_result:
        msg = f"mntner {suspended_mntner.pk()} does not exist in {source} (or may already be suspended)"
        logger.info(f"{suspended_mntner.pk()}: error: {msg}")
        raise ValueError(msg)

    suspended_objects = []

    for row in query1_result + query2_result:
        if row in suspended_objects:
            continue

        mntners: Set[str] = set(row['parsed_data']['mnt-by'])
        mntners.remove(suspended_mntner_rpsl_pk)
        mntners_active = [m for m in mntners if mntner_active(m)]
        if mntners_active:
            logger.info(f"{suspended_mntner.pk()}: Skipping suspension of {row['object_class']}/{row['rpsl_pk']} because of remaining active mntners {mntners}")
            continue

        logger.info(f"{suspended_mntner.pk()}: Suspending {row['object_class']}/{row['rpsl_pk']}")
        database_handler.suspend_rpsl_object(row['pk'])
        suspended_objects.append(row)
    return suspended_objects


def reactivate_for_mntner(database_handler: DatabaseHandler, reactivated_mntner: RPSLMntner) -> Tuple[List[RPSLObject], List[str]]:
    source = reactivated_mntner.source()
    scopefilter_validator = ScopeFilterValidator()
    roa_validator = SingleRouteROAValidator(database_handler)

    if not get_setting(f'sources.{source}.authoritative'):
        raise ValueError(f'Not authoritative for source {source}')

    logger.info(f"{reactivated_mntner.pk()}: Starting reactivation for for {reactivated_mntner}")

    reactivated_mntner_rpsl_pk = reactivated_mntner.pk()
    query = RPSLDatabaseSuspendedQuery()
    query = query.sources([source]).mntner(reactivated_mntner_rpsl_pk)
    results = list(database_handler.execute_query(query))

    restored_row_pk_uuids = set()
    restored_objects = []
    info_messages: List[str] = []

    if not results:
        msg = f"mntner {reactivated_mntner.pk()} is not a mntner for any suspended objects in {source}"
        logger.info(f"{reactivated_mntner.pk()}: error: {msg}")
        raise ValueError(msg)

    for result in results:
        rpsl_obj = rpsl_object_from_text(result['object_text'], strict_validation=False)

        existing_object_query = RPSLDatabaseQuery(column_names=['pk']).sources([source])
        existing_object_query = existing_object_query.rpsl_pk(rpsl_obj.pk()).object_classes([rpsl_obj.rpsl_object_class])
        if list(database_handler.execute_query(existing_object_query)):
            msg = f"Skipping restore of object {rpsl_obj} - an object already exists with the same key"
            logger.info(f"{reactivated_mntner.pk()}: {msg}")
            info_messages.append(msg)
            continue

        rpsl_obj.scopefilter_status, _ = scopefilter_validator.validate_rpsl_object(rpsl_obj)
        if get_setting('rpki.roa_source') and rpsl_obj.rpki_relevant and rpsl_obj.asn_first:
            rpsl_obj.rpki_status = roa_validator.validate_route(rpsl_obj.prefix, rpsl_obj.asn_first, source)

        database_handler.upsert_rpsl_object(rpsl_obj, JournalEntryOrigin.suspension)
        restored_row_pk_uuids.add(result['pk'])
        restored_objects.append(rpsl_obj)
        logger.info(f"{reactivated_mntner.pk()}: Restoring object {rpsl_obj}")

    database_handler.delete_suspended_rpsl_objects(restored_row_pk_uuids)
    return restored_objects, info_messages


if __name__ == '__main__':
    import os
    config_init(os.environ['IRRD_CONFIG_FILE'])
    dh = DatabaseHandler()
    mntner = RPSLMntner()
    mntner.parsed_data = {'mntner': 'SR42-MNT', 'source': 'RIPE'}
    suspend_for_mntner(dh, mntner)
    reactivate_for_mntner(dh, mntner)

    # dh.reactivate_rpsl_objects('SR42-MNT', 'RIPE')
    dh.commit()
    dh.close()
