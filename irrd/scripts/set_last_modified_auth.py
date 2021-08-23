#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import logging
import sys
from pathlib import Path


"""
Set last-modified attribute on all authoritative objects.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.storage.database_handler import DatabaseHandler
from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.models import RPSLDatabaseObject
from irrd.storage.queries import RPSLDatabaseQuery

def set_last_modified():
    dh = DatabaseHandler()
    auth_sources = [k for k, v in get_setting('sources').items() if v.get('authoritative')]
    q = RPSLDatabaseQuery(column_names=['pk', 'object_text', 'updated'], enable_ordering=False)
    q = q.sources(auth_sources)

    results = list(dh.execute_query(q))
    print(f'Updating {len(results)} objects in sources {auth_sources}')
    for result in results:
        rpsl_obj = rpsl_object_from_text(result['object_text'], strict_validation=False)
        if rpsl_obj.messages.errors():  # pragma: no cover
            print(f'Failed to process {rpsl_obj}: {rpsl_obj.messages.errors()}')
            continue
        new_text = rpsl_obj.render_rpsl_text(result['updated'])
        stmt = RPSLDatabaseObject.__table__.update().where(
            RPSLDatabaseObject.__table__.c.pk == result['pk']).values(
            object_text=new_text,
        )
        dh.execute_statement(stmt)
    dh.commit()
    dh.close()


def main():  # pragma: no cover
    description = """Set last-modified attribute on all authoritative objects."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting('database_readonly'):
        print('Unable to run, because database_readonly is set')
        sys.exit(-1)

    sys.exit(set_last_modified())


if __name__ == '__main__':  # pragma: no cover
    main()
