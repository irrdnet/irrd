from typing import Generator, Set, Dict
import functools

from irrd.conf import config_init, get_setting
from irrd.rpsl.rpsl_objects import RPSLMntner
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery

# TODO: rename method


def objects_for_suspended_mntner(database_handler: DatabaseHandler, suspended_mntner: RPSLMntner) -> Generator[Dict[str, str], None, None]:
    source = suspended_mntner.source()
    # if not get_setting(f'sources.{source}.authoritative'):
    # raise ValueError(f'Not authoritative for source {source}')

    @functools.lru_cache(maxsize=50)
    def mntner_active(rpsl_pk: str):
        q = RPSLDatabaseQuery(column_names=['pk']).sources([source]).rpsl_pk(rpsl_pk)
        return bool(list(dh.execute_query(q.first_only())))

    suspended_mntner_rpsl_pk = suspended_mntner.pk()
    query = RPSLDatabaseQuery(column_names=['pk', 'rpsl_pk', 'parsed_data'])
    query = query.sources([source]).lookup_attr('mnt-by', suspended_mntner_rpsl_pk)

    relevant_objects = list(dh.execute_query(query))

    for row in relevant_objects:
        mntners: Set[str] = set(row['parsed_data']['mnt-by'])
        mntners.remove(suspended_mntner_rpsl_pk)
        mntners_active = [m for m in mntners if mntner_active(m)]
        if mntners_active:  # only count if they're active!
            print(f'skipping {row["rpsl_pk"]} due to other mntners')
            continue

        print(f'go ahead on {row["rpsl_pk"]}')
        yield row


if __name__ == '__main__':
    import os
    config_init(os.environ['IRRD_CONFIG_FILE'])
    dh = DatabaseHandler()
    # mntner = RPSLMntner()
    # mntner.parsed_data = {'mntner': 'SR42-MNT', 'source': 'RIPE'}
    # res = objects_for_suspended_mntner(dh, mntner)
    # for r in res:
    #     dh.suspend_rpsl_object(r['pk'])

    dh.reactivate_rpsl_objects('SR42-MNT', 'RIPE')
    dh.commit()
    dh.close()
