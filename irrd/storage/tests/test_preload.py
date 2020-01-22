import os

import pytest
import threading
from unittest.mock import Mock

from irrd.rpki.status import RPKIStatus
from ..database_handler import DatabaseHandler
from ..queries import RPSLDatabaseQuery
from irrd.utils.test_utils import flatten_mock_calls
from ..preload import Preloader, PreloadUpdater, get_preloader, send_reload_signal


@pytest.fixture()
def prepare_preload_updater_mock(monkeypatch):
    mock_preload_updater = Mock(spec=PreloadUpdater)
    monkeypatch.setattr('irrd.storage.preload.PreloadUpdater', mock_preload_updater)

    return mock_preload_updater


class TestPreloader:
    def test_load_reload(self, prepare_preload_updater_mock, tmpdir, caplog):
        mock_preload_updater = prepare_preload_updater_mock
        preloader = get_preloader()
        preload2 = get_preloader()
        assert preloader == preload2

        assert mock_preload_updater.mock_calls[0][0] == ''
        assert mock_preload_updater.mock_calls[0][1][0] == preloader
        assert mock_preload_updater.mock_calls[0][1][1] == preloader._reload_lock
        assert mock_preload_updater.mock_calls[0][1][2] == preloader._store_ready_event
        assert mock_preload_updater.mock_calls[1][0] == '().start'
        assert len(mock_preload_updater.mock_calls) == 2
        assert len(preloader._threads) == 1
        mock_preload_updater.reset_mock()

        # First call should be ignored, inetnums are not preloaded
        preloader.reload({'inetnum'})
        preloader.reload({'route'})

        assert mock_preload_updater.mock_calls[0][0] == '().is_alive'
        assert mock_preload_updater.mock_calls[1][0] == ''
        assert mock_preload_updater.mock_calls[1][1][0] == preloader
        assert mock_preload_updater.mock_calls[2][0] == '().start'
        assert len(mock_preload_updater.mock_calls) == 3
        assert len(preloader._threads) == 2
        mock_preload_updater.reset_mock()

        # Two threads already running, do nothing
        preloader.reload()

        assert mock_preload_updater.mock_calls[0][0] == '().is_alive'
        assert mock_preload_updater.mock_calls[1][0] == '().is_alive'
        assert len(mock_preload_updater.mock_calls) == 2
        assert len(preloader._threads) == 2
        mock_preload_updater.reset_mock()

        # Assume all threads are dead
        for thread in preloader._threads:
            thread.is_alive = lambda: False

        # Call the reload indirectly through a signal
        pidfile = str(tmpdir) + '/pidfile'
        with open(pidfile, 'w') as fh:
            fh.write(str(os.getpid()))
        send_reload_signal(pidfile)

        assert mock_preload_updater.mock_calls[0][0] == ''
        assert mock_preload_updater.mock_calls[0][1][0] == preloader
        assert mock_preload_updater.mock_calls[1][0] == '().start'
        assert len(mock_preload_updater.mock_calls) == 2
        assert len(preloader._threads) == 2
        mock_preload_updater.reset_mock()

    def test_reload_signal_incorrect_pid(self, prepare_preload_updater_mock, tmpdir, caplog):
        mock_preload_updater = prepare_preload_updater_mock
        pidfile = str(tmpdir) + '/pidfile'
        with open(pidfile, 'w') as fh:
            fh.write('a')

        # Call the reload signal with an incorrect PID and incorrect filename
        send_reload_signal(pidfile)
        assert 'Attempted to send reload signal to update preloader for IRRD on PID a, but process is' in caplog.text
        send_reload_signal(str(tmpdir) + '/invalid_pidfile')
        assert 'but file could not be opened: [Errno 2] No such file or directory' in caplog.text
        assert not len(mock_preload_updater.mock_calls)

    def test_routes_for_origins(self, prepare_preload_updater_mock):
        preloader = Preloader()
        preloader._store_ready_event.set()

        preloader.update_route_store(
            {
                'AS65546': {'TEST2': {'192.0.2.0/25'}},
                'AS65547': {'TEST1': {'192.0.2.128/25', '198.51.100.0/25'}}
            },
            {
                'AS65547': {'TEST2': {'2001:db8::/32'}}
            },
        )

        sources = ['TEST1', 'TEST2']
        assert preloader.routes_for_origins(['AS65545'], sources) == set()
        assert preloader.routes_for_origins(['AS65546'], sources, 4) == {'192.0.2.0/25'}
        assert preloader.routes_for_origins(['AS65547'], sources, 4) == {'192.0.2.128/25', '198.51.100.0/25'}
        assert preloader.routes_for_origins(['AS65546'], sources, 6) == set()
        assert preloader.routes_for_origins(['AS65547'], sources, 6) == {'2001:db8::/32'}
        assert preloader.routes_for_origins(['AS65546'], sources) == {'192.0.2.0/25'}
        assert preloader.routes_for_origins(['AS65547'], sources) == {'192.0.2.128/25', '198.51.100.0/25', '2001:db8::/32'}
        assert preloader.routes_for_origins(['AS65547', 'AS65546'], sources, 4) == {'192.0.2.0/25', '192.0.2.128/25', '198.51.100.0/25'}

        assert preloader.routes_for_origins(['AS65547', 'AS65546'], ['TEST1']) == {'192.0.2.128/25', '198.51.100.0/25'}
        assert preloader.routes_for_origins(['AS65547', 'AS65546'], ['TEST2']) == {'192.0.2.0/25', '2001:db8::/32'}

        with pytest.raises(ValueError) as ve:
            preloader.routes_for_origins(['AS65547'], sources, 2)
        assert 'Invalid IP version: 2' in str(ve.value)


class TestPreloadUpdater:
    def test_preload_updater(self, monkeypatch):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr('irrd.storage.preload.RPSLDatabaseQuery',
                            lambda column_names, enable_ordering: mock_database_query)
        mock_reload_lock = Mock()
        mock_ready_event = Mock(spec=threading.Event)
        mock_preload_obj = Mock()

        mock_query_result = [
            {
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 25,
                'asn_first': 65546,
                'source': 'TEST1',
            },
            {
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 25,
                'asn_first': 65547,
                'source': 'TEST1',
            },
            {
                'ip_version': 4,
                'ip_first': '198.51.100.0',
                'ip_size': 128,
                'asn_first': 65547,
                'source': 'TEST1',
            },
            {
                'ip_version': 6,
                'ip_first': '2001:db8::',
                'prefix_length': 32,
                'asn_first': 65547,
                'source': 'TEST2',
            },
        ]
        mock_database_handler.execute_query = lambda query: mock_query_result
        PreloadUpdater(mock_preload_obj, mock_reload_lock, mock_ready_event).run(mock_database_handler)

        assert flatten_mock_calls(mock_reload_lock) == [['acquire', (), {}], ['release', (), {}]]
        assert flatten_mock_calls(mock_ready_event) == [['set', (), {}]]
        assert flatten_mock_calls(mock_database_query) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['rpki_status', ([RPKIStatus.unknown, RPKIStatus.valid],), {}],
        ]

        assert flatten_mock_calls(mock_preload_obj) == [
            [
                'update_route_store',
                (
                    {
                        'AS65546': {'TEST1': {'192.0.2.0/25'}},
                        'AS65547': {'TEST1': {'192.0.2.128/25', '198.51.100.0/25'}}
                    },
                    {
                        'AS65547': {'TEST2': {'2001:db8::/32'}}
                    },
                ),
                {}
            ]
        ]
