import uuid
from unittest.mock import Mock

import pytest
from IPy import IP
from pytest import raises

from .. import engine
from ..api import DatabaseHandler, RPSLDatabaseQuery, RPSLDatabaseJournalQuery, RPSLDatabaseStatusQuery
from ..models import RPSLDatabaseObject, DatabaseOperation

"""
These tests for the database use a live PostgreSQL database,
as it's rather complicated to mock, and mocking would not make it
a very useful test. Using in-memory SQLite is not an option due to
using specific PostgreSQL features.

To improve performance, these tests do not run full migrations.
"""


@pytest.fixture()
def irrd_database(monkeypatch):
    RPSLDatabaseObject.metadata.drop_all(engine)

    engine.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    table_name = RPSLDatabaseObject.__tablename__
    if engine.dialect.has_table(engine, table_name):  # pragma: no cover
        raise Exception(f"The database on URL {engine.url} already has a table named {table_name} - refusing "
                        f"to overwrite existing database.")
    RPSLDatabaseObject.metadata.create_all(engine)

    yield None

    engine.dispose()
    # RPSLDatabaseObject.metadata.drop_all(engine)


# noinspection PyTypeChecker
@pytest.fixture()
def database_handler_with_route():
    rpsl_object_route_v4 = Mock(
        pk=lambda: '192.0.2.0/24,AS23456',
        rpsl_object_class='route',
        parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'TEST'},
        render_rpsl_text=lambda: 'object-text',
        ip_version=lambda: 4,
        ip_first=IP('192.0.2.0'),
        ip_last=IP('192.0.2.255'),
        asn_first=23456,
        asn_last=23456,
    )
    dh = DatabaseHandler()
    dh.upsert_rpsl_object(rpsl_object_route_v4)
    yield dh
    dh._connection.close()


# noinspection PyTypeChecker
class TestDatabaseHandlerLive:
    """
    This test covers mainly DatabaseHandler and DatabaseStatusTracker.
    """
    def test_object_writing(self, monkeypatch, irrd_database):
        monkeypatch.setenv('IRRD_DATABASES_TEST_AUTHORITATIVE', '1')
        monkeypatch.setenv('IRRD_DATABASES_TEST2_KEEP_JOURNAL', '1')
        monkeypatch.setattr('irrd.storage.api.MAX_RECORDS_CACHE_BEFORE_INSERT', 1)

        rpsl_object_route_v4 = Mock(
            pk=lambda: '192.0.2.0/24,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-WRONG', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.0'),
            ip_last=IP('192.0.2.255'),
            asn_first=23456,
            asn_last=23456,
        )

        self.dh = DatabaseHandler()
        self.dh.upsert_rpsl_object(rpsl_object_route_v4, 42)
        assert len(self.dh._rpsl_upsert_cache) == 1

        rpsl_object_route_v4.parsed_data = {'mnt-by': 'MNT-CORRECT', 'source': 'TEST'}
        self.dh.upsert_rpsl_object(rpsl_object_route_v4)  # should trigger an immediate flush due to duplicate RPSL pk
        assert len(self.dh._rpsl_upsert_cache) == 1

        rpsl_object_route_v6 = Mock(
            pk=lambda: '2001:db8::/64,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-CORRECT', 'source': 'TEST2'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 6,
            ip_first=IP('2001:db8::'),
            ip_last=IP('2001:db8::ffff:ffff:ffff:ffff'),
            asn_first=23456,
            asn_last=23456,
        )
        self.dh.upsert_rpsl_object(rpsl_object_route_v6)
        assert len(self.dh._rpsl_upsert_cache) == 0  # should have been flushed to the DB
        self.dh.upsert_rpsl_object(rpsl_object_route_v6)

        self.dh.commit()

        # There should be two entries with MNT-CORRECT in the db now.
        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 2

        query = RPSLDatabaseQuery().lookup_attr('mnt-by', 'MNT-CORRECT')
        result = list(self.dh.execute_query(query))
        assert len(result) == 2

        # This object should be ignored due to a rollback.
        rpsl_obj_ignored = Mock(
            pk=lambda: 'AS2914',
            rpsl_object_class='aut-num',
            parsed_data={'mnt-by': 'MNT-CORRECT', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            asn_first=23456,
            asn_last=23456,
        )
        self.dh.upsert_rpsl_object(rpsl_obj_ignored)
        assert len(self.dh._rpsl_upsert_cache) == 1
        self.dh.upsert_rpsl_object(rpsl_obj_ignored)
        assert len(self.dh._rpsl_upsert_cache) == 1
        self.dh.rollback()

        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 2

        self.dh.delete_rpsl_object(rpsl_object_route_v6)
        self.dh.delete_rpsl_object(rpsl_object_route_v6)
        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 1
        self.dh.commit()

        journal = self._clean_result(self.dh.execute_query(RPSLDatabaseJournalQuery()))

        # The IPv6 object was created in a different source, so it should
        # have a separate sequence of NRTM serials. Serial for TEST was forced
        # to 42 at the first upsert query.
        assert journal == [
            {'rpsl_pk': '192.0.2.0/24,AS23456', 'source': 'TEST', 'serial_nrtm': 42,
             'operation': DatabaseOperation.add_or_update, 'object_class': 'route', 'object_text': 'object-text'},
            {'rpsl_pk': '192.0.2.0/24,AS23456', 'source': 'TEST', 'serial_nrtm': 43,
             'operation': DatabaseOperation.add_or_update, 'object_class': 'route', 'object_text': 'object-text'},
            {'rpsl_pk': '2001:db8::/64,AS23456', 'source': 'TEST2', 'serial_nrtm': 1,
             'operation': DatabaseOperation.add_or_update, 'object_class': 'route', 'object_text': 'object-text'},
            {'rpsl_pk': '2001:db8::/64,AS23456', 'source': 'TEST2', 'serial_nrtm': 2,
             'operation': DatabaseOperation.add_or_update, 'object_class': 'route', 'object_text': 'object-text'},
            {'rpsl_pk': '2001:db8::/64,AS23456', 'source': 'TEST2', 'serial_nrtm': 3,
             'operation': DatabaseOperation.delete, 'object_class': 'route', 'object_text': 'object-text'},
        ]

        status_test = self._clean_result(self.dh.execute_query(RPSLDatabaseStatusQuery().sources(['TEST'])))
        assert status_test == [
            {'source': 'TEST', 'serial_oldest_journal': 42, 'serial_newest_journal': 43,
             'serial_oldest_seen': 42, 'serial_newest_seen': 43,
             'serial_last_dump': None, 'last_error': None},
        ]
        status_test2 = self._clean_result(self.dh.execute_query(RPSLDatabaseStatusQuery().sources(['TEST2'])))
        assert status_test2 == [
            {'source': 'TEST2', 'serial_oldest_journal': 1, 'serial_newest_journal': 3,
             'serial_oldest_seen': 1, 'serial_newest_seen': 3,
             'serial_last_dump': None, 'last_error': None},
        ]

        self.dh.rollback()
        self.dh._connection.close()

    def test_updates_database_status_forced_serials(self, monkeypatch, irrd_database):
        # As settings are default, journal keeping is disabled for this DB
        rpsl_object_route_v4 = Mock(
            pk=lambda: '192.0.2.0/24,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-WRONG', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.0'),
            ip_last=IP('192.0.2.255'),
            asn_first=23456,
            asn_last=23456,
        )

        self.dh = DatabaseHandler()
        # This upsert has a forced serial, so it should be recorded in the DB status.
        self.dh.upsert_rpsl_object(rpsl_object_route_v4, 42)
        self.dh.upsert_rpsl_object(rpsl_object_route_v4, 4242)

        rpsl_object_route_v6 = Mock(
            pk=lambda: '2001:db8::/64,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-CORRECT', 'source': 'TEST2'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 6,
            ip_first=IP('2001:db8::'),
            ip_last=IP('2001:db8::ffff:ffff:ffff:ffff'),
            asn_first=23456,
            asn_last=23456,
        )
        # This upsert has no serial, and journal keeping is not enabled,
        # so there should be no record of the DB status.
        self.dh.upsert_rpsl_object(rpsl_object_route_v6)
        self.dh.commit()

        status = self._clean_result(self.dh.execute_query(RPSLDatabaseStatusQuery()))
        print(status)
        assert status == [
            {'source': 'TEST', 'serial_oldest_journal': None, 'serial_newest_journal': None,
             'serial_oldest_seen': 42, 'serial_newest_seen': 4242,
             'serial_last_dump': None, 'last_error': None},
        ]

        self.dh.rollback()
        self.dh._connection.close()

    def _clean_result(self, results):
        variable_fields = ['pk', 'timestamp', 'created', 'updated']
        return [{k: v for k, v in result.items() if k not in variable_fields} for result in list(results)]


# noinspection PyTypeChecker
class TestRPSLDatabaseQueryLive:

    def test_matching_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route

        # Each of these filters should match
        self._assert_match(RPSLDatabaseQuery().rpsl_pk('192.0.2.0/24,AS23456'))
        self._assert_match(RPSLDatabaseQuery().sources(['TEST', 'X']))
        self._assert_match(RPSLDatabaseQuery().object_classes(['route']))
        self._assert_match(RPSLDatabaseQuery().lookup_attr('mnt-by', 'MNT-test'))  # intentional case mismatch
        self._assert_match(RPSLDatabaseQuery().ip_exact(IP('192.0.2.0/24')))
        self._assert_match(RPSLDatabaseQuery().asn(23456))
        self._assert_match(RPSLDatabaseQuery().ip_more_specific(IP('192.0.0.0/21')))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/24')))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/25')))
        self._assert_match(RPSLDatabaseQuery().text_search('192.0.2.0/24'))
        self._assert_match(RPSLDatabaseQuery().text_search('192.0.2.0/25'))
        self._assert_match(RPSLDatabaseQuery().text_search('192.0.2.1'))
        self._assert_match(RPSLDatabaseQuery().text_search('192.0.2.0/24,As23456'))

    def test_chained_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route

        q = RPSLDatabaseQuery().rpsl_pk('192.0.2.0/24,AS23456').sources(['TEST', 'X']).object_classes(['route'])
        q = q.lookup_attr('mnt-by', 'MNT-TEST').ip_exact(IP('192.0.2.0/24')).asn(23456)
        q = q.ip_less_specific(IP('192.0.2.0/25')).ip_less_specific(IP('192.0.2.0/24'))
        q = q.ip_more_specific(IP('192.0.0.0/21'))

        result = [i for i in self.dh.execute_query(q)]
        assert len(result) == 1, f"Failed query: {q}"
        pk = result[0]['pk']

        self._assert_match(RPSLDatabaseQuery().pk(pk))

    def test_non_matching_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        # None of these should match
        self._assert_no_match(RPSLDatabaseQuery().pk(str(uuid.uuid4())))
        self._assert_no_match(RPSLDatabaseQuery().rpsl_pk('foo'))
        self._assert_no_match(RPSLDatabaseQuery().sources(['TEST3']))
        self._assert_no_match(RPSLDatabaseQuery().object_classes(['route6']))
        self._assert_no_match(RPSLDatabaseQuery().lookup_attr('mnt-by', 'MNT-NOTEXIST'))
        self._assert_no_match(RPSLDatabaseQuery().ip_exact(IP('192.0.2.0/25')))
        self._assert_no_match(RPSLDatabaseQuery().asn(23455))
        self._assert_no_match(RPSLDatabaseQuery().ip_more_specific(IP('192.0.2.0/24')))
        self._assert_no_match(RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/23')))
        self._assert_no_match(RPSLDatabaseQuery().text_search('192.0.2.0/23'))
        self._assert_no_match(RPSLDatabaseQuery().text_search('AS2914'))
        self._assert_no_match(RPSLDatabaseQuery().text_search('23456'))

    def test_ordering_sources(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        rpsl_object_2 = Mock(
            pk=lambda: '192.0.2.1/32,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'AAA-TST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.1'),
            ip_last=IP('192.0.2.1'),
            asn_first=23456,
            asn_last=23456,
        )
        rpsl_object_3 = Mock(
            pk=lambda: '192.0.2.2/32,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'OTHER-SOURCE'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.2'),
            ip_last=IP('192.0.2.2'),
            asn_first=23456,
            asn_last=23456,
        )
        self.dh.upsert_rpsl_object(rpsl_object_2)
        self.dh.upsert_rpsl_object(rpsl_object_3)

        query = RPSLDatabaseQuery()
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['TEST', 'AAA-TST', 'OTHER-SOURCE']  # ordered by IP

        query = RPSLDatabaseQuery().sources(['OTHER-SOURCE', 'AAA-TST', 'TEST'])
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['OTHER-SOURCE', 'AAA-TST', 'TEST']

        query = RPSLDatabaseQuery().sources(['TEST', 'AAA-TST', 'TEST'])
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['TEST', 'AAA-TST']

        query = RPSLDatabaseQuery().sources(['AAA-TST', 'TEST']).first_only()
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['AAA-TST']

        query = RPSLDatabaseQuery().sources(['OTHER-SOURCE', 'TEST']).first_only()
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['OTHER-SOURCE']

        query = RPSLDatabaseQuery().prioritise_source('OTHER-SOURCE')
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['OTHER-SOURCE', 'TEST', 'AAA-TST']

        query = RPSLDatabaseQuery().prioritise_source('OTHER-SOURCE').sources(['AAA-TST', 'OTHER-SOURCE', 'TEST'])
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['OTHER-SOURCE', 'AAA-TST', 'TEST']

        query = RPSLDatabaseQuery().prioritise_source('OTHER-SOURCE').sources(['AAA-TST', 'TEST'])
        response_sources = [r['source'] for r in self.dh.execute_query(query)]
        assert response_sources == ['AAA-TST', 'TEST']

    def test_text_search_person_role(self, irrd_database):
        rpsl_object_person = Mock(
            pk=lambda: 'PERSON',
            rpsl_object_class='person',
            parsed_data={'person': 'my person-name', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            asn_first=None,
            asn_last=None,
        )
        rpsl_object_role = Mock(
            pk=lambda: 'ROLE',
            rpsl_object_class='person',
            parsed_data={'person': 'my role-name', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            asn_first=None,
            asn_last=None,
        )
        self.dh = DatabaseHandler()
        self.dh.upsert_rpsl_object(rpsl_object_person)
        self.dh.upsert_rpsl_object(rpsl_object_role)

        self._assert_match(RPSLDatabaseQuery().text_search('person-name'))
        self._assert_match(RPSLDatabaseQuery().text_search('role-name'))

        self.dh._connection.close()

    def test_more_less_specific_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        rpsl_route_more_specific_25_1 = Mock(
            pk=lambda: '192.0.2.0/25,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.0'),
            ip_last=IP('192.0.2.127'),
            asn_first=23456,
            asn_last=23456,
        )
        rpsl_route_more_specific_25_2 = Mock(
            pk=lambda: '192.0.2.128/25,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.128'),
            ip_last=IP('192.0.2.255'),
            asn_first=23456,
            asn_last=23456,
        )
        rpsl_route_more_specific_26 = Mock(
            pk=lambda: '192.0.2.0/26,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': ['MNT-TEST', 'MNT-TEST2'], 'source': 'TEST2'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 4,
            ip_first=IP('192.0.2.0'),
            ip_last=IP('192.0.2.63'),
            asn_first=23456,
            asn_last=23456,
        )
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_25_1)
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_25_2)
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_26)
        self.dh.commit()

        q = RPSLDatabaseQuery().ip_more_specific(IP('192.0.2.0/24'))
        rpsl_pks = [r['rpsl_pk'] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 3, f"Failed query: {q}"
        assert '192.0.2.0/25,AS23456' in rpsl_pks
        assert '192.0.2.128/25,AS23456' in rpsl_pks
        assert '192.0.2.0/26,AS23456' in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/25'))
        rpsl_pks = [r['rpsl_pk'] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 2, f"Failed query: {q}"
        assert '192.0.2.0/25,AS23456' in rpsl_pks
        assert '192.0.2.0/24,AS23456' in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific_one_level(IP('192.0.2.0/26'))
        rpsl_pks = [r['rpsl_pk'] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 1, f"Failed query: {q}"
        assert '192.0.2.0/25,AS23456' in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/25')).first_only()
        rpsl_pks = [r['rpsl_pk'] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 1, f"Failed query: {q}"
        assert '192.0.2.0/25,AS23456' in rpsl_pks

        q = RPSLDatabaseQuery().sources(['TEST']).ip_less_specific_one_level(IP('192.0.2.0/27'))
        self._assert_match(q)

    def test_modify_frozen_filter(self):
        with raises(ValueError) as ve:
            RPSLDatabaseQuery().ip_less_specific_one_level(IP('192.0.2.0/27')).sources(['TEST'])
        assert 'frozen' in str(ve)

    def test_invalid_lookup_attribute(self):
        with raises(ValueError) as ve:
            RPSLDatabaseQuery().lookup_attr('not-a-lookup-attr', 'value')
        assert 'Invalid lookup attribute' in str(ve)

    def _assert_match(self, query):
        __tracebackhide__ = True
        assert len(list(self.dh.execute_query(query))) == 1, f"Failed query: {query}"

    def _assert_no_match(self, query):
        __tracebackhide__ = True
        result = list(self.dh.execute_query(query))
        assert not len(result), f"Failed query: {query}: unexpected output: {result}"
