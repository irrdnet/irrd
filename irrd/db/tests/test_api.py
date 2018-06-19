import uuid
from unittest.mock import Mock

import pytest
from IPy import IP
from pytest import raises

from .. import engine
from ..api import DatabaseHandler, RPSLDatabaseQuery
from ..models import RPSLDatabaseObject

"""
These tests for the database use a live PostgreSQL database,
as it's rather complicated to mock, and mocking would not make it
a very useful test. Using in-memory SQLite is not an option due to
using specific PostgreSQL features.

To improve performance, these tests do not run full migrations.
"""


@pytest.fixture()
def irrd_database():
    engine.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    table_name = RPSLDatabaseObject.__tablename__
    if engine.dialect.has_table(engine, table_name):  # pragma: no cover
        raise Exception(f"The database on URL {engine.url} already has a table named {table_name} - refusing "
                        f"to overwrite existing database.")
    RPSLDatabaseObject.metadata.create_all(engine)

    yield None

    engine.dispose()
    RPSLDatabaseObject.metadata.drop_all(engine)


class TestDatabaseHandlerLive:
    def test_object_writing(self, monkeypatch, irrd_database):
        monkeypatch.setattr('irrd.db.api.MAX_RECORDS_CACHE_BEFORE_INSERT', 1)
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

        dh = DatabaseHandler()
        dh.upsert_rpsl_object(rpsl_object_route_v4)
        assert len(dh._rpsl_upsert_cache) == 1

        rpsl_object_route_v4.parsed_data = {'mnt-by': 'MNT-CORRECT', 'source': 'TEST'}
        dh.upsert_rpsl_object(rpsl_object_route_v4)  # should trigger an immediate flush due to duplicate RPSL pk
        assert len(dh._rpsl_upsert_cache) == 1

        rpsl_obj_route_v6 = Mock(
            pk=lambda: '2001:db8::/64,AS23456',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-CORRECT', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 6,
            ip_first=IP('2001:db8::'),
            ip_last=IP('2001:db8::ffff:ffff:ffff:ffff'),
            asn_first=23456,
            asn_last=23456,
        )
        dh.upsert_rpsl_object(rpsl_obj_route_v6)
        assert len(dh._rpsl_upsert_cache) == 0  # should have been flushed to the DB
        dh.upsert_rpsl_object(rpsl_obj_route_v6)

        dh.commit()

        # There should be two entries with MNT-CORRECT in the db now.
        query = RPSLDatabaseQuery()
        result = [i for i in dh.execute_query(query)]  # Loop to exhaust the generator
        assert len(result) == 2

        query.lookup_attr('mnt-by', 'MNT-CORRECT')
        result = [i for i in dh.execute_query(query)]
        assert len(result) == 2

        rpsl_obj_ignored = Mock(
            pk=lambda: '2001:db8::/64,AS2914',
            rpsl_object_class='route',
            parsed_data={'mnt-by': 'MNT-CORRECT', 'source': 'TEST'},
            render_rpsl_text=lambda: 'object-text',
            ip_version=lambda: 6,
            ip_first=IP('2001:db8::'),
            ip_last=IP('2001:db8::ffff:ffff:ffff:ffff'),
            asn_first=23456,
            asn_last=23456,
        )
        dh.upsert_rpsl_object(rpsl_obj_ignored)
        assert len(dh._rpsl_upsert_cache) == 1
        dh.upsert_rpsl_object(rpsl_obj_ignored)
        assert len(dh._rpsl_upsert_cache) == 1
        dh.rollback()

        query = RPSLDatabaseQuery()
        result = [i for i in dh.execute_query(query)]  # Loop to exhaust the generator
        assert len(result) == 2

        dh._connection.close()


class TestRPSLDatabaseQueryLive:

    def test_queries(self, irrd_database):
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
        self.dh = DatabaseHandler()
        self.dh.upsert_rpsl_object(rpsl_object_route_v4)

        # Each of these filters should match
        self._assert_match(RPSLDatabaseQuery().rpsl_pk('192.0.2.0/24,AS23456'))
        self._assert_match(RPSLDatabaseQuery().sources(['TEST', 'X']))
        self._assert_match(RPSLDatabaseQuery().object_classes(['route']))
        self._assert_match(RPSLDatabaseQuery().lookup_attr('mnt-by', 'MNT-TEST'))
        self._assert_match(RPSLDatabaseQuery().ip_exact(IP('192.0.2.0/24')))
        self._assert_match(RPSLDatabaseQuery().asn(23456))
        self._assert_match(RPSLDatabaseQuery().ip_more_specific(IP('192.0.0.0/21')))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/24')))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP('192.0.2.0/25')))

        q = RPSLDatabaseQuery().rpsl_pk('192.0.2.0/24,AS23456').sources(['TEST', 'X']).object_classes(['route'])
        q = q.lookup_attr('mnt-by', 'MNT-TEST').ip_exact(IP('192.0.2.0/24')).asn(23456)
        q = q.ip_less_specific(IP('192.0.2.0/25')).ip_less_specific(IP('192.0.2.0/24'))
        q = q.ip_more_specific(IP('192.0.0.0/21'))

        result = [i for i in self.dh.execute_query(q)]
        assert len(result) == 1, f"Failed query: {q}"
        pk = result[0]['pk']

        assert generator_len(self.dh.execute_query(RPSLDatabaseQuery().pk(pk))) == 1

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

        with raises(ValueError) as ve:
            RPSLDatabaseQuery().lookup_attr('not-a-lookup-attr', 'value')
        assert 'Invalid lookup attribute' in str(ve)

        self.dh._connection.close()

    def _assert_match(self, query):
        __tracebackhide__ = True
        assert generator_len(self.dh.execute_query(query)) == 1, f"Failed query: {query}"

    def _assert_no_match(self, query):
        __tracebackhide__ = True
        assert not generator_len(self.dh.execute_query(query)), f"Failed query: {query}"


def generator_len(generator):
    return len([i for i in generator])
