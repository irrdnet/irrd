from base64 import b64decode
from typing import List
from unittest.mock import Mock

import pytest

from irrd.conf import DEFAULT_SETTINGS
from irrd.utils.test_utils import flatten_mock_calls
from ..nrtm_runner import MirrorUpdateRunner, MirrorFullImportRunner, NRTMUpdateStreamRunner


class TestMirrorUpdateRunner:
    def test_full_import_call(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.nrtm_runner.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.RPSLDatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.MirrorFullImportRunner', lambda source: mock_full_import_runner)

        mock_dh.execute_query = lambda q: iter([])
        runner = MirrorUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == 'run'

    def test_update_stream_call(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_stream_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.nrtm_runner.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.RPSLDatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.NRTMUpdateStreamRunner', lambda source: mock_stream_runner)

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242}])
        runner = MirrorUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_stream_runner.mock_calls) == 1
        assert mock_stream_runner.mock_calls[0][0] == 'run'
        assert mock_stream_runner.mock_calls[0][1] == (424242,)


class TestMirrorFullImportRunner:
    def test_run_import(self, monkeypatch):
        DEFAULT_SETTINGS['sources'] = {'TEST': {
            'dump_source': 'ftp://host/source1.gz,ftp://host/source2',
            'dump_serial_source': 'ftp://host/serial',
        }}

        mock_dh = Mock()
        mock_ftp = Mock()
        MockMirrorFullImportParser.rpsl_data_calls = []
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.MirrorFullImportParser', MockMirrorFullImportParser)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.FTP', lambda url: mock_ftp)

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
            'RETR /serial': b'424242',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        MirrorFullImportRunner('TEST').run(mock_dh)

        assert MockMirrorFullImportParser.rpsl_data_calls == ['source1', 'source2']

    def test_missing_source_settings(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {
            'dump_source': 'ftp://host/source1.gz,ftp://host/source2',
        }}

        mock_dh = Mock()
        MirrorFullImportRunner('TEST').run(mock_dh)

    def test_unsupported_protocol(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {
            'dump_source': 'ftp://host/source1.gz,ftp://host/source2',
            'dump_serial_source': 'gopher://host/serial',
        }}

        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            MirrorFullImportRunner('TEST').run(mock_dh)
        assert 'scheme gopher is not supported' in str(ve)


class MockMirrorFullImportParser:
    rpsl_data_calls: List[str] = []

    def __init__(self, source, filename, serial, database_handler):
        with open(filename, 'r') as f:
            self.rpsl_data_calls.append(f.read())
        assert source == 'TEST'
        assert serial == 424242


class TestNRTMUpdateStreamRunner:
    def test_run_import(self, monkeypatch):
        DEFAULT_SETTINGS['sources'] = {'TEST': {
            'nrtm_host': '192.0.2.1',
            'nrtm_port': 43,
        }}

        def mock_whois_query(host, port, query, end_markings) -> str:
            assert host == '192.0.2.1'
            assert port == 43
            assert query == '-g TEST:3:424243-LAST'
            assert 'TEST' in end_markings[0]
            return 'response'

        mock_dh = Mock()
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.NRTMStreamParser', MockNRTMStreamParser)
        monkeypatch.setattr('irrd.mirroring.nrtm_runner.whois_query', mock_whois_query)

        NRTMUpdateStreamRunner('TEST').run(424242, mock_dh)

    def test_missing_source_settings(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {
            'nrtm_host': '192.0.2.1',
        }}

        mock_dh = Mock()
        NRTMUpdateStreamRunner('TEST').run(424242, mock_dh)


class MockNRTMStreamParser(object):
    def __init__(self, source, response, database_handler):
        assert source == 'TEST'
        assert response == 'response'
        self.operations = [Mock()]
