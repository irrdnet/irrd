from base64 import b64decode
from typing import List
from unittest.mock import Mock

import pytest

from irrd.utils.test_utils import flatten_mock_calls
from ..mirror_runners import MirrorUpdateRunner, MirrorFullImportRunner, NRTMUpdateStreamRunner


class TestMirrorUpdateRunner:
    def test_full_import_call(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.MirrorFullImportRunner', lambda source: mock_full_import_runner)

        mock_dh.execute_query = lambda q: iter([])
        runner = MirrorUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == 'run'

    def test_force_reload(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.MirrorFullImportRunner', lambda source: mock_full_import_runner)

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': True}])
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

        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.NRTMUpdateStreamRunner', lambda source: mock_stream_runner)

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': False}])
        runner = MirrorUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_stream_runner.mock_calls) == 1
        assert mock_stream_runner.mock_calls[0][0] == 'run'
        assert mock_stream_runner.mock_calls[0][1] == (424242,)

    def test_exception_handling(self, monkeypatch, caplog):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_stream_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.NRTMUpdateStreamRunner', lambda source: mock_stream_runner)
        mock_stream_runner.run = Mock(side_effect=Exception('test-error'))

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': False}])
        runner = MirrorUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert 'An exception occurred while attempting a mirror update or initial import for TEST' in caplog.text
        assert 'test-error' in caplog.text


class TestMirrorFullImportRunner:
    def test_run_import_ftp(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'import_source': ['ftp://host/source1.gz', 'ftp://host/source2'],
                    'import_serial_source': 'ftp://host/serial',
                }
            }
        })

        mock_dh = Mock()
        mock_ftp = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr('irrd.mirroring.mirror_runners.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = 424242

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
            'RETR /serial': b'424242',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        MirrorFullImportRunner('TEST').run(mock_dh)

        assert MockMirrorFileImportParser.rpsl_data_calls == ['source1', 'source2']
        assert flatten_mock_calls(mock_dh) == [
            ['delete_all_rpsl_objects_with_journal', ('TEST',), {}],
            ['disable_journaling', (), {}],
        ]

    def test_run_import_local_file(self, monkeypatch, config_override, tmpdir):
        tmp_import_source1 = tmpdir + '/source1.rpsl'
        with open(tmp_import_source1, 'w') as fh:
            fh.write('source1')
        tmp_import_source2 = tmpdir + '/source2.rpsl'
        with open(tmp_import_source2, 'w') as fh:
            fh.write('source2')
        tmp_import_serial = tmpdir + '/serial'
        with open(tmp_import_serial, 'w') as fh:
            fh.write('424242')

        config_override({
            'sources': {
                'TEST': {
                    'import_source': ['file://' + str(tmp_import_source1), 'file://' + str(tmp_import_source2)],
                    'import_serial_source': 'file://' + str(tmp_import_serial),
                }
            }
        })

        mock_dh = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr('irrd.mirroring.mirror_runners.MirrorFileImportParser', MockMirrorFileImportParser)
        MockMirrorFileImportParser.expected_serial = 424242

        MirrorFullImportRunner('TEST').run(mock_dh)

        assert MockMirrorFileImportParser.rpsl_data_calls == ['source1', 'source2']
        assert flatten_mock_calls(mock_dh) == [
            ['delete_all_rpsl_objects_with_journal', ('TEST',), {}],
            ['disable_journaling', (), {}],
        ]

    def test_no_serial_ftp(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'import_source': ['ftp://host/source1.gz', 'ftp://host/source2'],
                }
            }
        })

        mock_dh = Mock()
        mock_ftp = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr('irrd.mirroring.mirror_runners.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = 0

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        MirrorFullImportRunner('TEST').run(mock_dh)

        assert MockMirrorFileImportParser.rpsl_data_calls == ['source1', 'source2']
        assert flatten_mock_calls(mock_dh) == [
            ['delete_all_rpsl_objects_with_journal', ('TEST',), {}],
            ['disable_journaling', (), {}],
        ]

    def test_missing_source_settings_ftp(self, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'import_serial_source': 'ftp://host/serial',
                }
            }
        })

        mock_dh = Mock()
        MirrorFullImportRunner('TEST').run(mock_dh)
        assert not flatten_mock_calls(mock_dh)

    def test_unsupported_protocol(self, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'import_source': 'ftp://host/source1.gz',
                    'import_serial_source': 'gopher://host/serial',
                }
            }
        })

        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            MirrorFullImportRunner('TEST').run(mock_dh)
        assert 'scheme gopher is not supported' in str(ve)


class MockMirrorFileImportParser:
    rpsl_data_calls: List[str] = []
    expected_serial = 424242

    def __init__(self, source, filename, serial, database_handler):
        with open(filename, 'r') as f:
            self.rpsl_data_calls.append(f.read())
        assert source == 'TEST'
        assert serial == self.expected_serial


class TestNRTMUpdateStreamRunner:
    def test_run_import(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'nrtm_host': '192.0.2.1',
                    'nrtm_port': 43,
                }
            }
        })

        def mock_whois_query(host, port, query, end_markings) -> str:
            assert host == '192.0.2.1'
            assert port == 43
            assert query == '-g TEST:3:424243-LAST'
            assert 'TEST' in end_markings[0]
            return 'response'

        mock_dh = Mock()
        monkeypatch.setattr('irrd.mirroring.mirror_runners.NRTMStreamParser', MockNRTMStreamParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners.whois_query', mock_whois_query)

        NRTMUpdateStreamRunner('TEST').run(424242, mock_dh)

    def test_missing_source_settings(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'nrtm_host': '192.0.2.1',
                }
            }
        })

        mock_dh = Mock()
        NRTMUpdateStreamRunner('TEST').run(424242, mock_dh)


class MockNRTMStreamParser(object):
    def __init__(self, source, response, database_handler):
        assert source == 'TEST'
        assert response == 'response'
        self.operations = [Mock()]
