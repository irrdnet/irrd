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


def suspend_for_mntner(database_handler: DatabaseHandler, suspended_mntner: RPSLMntner) -> List[Dict[str, str]]:
    source = suspended_mntner.source()
    if not get_setting(f'sources.{source}.authoritative'):
        raise ValueError(f'Not authoritative for source {source}')

    @functools.lru_cache(maxsize=50)
    def mntner_active(rpsl_pk: str):
        q = RPSLDatabaseQuery(column_names=['pk']).sources([source]).rpsl_pk(rpsl_pk)
        return bool(list(database_handler.execute_query(q.first_only())))

    suspended_mntner_rpsl_pk = suspended_mntner.pk()
    query = RPSLDatabaseQuery(column_names=['pk', 'rpsl_pk', 'parsed_data'])
    query = query.sources([source]).lookup_attr('mnt-by', suspended_mntner_rpsl_pk)

    suspended_objects = []

    for row in list(database_handler.execute_query(query)):
        mntners: Set[str] = set(row['parsed_data']['mnt-by'])
        mntners.remove(suspended_mntner_rpsl_pk)
        mntners_active = [m for m in mntners if mntner_active(m)]
        if mntners_active:
            print(f'skipping {row["rpsl_pk"]} due to other mntners')
            continue

        print(f'go ahead on {row["rpsl_pk"]}')
        database_handler.suspend_rpsl_object(row['pk'])
        suspended_objects.append(row)
    return suspended_objects


def reactivate_for_mntner(database_handler: DatabaseHandler, reactivated_mntner: RPSLMntner) -> Tuple[List[RPSLObject], List[str]]:
    source = reactivated_mntner.source()
    scopefilter_validator = ScopeFilterValidator()
    roa_validator = SingleRouteROAValidator(database_handler)

    if not get_setting(f'sources.{source}.authoritative'):
        raise ValueError(f'Not authoritative for source {source}')

    reactivated_mntner_rpsl_pk = reactivated_mntner.pk()
    query = RPSLDatabaseSuspendedQuery()
    query = query.sources([source]).mntner(reactivated_mntner_rpsl_pk)

    restored_row_pk_uuids = set()
    restored_objects = []
    info_messages: List[str] = []

    for result in database_handler.execute_query(query):
        rpsl_obj = rpsl_object_from_text(result['object_text'], strict_validation=False)

        existing_object_query = RPSLDatabaseQuery(column_names=['pk']).sources([source])
        existing_object_query = existing_object_query.rpsl_pk(rpsl_obj.pk()).object_classes([rpsl_obj.rpsl_object_class])
        if list(database_handler.execute_query(existing_object_query)):
            info_messages.append(f"Skipping restore of object {rpsl_obj} - an object already exists with the same key")
            continue

        rpsl_obj.scopefilter_status, _ = scopefilter_validator.validate_rpsl_object(rpsl_obj)
        if get_setting('rpki.roa_source') and rpsl_obj.rpki_relevant and rpsl_obj.asn_first:
            rpsl_obj.rpki_status = roa_validator.validate_route(rpsl_obj.prefix, rpsl_obj.asn_first, source)

        print(f"status {rpsl_obj} scope {rpsl_obj.scopefilter_status} rpki {rpsl_obj.rpki_status}")

        database_handler.upsert_rpsl_object(rpsl_obj, JournalEntryOrigin.suspension)
        restored_row_pk_uuids.add(result['pk'])
        restored_objects.append(rpsl_obj)
        print(f"restoring {rpsl_obj}")

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
