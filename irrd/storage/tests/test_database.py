import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest
from IPy import IP
from pytest import raises
from sqlalchemy.exc import ProgrammingError

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.test_utils import flatten_mock_calls

from .. import get_engine
from ..database_handler import DatabaseHandler
from ..models import DatabaseOperation, JournalEntryOrigin, RPSLDatabaseObject
from ..preload import Preloader
from ..queries import (
    DatabaseStatusQuery,
    ROADatabaseObjectQuery,
    RPSLDatabaseJournalQuery,
    RPSLDatabaseObjectStatisticsQuery,
    RPSLDatabaseQuery,
    RPSLDatabaseSuspendedQuery,
)

"""
These tests for the database use a live PostgreSQL database,
as it's rather complicated to mock, and mocking would not make it
a very useful test. Using in-memory SQLite is not an option due to
using specific PostgreSQL features.

To improve performance, these tests do not run full migrations.

The tests also cover both database_handler.py and queries.py, as they
closely interact with the database.
"""


@pytest.fixture()
def irrd_database(monkeypatch):
    engine = get_engine()
    # RPSLDatabaseObject.metadata.drop_all(engine)
    try:
        engine.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    except ProgrammingError as pe:  # pragma: no cover
        print(f"WARNING: unable to create extension pgcrypto on the database. Queries may fail: {pe}")

    table_name = RPSLDatabaseObject.__tablename__
    if engine.dialect.has_table(engine, table_name):  # pragma: no cover
        raise Exception(
            f"The database on URL {engine.url} already has a table named {table_name} - refusing "
            "to overwrite existing database."
        )
    RPSLDatabaseObject.metadata.create_all(engine)

    monkeypatch.setattr(
        "irrd.storage.database_handler.Preloader", lambda enable_queries: Mock(spec=Preloader)
    )

    yield None

    engine.dispose()
    RPSLDatabaseObject.metadata.drop_all(engine)


# noinspection PyTypeChecker
@pytest.fixture()
def database_handler_with_route():
    rpsl_object_route_v4 = Mock(
        pk=lambda: "192.0.2.0/24,AS65537",
        rpsl_object_class="route",
        parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "TEST"},
        render_rpsl_text=lambda last_modified: "object-text",
        ip_version=lambda: 4,
        ip_first=IP("192.0.2.0"),
        ip_last=IP("192.0.2.255"),
        prefix_length=24,
        prefix=IP("192.0.2.0/24"),
        asn_first=65537,
        asn_last=65537,
        rpki_status=RPKIStatus.invalid,
        scopefilter_status=ScopeFilterStatus.in_scope,
        route_preference_status=RoutePreferenceStatus.visible,
    )

    dh = DatabaseHandler()

    dh.upsert_rpsl_object(rpsl_object_route_v4, JournalEntryOrigin.auth_change)
    yield dh
    dh.close()


# noinspection PyTypeChecker
class TestDatabaseHandlerLive:
    """
    This test covers mainly DatabaseHandler and DatabaseStatusTracker.
    """

    def test_readonly(self, monkeypatch, irrd_database, config_override):
        monkeypatch.setattr("irrd.storage.database_handler.MAX_RECORDS_BUFFER_BEFORE_INSERT", 1)

        rpsl_object_route_v4 = Mock(
            pk=lambda: "192.0.2.0/24,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": "MNT-WRONG", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.255"),
            prefix=IP("192.0.2.0/24"),
            prefix_length=24,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )

        self.dh = DatabaseHandler(readonly=True)
        with pytest.raises(Exception) as ex:
            self.dh.upsert_rpsl_object(rpsl_object_route_v4, JournalEntryOrigin.auth_change)
        assert "readonly" in str(ex)

        config_override(
            {
                "database_readonly": True,
            }
        )

        self.dh = DatabaseHandler()
        with pytest.raises(Exception) as ex:
            self.dh.upsert_rpsl_object(rpsl_object_route_v4, JournalEntryOrigin.auth_change)
        assert "readonly" in str(ex)

    def test_duplicate_key_different_class(self, monkeypatch, irrd_database, config_override):
        monkeypatch.setattr("irrd.storage.database_handler.MAX_RECORDS_BUFFER_BEFORE_INSERT", 1)
        # tests for #560

        rpsl_object_mntner = Mock(
            pk=lambda: "AS-TEST",
            rpsl_object_class="mntner",
            parsed_data={"mnt-by": "MNT-TEST", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            prefix=None,
            prefix_length=None,
            asn_first=None,
            asn_last=None,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )

        self.dh = DatabaseHandler()
        self.dh.upsert_rpsl_object(rpsl_object_mntner, JournalEntryOrigin.auth_change)

        rpsl_object_as_set = Mock(
            pk=lambda: "AS-TEST",
            rpsl_object_class="as-set",
            parsed_data={"mnt-by": "MNT-TEST", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            prefix=None,
            prefix_length=None,
            asn_first=None,
            asn_last=None,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh.upsert_rpsl_object(rpsl_object_as_set, JournalEntryOrigin.auth_change)

        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 2

        self.dh.close()

    def test_object_writing_and_status_checking(self, monkeypatch, irrd_database, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {"keep_journal": True},
                    "TEST2": {"keep_journal": True, "nrtm_host": "a", "rpki_excluded": True},
                }
            }
        )
        monkeypatch.setattr("irrd.storage.database_handler.MAX_RECORDS_BUFFER_BEFORE_INSERT", 1)

        rpsl_object_route_v4 = Mock(
            pk=lambda: "192.0.2.0/24,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": "MNT-WRONG", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.255"),
            prefix=IP("192.0.2.0/24"),
            prefix_length=24,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )

        self.dh = DatabaseHandler()
        self.dh.changed_objects_tracker.preloader.signal_reload = Mock(return_value=None)
        self.dh.upsert_rpsl_object(
            rpsl_object_route_v4, JournalEntryOrigin.auth_change, forced_created_value="2021-01-01"
        )
        assert len(self.dh._rpsl_upsert_buffer) == 1

        rpsl_object_route_v4.parsed_data = {"mnt-by": "MNT-CORRECT", "source": "TEST"}
        self.dh.upsert_rpsl_object(
            rpsl_object_route_v4, JournalEntryOrigin.auth_change
        )  # should trigger an immediate flush due to duplicate RPSL pk
        assert len(self.dh._rpsl_upsert_buffer) == 1

        rpsl_object_route_v6 = Mock(
            pk=lambda: "2001:db8::/64,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": "MNT-CORRECT", "source": "TEST2"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 6,
            ip_first=IP("2001:db8::"),
            ip_last=IP("2001:db8::ffff:ffff:ffff:ffff"),
            prefix=IP("2001:db8::/32"),
            prefix_length=32,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh.upsert_rpsl_object(rpsl_object_route_v6, JournalEntryOrigin.auth_change, source_serial=42)
        assert len(self.dh._rpsl_upsert_buffer) == 0  # should have been flushed to the DB
        self.dh.upsert_rpsl_object(rpsl_object_route_v6, JournalEntryOrigin.auth_change, source_serial=43)

        self.dh.commit()
        self.dh.refresh_connection()

        # There should be two entries with MNT-CORRECT in the db now.
        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 2
        assert "parsed_data" in result[0]
        assert "object_text" in result[0]

        query = RPSLDatabaseQuery(["parsed_data"]).lookup_attr("mnt-by", "MNT-CORRECT")
        result = list(self.dh.execute_query(query))
        assert len(result) == 2
        assert "parsed_data" in result[0]
        assert "object_text" not in result[0]

        # This object should be ignored due to a rollback.
        rpsl_obj_ignored = Mock(
            pk=lambda: "AS2914",
            rpsl_object_class="aut-num",
            parsed_data={"mnt-by": "MNT-CORRECT", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            prefix=None,
            prefix_length=None,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh.upsert_rpsl_object(rpsl_obj_ignored, JournalEntryOrigin.auth_change)
        assert len(self.dh._rpsl_upsert_buffer) == 1
        self.dh.upsert_rpsl_object(rpsl_obj_ignored, JournalEntryOrigin.auth_change)
        assert len(self.dh._rpsl_upsert_buffer) == 1
        # Flush the buffer to make sure the INSERT is issued but then rolled back
        self.dh._flush_rpsl_object_writing_buffer()
        self.dh.rollback()

        statistics = list(self.dh.execute_query(RPSLDatabaseObjectStatisticsQuery()))

        assert statistics == [
            {"source": "TEST", "object_class": "route", "count": 1},
            {"source": "TEST2", "object_class": "route", "count": 1},
        ]

        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 2

        self.dh.delete_rpsl_object(
            rpsl_object=rpsl_object_route_v6, origin=JournalEntryOrigin.auth_change, source_serial=44
        )
        self.dh.delete_rpsl_object(
            rpsl_object=rpsl_object_route_v6, origin=JournalEntryOrigin.auth_change, source_serial=45
        )
        query = RPSLDatabaseQuery()
        result = list(self.dh.execute_query(query))
        assert len(result) == 1

        self.dh.record_mirror_error("TEST2", "error")
        self.dh.record_serial_exported("TEST2", "424242")
        self.dh.commit()

        journal = self._clean_result(self.dh.execute_query(RPSLDatabaseJournalQuery()))

        # The IPv6 object was created in a different source, so it should
        # have a separate sequence of NRTM serials.
        assert journal == [
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "serial_nrtm": 1,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 1,
            },
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "serial_nrtm": 2,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 2,
            },
            {
                "rpsl_pk": "2001:db8::/64,AS65537",
                "source": "TEST2",
                "serial_nrtm": 42,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 3,
            },
            {
                "rpsl_pk": "2001:db8::/64,AS65537",
                "source": "TEST2",
                "serial_nrtm": 43,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 4,
            },
            {
                "rpsl_pk": "2001:db8::/64,AS65537",
                "source": "TEST2",
                "serial_nrtm": 44,
                "operation": DatabaseOperation.delete,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 7,
            },
        ]

        partial_journal = self._clean_result(
            self.dh.execute_query(RPSLDatabaseJournalQuery().sources(["TEST"]).serial_nrtm_range(1, 1))
        )
        assert partial_journal == [
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "serial_nrtm": 1,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 1,
            },
        ]
        partial_journal = self._clean_result(
            self.dh.execute_query(RPSLDatabaseJournalQuery().sources(["TEST"]).serial_nrtm_range(1))
        )
        assert partial_journal == [
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "serial_nrtm": 1,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 1,
            },
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "serial_nrtm": 2,
                "operation": DatabaseOperation.add_or_update,
                "object_class": "route",
                "object_text": "object-text",
                "origin": JournalEntryOrigin.auth_change,
                "serial_global": 2,
            },
        ]

        # Override the config to enable synchronised serials for TEST
        config_override(
            {
                "sources": {
                    "TEST": {"keep_journal": True, "nrtm_host": "a", "rpki_excluded": True},
                    "TEST2": {"keep_journal": True, "nrtm_host": "a", "rpki_excluded": True},
                }
            }
        )

        self.dh.set_force_reload("TEST")
        self.dh.commit()
        status_test = list(self.dh.execute_query(DatabaseStatusQuery().source("TEST")))
        assert self._clean_result(status_test) == [
            {
                "source": "TEST",
                "serial_oldest_journal": 1,
                "serial_newest_journal": 2,
                "serial_oldest_seen": None,
                "serial_newest_seen": None,
                "serial_last_export": None,
                "serial_newest_mirror": None,
                "last_error": None,
                "force_reload": True,
                "synchronised_serials": True,
            },
        ]
        assert status_test[0]["created"]
        assert status_test[0]["updated"]
        assert not status_test[0]["last_error_timestamp"]

        self.dh.record_serial_newest_mirror("TEST2", 99999999)
        self.dh.record_serial_seen("TEST2", 44)
        self.dh.set_force_reload("TEST2")  # should be ignored, source is new
        self.dh.commit()

        status_test2 = list(self.dh.execute_query(DatabaseStatusQuery().source("TEST2")))
        assert self._clean_result(status_test2) == [
            {
                "source": "TEST2",
                "serial_oldest_journal": 42,
                "serial_newest_journal": 44,
                "serial_oldest_seen": 42,
                "serial_newest_seen": 44,
                "serial_last_export": 424242,
                "serial_newest_mirror": 99999999,
                "last_error": "error",
                "force_reload": False,
                "synchronised_serials": True,
            },
        ]
        assert status_test2[0]["created"]
        assert status_test2[0]["updated"]
        assert status_test2[0]["last_error_timestamp"]

        self.dh.upsert_rpsl_object(rpsl_object_route_v6, JournalEntryOrigin.auth_change, source_serial=45)
        assert len(list(self.dh.execute_query(RPSLDatabaseQuery().sources(["TEST"])))) == 1
        assert len(list(self.dh.execute_query(DatabaseStatusQuery().sources(["TEST"]))))
        assert len(list(self.dh.execute_query(RPSLDatabaseQuery().sources(["TEST2"])))) == 1
        self.dh.delete_all_rpsl_objects_with_journal("TEST")
        assert not len(list(self.dh.execute_query(RPSLDatabaseQuery().sources(["TEST"]))))
        assert not len(list(self.dh.execute_query(DatabaseStatusQuery().sources(["TEST"]))))
        assert len(list(self.dh.execute_query(RPSLDatabaseQuery().sources(["TEST2"])))) == 1

        self.dh.close()

        assert flatten_mock_calls(self.dh.changed_objects_tracker.preloader.signal_reload) == [
            ["", ({"route"},), {}],
            ["", ({"route"},), {}],
        ]

    def test_disable_journaling(self, monkeypatch, irrd_database):
        monkeypatch.setenv("IRRD_SOURCES_TEST_AUTHORITATIVE", "1")
        monkeypatch.setenv("IRRD_SOURCES_TEST_KEEP_JOURNAL", "1")

        rpsl_object_route_v4 = Mock(
            pk=lambda: "192.0.2.0/24,AS65537",
            rpsl_object_class="route",
            parsed_data={"source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.255"),
            prefix=IP("192.0.2.0/24"),
            prefix_length=24,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )

        self.dh = DatabaseHandler()
        self.dh.disable_journaling()
        self.dh.upsert_rpsl_object(rpsl_object_route_v4, JournalEntryOrigin.auth_change)
        self.dh.commit()

        assert not self._clean_result(self.dh.execute_query(RPSLDatabaseJournalQuery()))

        status_test = self._clean_result(self.dh.execute_query(DatabaseStatusQuery()))
        assert status_test == [
            {
                "source": "TEST",
                "serial_oldest_journal": None,
                "serial_newest_journal": None,
                "serial_oldest_seen": None,
                "serial_newest_seen": None,
                "serial_last_export": None,
                "serial_newest_mirror": None,
                "last_error": None,
                "force_reload": False,
                "synchronised_serials": False,
            },
        ]

        self.dh.enable_journaling()
        self.dh.upsert_rpsl_object(rpsl_object_route_v4, JournalEntryOrigin.auth_change)
        self.dh.commit()
        assert self._clean_result(self.dh.execute_query(RPSLDatabaseJournalQuery()))

        self.dh.close()

    def test_roa_handling_and_query(self, irrd_database):
        self.dh = DatabaseHandler()
        self.dh.insert_roa_object(
            ip_version=4, prefix_str="192.0.2.0/24", asn=64496, max_length=28, trust_anchor="TEST TA"
        )
        self.dh.insert_roa_object(
            ip_version=6, prefix_str="2001:db8::/32", asn=64497, max_length=64, trust_anchor="TEST TA"
        )
        self.dh.commit()

        roas = self._clean_result(self.dh.execute_query(ROADatabaseObjectQuery()))
        assert roas == [
            {
                "prefix": "192.0.2.0/24",
                "asn": 64496,
                "max_length": 28,
                "trust_anchor": "TEST TA",
                "ip_version": 4,
            },
            {
                "prefix": "2001:db8::/32",
                "asn": 64497,
                "max_length": 64,
                "trust_anchor": "TEST TA",
                "ip_version": 6,
            },
        ]

        assert (
            len(
                list(
                    self.dh.execute_query(
                        ROADatabaseObjectQuery().ip_less_specific_or_exact(IP("192.0.2.0/23"))
                    )
                )
            )
            == 0
        )
        assert (
            len(
                list(
                    self.dh.execute_query(
                        ROADatabaseObjectQuery().ip_less_specific_or_exact(IP("192.0.2.0/24"))
                    )
                )
            )
            == 1
        )
        assert (
            len(
                list(
                    self.dh.execute_query(
                        ROADatabaseObjectQuery().ip_less_specific_or_exact(IP("192.0.2.0/25"))
                    )
                )
            )
            == 1
        )

        self.dh.delete_all_roa_objects()
        self.dh.commit()
        roas = self._clean_result(self.dh.execute_query(ROADatabaseObjectQuery()))
        assert roas == []

        self.dh.close()

    def test_rpki_status_storage(self, monkeypatch, irrd_database, database_handler_with_route):
        monkeypatch.setenv("IRRD_SOURCES_TEST_KEEP_JOURNAL", "1")
        dh = database_handler_with_route

        # Create a second route object, whose status should never be changed,
        # even though it has the same rpsl_pk - see #461
        second_route_obj = Mock(
            pk=lambda: "192.0.2.0/24,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "RPKI-EXCLUDED"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.255"),
            prefix=IP("192.0.2.0/24"),
            prefix_length=24,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        dh.upsert_rpsl_object(second_route_obj, JournalEntryOrigin.auth_change)

        route1_pk = list(dh.execute_query(RPSLDatabaseQuery().sources(["TEST"])))[0]["pk"]
        route_rpsl_objs = [
            {
                "pk": route1_pk,
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "object_class": "route",
                "object_text": "object-text",
                "old_status": RPKIStatus.invalid,  # This always triggers a journal entry
                "scopefilter_status": ScopeFilterStatus.in_scope,
                "route_preference_status": RoutePreferenceStatus.visible,
            }
        ]

        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.invalid])))) == 1
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.not_found])))) == 1

        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.not_found
        dh.update_rpki_status(rpsl_objs_now_not_found=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.not_found])))) == 2
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(1, 1)))
        assert journal_entry[0]["operation"] == DatabaseOperation.add_or_update

        dh.update_rpki_status()
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.not_found])))) == 2
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 1  # no new entry

        route_rpsl_objs[0]["old_status"] = RPKIStatus.valid
        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.invalid
        dh.update_rpki_status(rpsl_objs_now_invalid=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.invalid])))) == 1
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(2, 2)))
        assert journal_entry[0]["operation"] == DatabaseOperation.delete

        dh.update_rpki_status(rpsl_objs_now_invalid=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.invalid])))) == 1
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(3, 3)))
        assert journal_entry[0]["operation"] == DatabaseOperation.delete

        route_rpsl_objs[0]["old_status"] = RPKIStatus.invalid
        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.not_found
        dh.update_rpki_status(rpsl_objs_now_not_found=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.not_found])))) == 2
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(4, 4)))
        assert journal_entry[0]["operation"] == DatabaseOperation.add_or_update

        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.valid
        dh.update_rpki_status(rpsl_objs_now_valid=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.valid])))) == 1
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(5, 5)))
        assert journal_entry[0]["operation"] == DatabaseOperation.add_or_update

        # A state change from valid to not_found should not trigger a journal entry
        route_rpsl_objs[0]["old_status"] = RPKIStatus.valid
        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.not_found
        dh.update_rpki_status(rpsl_objs_now_not_found=route_rpsl_objs)
        assert not list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(6, 6)))

        # State change from invalid to valid should not create journal entry
        # if scope filter is still out of scope
        route_rpsl_objs[0].update(
            {
                "old_status": RPKIStatus.invalid,
                "rpki_status": RPKIStatus.valid,
                "scopefilter_status": ScopeFilterStatus.out_scope_as,
            }
        )
        dh.update_rpki_status(rpsl_objs_now_valid=route_rpsl_objs)
        assert len(list(dh.execute_query(RPSLDatabaseQuery().rpki_status([RPKIStatus.valid])))) == 1
        assert not list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(6, 6)))

        dh.delete_journal_entries_before_date(datetime.utcnow(), "TEST")
        assert not list(dh.execute_query(RPSLDatabaseJournalQuery()))

    def test_scopefilter_status_storage(self, monkeypatch, irrd_database, database_handler_with_route):
        monkeypatch.setenv("IRRD_SOURCES_TEST_KEEP_JOURNAL", "1")
        dh = database_handler_with_route
        route_rpsl_objs = [
            {
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "object_class": "route",
                "object_text": "object-text",
                "old_status": ScopeFilterStatus.in_scope,
                "rpki_status": RPKIStatus.valid,
                "route_preference_status": RoutePreferenceStatus.visible,
            }
        ]

        assert (
            len(list(dh.execute_query(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.in_scope]))))
            == 1
        )

        route_rpsl_objs[0]["scopefilter_status"] = ScopeFilterStatus.out_scope_prefix
        dh.update_scopefilter_status(rpsl_objs_now_out_scope_prefix=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.out_scope_prefix])
                    )
                )
            )
            == 1
        )
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(1, 1)))
        assert journal_entry[0]["operation"] == DatabaseOperation.delete

        dh.update_scopefilter_status()
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.out_scope_prefix])
                    )
                )
            )
            == 1
        )
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 1  # no new entry

        route_rpsl_objs[0]["old_status"] = ScopeFilterStatus.out_scope_prefix
        route_rpsl_objs[0]["scopefilter_status"] = ScopeFilterStatus.out_scope_prefix
        dh.update_scopefilter_status(rpsl_objs_now_out_scope_as=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.out_scope_as]))
                )
            )
            == 1
        )
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 1  # no new entry

        route_rpsl_objs[0]["scopefilter_status"] = ScopeFilterStatus.in_scope
        dh.update_scopefilter_status(rpsl_objs_now_in_scope=route_rpsl_objs)
        assert (
            len(list(dh.execute_query(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.in_scope]))))
            == 1
        )
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(2, 2)))
        assert journal_entry[0]["operation"] == DatabaseOperation.add_or_update

        # Special case: updating the status from out to in scope while RPKI invalid,
        # should change the status but not create a journal entry - see #524
        route_rpsl_objs[0].update(
            {
                "old_status": ScopeFilterStatus.out_scope_as,
                "scopefilter_status": ScopeFilterStatus.in_scope,
                "rpki_status": RPKIStatus.invalid,
            }
        )
        dh.update_scopefilter_status(rpsl_objs_now_in_scope=route_rpsl_objs)
        assert (
            len(list(dh.execute_query(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.in_scope]))))
            == 1
        )
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 2  # no new entry since last test

    def test_route_preference_status_storage(self, monkeypatch, irrd_database, database_handler_with_route):
        monkeypatch.setenv("IRRD_SOURCES_TEST_KEEP_JOURNAL", "1")
        dh = database_handler_with_route
        existing_pk = list(dh.execute_query(RPSLDatabaseQuery()))[0]["pk"]
        route_rpsl_objs = [
            {
                "pk": existing_pk,
                "rpsl_pk": "192.0.2.0/24,AS65537",
                "source": "TEST",
                "object_class": "route",
                "object_text": "object-text",
                "rpki_status": RPKIStatus.valid,
                "scopefilter_status": ScopeFilterStatus.in_scope,
            }
        ]

        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.visible])
                    )
                )
            )
            == 1
        )

        dh.update_route_preference_status(rpsl_objs_now_suppressed=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.suppressed])
                    )
                )
            )
            == 1
        )
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(1, 1)))
        assert journal_entry[0]["operation"] == DatabaseOperation.delete

        dh.update_scopefilter_status()
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.suppressed])
                    )
                )
            )
            == 1
        )
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 1  # no new entry

        dh.update_route_preference_status(rpsl_objs_now_visible=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.visible])
                    )
                )
            )
            == 1
        )
        journal_entry = list(dh.execute_query(RPSLDatabaseJournalQuery().serial_nrtm_range(2, 2)))
        assert journal_entry[0]["operation"] == DatabaseOperation.add_or_update

        # Special case: updating the status while RPKI invalid,
        # should change the status but not create a journal entry - see #524
        route_rpsl_objs[0]["rpki_status"] = RPKIStatus.invalid
        dh.update_route_preference_status(rpsl_objs_now_suppressed=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.suppressed])
                    )
                )
            )
            == 1
        )
        dh.update_route_preference_status(rpsl_objs_now_visible=route_rpsl_objs)
        assert (
            len(
                list(
                    dh.execute_query(
                        RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.visible])
                    )
                )
            )
            == 1
        )
        assert len(list(dh.execute_query(RPSLDatabaseJournalQuery()))) == 2  # no new entry since last test

    def _clean_result(self, results):
        variable_fields = ["pk", "timestamp", "created", "updated", "last_error_timestamp"]
        return [{k: v for k, v in result.items() if k not in variable_fields} for result in list(results)]

    def test_suspension(self, monkeypatch, irrd_database, database_handler_with_route, config_override):
        monkeypatch.setenv("IRRD_SOURCES_TEST_KEEP_JOURNAL", "1")
        dh = database_handler_with_route
        route_object = next(dh.execute_query(RPSLDatabaseQuery()))
        with pytest.raises(ValueError):
            dh.suspend_rpsl_object(uuid.uuid4())
        dh.suspend_rpsl_object(route_object["pk"])

        assert len(list(dh.execute_query(RPSLDatabaseQuery()))) == 0
        suspended_objs = list(dh.execute_query(RPSLDatabaseSuspendedQuery()))
        assert len(suspended_objs) == 1
        assert suspended_objs[0]["rpsl_pk"] == "192.0.2.0/24,AS65537"
        assert set(suspended_objs[0]["mntners"]) == {"MNT-TEST", "MNT-TEST2"}

        journal = list(dh.execute_query(RPSLDatabaseJournalQuery()))
        assert len(journal) == 1
        assert journal[0]["rpsl_pk"] == "192.0.2.0/24,AS65537"
        assert journal[0]["operation"] == DatabaseOperation.delete

        assert len(list(dh.execute_query(RPSLDatabaseSuspendedQuery().mntner("MNT-TEST")))) == 1
        assert len(list(dh.execute_query(RPSLDatabaseSuspendedQuery().mntner("MNT-TEST2")))) == 1
        assert len(list(dh.execute_query(RPSLDatabaseSuspendedQuery().mntner("MNT-NO")))) == 0

        dh.delete_suspended_rpsl_objects([suspended_objs[0]["pk"]])
        assert len(list(dh.execute_query(RPSLDatabaseSuspendedQuery()))) == 0


# noinspection PyTypeChecker
class TestRPSLDatabaseQueryLive:
    def test_matching_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route

        # Each of these filters should match
        self._assert_match(RPSLDatabaseQuery().rpsl_pk("192.0.2.0/24,AS65537"))
        self._assert_match(RPSLDatabaseQuery().sources(["TEST", "X"]))
        self._assert_match(RPSLDatabaseQuery().object_classes(["route"]))
        self._assert_match(RPSLDatabaseQuery().lookup_attr("mnt-by", "MNT-test"))  # intentional case mismatch
        self._assert_match(RPSLDatabaseQuery().ip_exact(IP("192.0.2.0/24")))
        self._assert_match(RPSLDatabaseQuery().asn(65537))
        self._assert_match(RPSLDatabaseQuery().asns_first([65538, 65537]))
        self._assert_match(RPSLDatabaseQuery().asn_less_specific(65537))
        self._assert_match(RPSLDatabaseQuery().ip_more_specific(IP("192.0.0.0/21")))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP("192.0.2.0/24")))
        self._assert_match(RPSLDatabaseQuery().ip_less_specific(IP("192.0.2.0/25")))
        self._assert_match(RPSLDatabaseQuery().ip_any(IP("192.0.0.0/21")))
        self._assert_match(RPSLDatabaseQuery().ip_any(IP("192.0.2.0/24")))
        self._assert_match(RPSLDatabaseQuery().ip_any(IP("192.0.2.0/25")))
        self._assert_match(RPSLDatabaseQuery().text_search("192.0.2.0/24"))
        self._assert_match(RPSLDatabaseQuery().text_search("192.0.2.0/25"))
        self._assert_match(RPSLDatabaseQuery().text_search("192.0.2.1"))
        self._assert_match(RPSLDatabaseQuery().text_search("192.0.2.0/24,As65537"))
        self._assert_match(RPSLDatabaseQuery().rpki_status([RPKIStatus.invalid]))
        self._assert_match(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.in_scope]))
        self._assert_match(RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.visible]))

    def test_chained_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route

        q = (
            RPSLDatabaseQuery()
            .rpsl_pk("192.0.2.0/24,AS65537")
            .sources(["TEST", "X"])
            .object_classes(["route"])
        )
        q = q.lookup_attr("mnt-by", "MNT-TEST").ip_exact(IP("192.0.2.0/24")).asn_less_specific(65537)
        q = q.ip_less_specific(IP("192.0.2.0/25")).ip_less_specific(IP("192.0.2.0/24"))
        q = q.ip_more_specific(IP("192.0.0.0/21"))
        q = q.ip_any(IP("192.0.0.0/21"))

        result = [i for i in self.dh.execute_query(q)]
        assert len(result) == 1, f"Failed query: {q}"
        pk = result[0]["pk"]

        self._assert_match(RPSLDatabaseQuery().pk(pk))
        self._assert_match(RPSLDatabaseQuery().pks([pk]))

    def test_non_matching_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        # None of these should match
        self._assert_no_match(RPSLDatabaseQuery().pk(str(uuid.uuid4())))
        self._assert_no_match(RPSLDatabaseQuery().pks([str(uuid.uuid4())]))
        self._assert_no_match(RPSLDatabaseQuery().rpsl_pk("foo"))
        self._assert_no_match(RPSLDatabaseQuery().sources(["TEST3"]))
        self._assert_no_match(RPSLDatabaseQuery().object_classes(["route6"]))
        self._assert_no_match(RPSLDatabaseQuery().lookup_attr("mnt-by", "MNT-NOTEXIST"))
        self._assert_no_match(RPSLDatabaseQuery().ip_exact(IP("192.0.2.0/25")))
        self._assert_no_match(RPSLDatabaseQuery().asn(23455))
        self._assert_no_match(RPSLDatabaseQuery().asns_first([65538, 65539]))
        self._assert_no_match(RPSLDatabaseQuery().asn_less_specific(23455))
        self._assert_no_match(RPSLDatabaseQuery().ip_more_specific(IP("192.0.2.0/24")))
        self._assert_no_match(RPSLDatabaseQuery().ip_less_specific(IP("192.0.2.0/23")))
        self._assert_no_match(RPSLDatabaseQuery().ip_any(IP("192.0.3.0/24")))
        self._assert_no_match(RPSLDatabaseQuery().text_search("192.0.2.0/23"))
        self._assert_no_match(RPSLDatabaseQuery().text_search("AS2914"))
        self._assert_no_match(RPSLDatabaseQuery().text_search("65537"))
        self._assert_no_match(RPSLDatabaseQuery().rpki_status([RPKIStatus.valid]))
        self._assert_no_match(RPSLDatabaseQuery().scopefilter_status([ScopeFilterStatus.out_scope_as]))
        self._assert_no_match(RPSLDatabaseQuery().route_preference_status([RoutePreferenceStatus.suppressed]))

    def test_ordering_sources(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        rpsl_object_2 = Mock(
            pk=lambda: "192.0.2.1/32,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "AAA-TST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.1"),
            ip_last=IP("192.0.2.1"),
            prefix=IP("192.0.2.0/32"),
            prefix_length=32,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        rpsl_object_3 = Mock(
            pk=lambda: "192.0.2.2/32,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "OTHER-SOURCE"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.2"),
            ip_last=IP("192.0.2.2"),
            prefix=IP("192.0.2.0/24"),
            prefix_length=32,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh.upsert_rpsl_object(rpsl_object_2, JournalEntryOrigin.auth_change)
        self.dh.upsert_rpsl_object(rpsl_object_3, JournalEntryOrigin.auth_change)

        query = RPSLDatabaseQuery()
        response_sources = [r["source"] for r in self.dh.execute_query(query)]
        assert response_sources == ["TEST", "AAA-TST", "OTHER-SOURCE"]  # ordered by IP

        query = RPSLDatabaseQuery().sources(["OTHER-SOURCE", "AAA-TST", "TEST"])
        response_sources = [r["source"] for r in self.dh.execute_query(query)]
        assert response_sources == ["OTHER-SOURCE", "AAA-TST", "TEST"]

        query = RPSLDatabaseQuery().sources(["TEST", "AAA-TST", "TEST"])
        response_sources = [r["source"] for r in self.dh.execute_query(query)]
        assert response_sources == ["TEST", "AAA-TST"]

        query = RPSLDatabaseQuery().sources(["AAA-TST", "TEST"]).first_only()
        response_sources = [r["source"] for r in self.dh.execute_query(query)]
        assert response_sources == ["AAA-TST"]

        query = RPSLDatabaseQuery().sources(["OTHER-SOURCE", "TEST"]).first_only()
        response_sources = [r["source"] for r in self.dh.execute_query(query)]
        assert response_sources == ["OTHER-SOURCE"]

    def test_text_search_person_role(self, irrd_database):
        rpsl_object_person = Mock(
            pk=lambda: "PERSON",
            rpsl_object_class="person",
            parsed_data={"person": "my person-name", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            prefix=None,
            prefix_length=None,
            asn_first=None,
            asn_last=None,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        rpsl_object_role = Mock(
            pk=lambda: "ROLE",
            rpsl_object_class="person",
            parsed_data={"person": "my role-name", "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: None,
            ip_first=None,
            ip_last=None,
            prefix=None,
            prefix_length=None,
            asn_first=None,
            asn_last=None,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh = DatabaseHandler()
        self.dh.upsert_rpsl_object(rpsl_object_person, JournalEntryOrigin.auth_change)
        self.dh.upsert_rpsl_object(rpsl_object_role, JournalEntryOrigin.auth_change)

        self._assert_match(RPSLDatabaseQuery().text_search("person-name"))
        self._assert_match(RPSLDatabaseQuery().text_search("role-name"))

        self.dh.close()

    def test_more_less_specific_filters(self, irrd_database, database_handler_with_route):
        self.dh = database_handler_with_route
        rpsl_route_more_specific_25_1 = Mock(
            pk=lambda: "192.0.2.0/25,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.127"),
            prefix=IP("192.0.2.0/25"),
            prefix_length=25,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        rpsl_route_more_specific_25_2 = Mock(
            pk=lambda: "192.0.2.128/25,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "TEST"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.128"),
            ip_last=IP("192.0.2.255"),
            prefix=IP("192.0.2.128/25"),
            prefix_length=25,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        rpsl_route_more_specific_26 = Mock(
            pk=lambda: "192.0.2.0/26,AS65537",
            rpsl_object_class="route",
            parsed_data={"mnt-by": ["MNT-TEST", "MNT-TEST2"], "source": "TEST2"},
            render_rpsl_text=lambda last_modified: "object-text",
            ip_version=lambda: 4,
            ip_first=IP("192.0.2.0"),
            ip_last=IP("192.0.2.63"),
            prefix=IP("192.0.2.0/26"),
            prefix_length=26,
            asn_first=65537,
            asn_last=65537,
            rpki_status=RPKIStatus.not_found,
            scopefilter_status=ScopeFilterStatus.in_scope,
            route_preference_status=RoutePreferenceStatus.visible,
        )
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_25_1, JournalEntryOrigin.auth_change)
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_25_2, JournalEntryOrigin.auth_change)
        self.dh.upsert_rpsl_object(rpsl_route_more_specific_26, JournalEntryOrigin.auth_change)
        self.dh.commit()

        self.dh.close()
        self.dh = DatabaseHandler(readonly=True)
        self.dh.refresh_connection()

        q = RPSLDatabaseQuery().ip_any(IP("192.0.2.0/25"))
        rpsl_pks = [r["rpsl_pk"] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 3, f"Failed query: {q}"
        assert "192.0.2.0/24,AS65537" in rpsl_pks
        assert "192.0.2.0/25,AS65537" in rpsl_pks
        assert "192.0.2.0/26,AS65537" in rpsl_pks

        q = RPSLDatabaseQuery().ip_more_specific(IP("192.0.2.0/24"))
        rpsl_pks = [r["rpsl_pk"] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 3, f"Failed query: {q}"
        assert "192.0.2.0/25,AS65537" in rpsl_pks
        assert "192.0.2.128/25,AS65537" in rpsl_pks
        assert "192.0.2.0/26,AS65537" in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific(IP("192.0.2.0/25"))
        rpsl_pks = [r["rpsl_pk"] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 2, f"Failed query: {q}"
        assert "192.0.2.0/25,AS65537" in rpsl_pks
        assert "192.0.2.0/24,AS65537" in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific_one_level(IP("192.0.2.0/26"))
        rpsl_pks = [r["rpsl_pk"] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 1, f"Failed query: {q}"
        assert "192.0.2.0/25,AS65537" in rpsl_pks

        q = RPSLDatabaseQuery().ip_less_specific(IP("192.0.2.0/25")).first_only()
        rpsl_pks = [r["rpsl_pk"] for r in self.dh.execute_query(q)]
        assert len(rpsl_pks) == 1, f"Failed query: {q}"
        assert "192.0.2.0/24,AS65537" in rpsl_pks

        q = RPSLDatabaseQuery().sources(["TEST"]).ip_less_specific_one_level(IP("192.0.2.0/27"))
        self._assert_match(q)

    def test_modify_frozen_filter(self):
        with raises(ValueError) as ve:
            RPSLDatabaseQuery().ip_less_specific_one_level(IP("192.0.2.0/27")).sources(["TEST"])
        assert "frozen" in str(ve.value)

    def test_invalid_lookup_attribute(self):
        with raises(ValueError) as ve:
            RPSLDatabaseQuery().lookup_attr("not-a-lookup-attr", "value")
        assert "Invalid lookup attribute" in str(ve.value)

    def _assert_match(self, query):
        __tracebackhide__ = True
        assert len(list(self.dh.execute_query(query))) == 1, f"Failed query: {query}"

    def _assert_no_match(self, query):
        __tracebackhide__ = True
        result = list(self.dh.execute_query(query))
        assert not len(result), f"Failed query: {query}: unexpected output: {result}"
