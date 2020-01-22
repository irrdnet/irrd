from base64 import b64decode
from typing import List
from unittest.mock import Mock

import pytest

from irrd.rpki.parser import BulkRouteRoaValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.test_utils import flatten_mock_calls
from ..mirror_runners_import import RPSLMirrorImportUpdateRunner, RPSLMirrorFullImportRunner, \
    NRTMImportUpdateStreamRunner, ROAImportRunner


class TestRPSLMirrorImportUpdateRunner:
    def test_full_import_call(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner', lambda source: mock_full_import_runner)

        mock_dh.execute_query = lambda q: iter([])
        runner = RPSLMirrorImportUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == 'run'

    def test_force_reload(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'nrtm_host': '192.0.2.1',
                }
            }
        })
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner', lambda source: mock_full_import_runner)

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': True}])
        runner = RPSLMirrorImportUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == 'run'

    def test_update_stream_call(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'nrtm_host': '192.0.2.1',
                }
            }
        })
        mock_dh = Mock()
        mock_dq = Mock()
        mock_stream_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.NRTMImportUpdateStreamRunner', lambda source: mock_stream_runner)

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': False}])
        runner = RPSLMirrorImportUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dq) == [['source', ('TEST',), {}]]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}], ['close', (), {}]]

        assert len(mock_stream_runner.mock_calls) == 1
        assert mock_stream_runner.mock_calls[0][0] == 'run'
        assert mock_stream_runner.mock_calls[0][1] == (424242,)

    def test_io_exception_handling(self, monkeypatch, caplog):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner', lambda source: mock_full_import_runner)
        mock_full_import_runner.run = Mock(side_effect=ConnectionResetError('test-error'))

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': False}])
        runner = RPSLMirrorImportUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert 'An error occurred while attempting a mirror update or initial import for TEST' in caplog.text
        assert 'test-error' in caplog.text
        assert 'Traceback' not in caplog.text

    def test_unexpected_exception_handling(self, monkeypatch, caplog):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseStatusQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner', lambda source: mock_full_import_runner)
        mock_full_import_runner.run = Mock(side_effect=Exception('test-error'))

        mock_dh.execute_query = lambda q: iter([{'serial_newest_seen': 424242, 'force_reload': False}])
        runner = RPSLMirrorImportUpdateRunner(source='TEST')
        runner.run()

        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert 'An exception occurred while attempting a mirror update or initial import for TEST' in caplog.text
        assert 'test-error' in caplog.text
        assert 'Traceback' in caplog.text


class TestRPSLMirrorFullImportRunner:
    def test_run_import_ftp(self, monkeypatch, config_override):
        config_override({
            'rpki': {'roa_source': 'https://example.com/roa.json'},
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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = 424242

        mock_bulk_validator_init = Mock()
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.BulkRouteRoaValidator', mock_bulk_validator_init)

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
            'RETR /serial': b'424242',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        RPSLMirrorFullImportRunner('TEST').run(mock_dh, serial_newest_seen=424241)

        assert MockMirrorFileImportParser.rpsl_data_calls == ['source1', 'source2']
        assert flatten_mock_calls(mock_dh) == [
            ['delete_all_rpsl_objects_with_journal', ('TEST',), {}],
            ['disable_journaling', (), {}],
        ]
        assert mock_bulk_validator_init.mock_calls[0][1][0] == mock_dh

    def test_run_import_local_file(self, monkeypatch, config_override, tmpdir):
        tmp_import_source1 = tmpdir + '/source1.rpsl.gz'
        with open(tmp_import_source1, 'wb') as fh:
            # gzipped data, contains 'source1'
            fh.write(b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'))
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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.MirrorFileImportParser', MockMirrorFileImportParser)
        MockMirrorFileImportParser.expected_serial = 424242

        RPSLMirrorFullImportRunner('TEST').run(mock_dh)

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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = None

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        RPSLMirrorFullImportRunner('TEST').run(mock_dh, serial_newest_seen=42)

        assert MockMirrorFileImportParser.rpsl_data_calls == ['source1', 'source2']
        assert flatten_mock_calls(mock_dh) == [
            ['delete_all_rpsl_objects_with_journal', ('TEST',), {}],
            ['disable_journaling', (), {}],
        ]

    def test_import_cancelled_serial_too_old(self, monkeypatch, config_override, caplog):
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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = 424242

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
            'RETR /serial': b'424242',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        RPSLMirrorFullImportRunner('TEST').run(mock_dh, serial_newest_seen=424243)

        assert not MockMirrorFileImportParser.rpsl_data_calls
        assert flatten_mock_calls(mock_dh) == []
        assert 'Current newest serial seen for TEST is 424243, import_serial is 424242, cancelling import.'

    def test_import_force_reload_with_serial_too_old(self, monkeypatch, config_override):
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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.MirrorFileImportParser', MockMirrorFileImportParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.FTP', lambda url: mock_ftp)
        MockMirrorFileImportParser.expected_serial = 424242

        responses = {
            # gzipped data, contains 'source1'
            'RETR /source1.gz': b64decode('H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA'),
            'RETR /source2': b'source2',
            'RETR /serial': b'424242',
        }
        mock_ftp.retrbinary = lambda path, callback: callback(responses[path])
        RPSLMirrorFullImportRunner('TEST').run(mock_dh, serial_newest_seen=424243, force_reload=True)

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
        RPSLMirrorFullImportRunner('TEST').run(mock_dh)
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
            RPSLMirrorFullImportRunner('TEST').run(mock_dh)
        assert 'scheme gopher is not supported' in str(ve.value)


class MockMirrorFileImportParser:
    rpsl_data_calls: List[str] = []
    expected_serial = 424242

    def __init__(self, source, filename, serial, database_handler, direct_error_return=False, roa_validator=None):
        self.filename = filename
        assert source == 'TEST'
        assert serial == self.expected_serial

    def run_import(self):
        with open(self.filename, 'r') as f:
            self.rpsl_data_calls.append(f.read())


class TestROAImportRunner:
    # As the code for retrieving files from HTTP, FTP or local file
    # is shared between ROAImportRunner and RPSLMirrorFullImportRunner,
    # not all protocols are tested here.
    def test_run_import_http_file_success(self, monkeypatch, config_override, tmpdir):
        config_override({
            'rpki': {
                'roa_source': 'https://host/roa.json',
            }
        })

        class MockRequestsSuccess:
            status_code = 200

            def __init__(self, url, stream):
                assert url == 'https://host/roa.json'
                assert stream

            def iter_content(self, size):
                return iter([b'roa_', b'data'])

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.ROADataImporter', MockROADataImporter)
        mock_bulk_validator = Mock(spec=BulkRouteRoaValidator)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.BulkRouteRoaValidator', lambda dh, roas: mock_bulk_validator)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.requests.get', MockRequestsSuccess)

        mock_bulk_validator.validate_all_routes = lambda: ({'pk_valid1', 'pk_valid2'}, {'pk_invalid1', 'pk_invalid2'})
        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            ['disable_journaling', (), {}],
            ['delete_all_roa_objects', (), {}],
            ['delete_all_rpsl_objects_with_journal', ('RPKI',), {}],
            ['commit', (), {}],
            ['update_rpki_status', (), {'rpsl_pks_invalid': {'pk_invalid1', 'pk_invalid2'}}],
            ['commit', (), {}],
            ['close', (), {}]
        ]

    def test_run_import_http_file_failed_download(self, monkeypatch, config_override, tmpdir, caplog):
        config_override({
            'rpki': {
                'roa_source': 'https://host/roa.json',
            }
        })

        class MockRequestsSuccess:
            status_code = 500
            content = 'expected-test-error'

            def __init__(self, url, stream):
                assert url == 'https://host/roa.json'
                assert stream

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.requests.get', MockRequestsSuccess)

        ROAImportRunner().run()
        assert 'Failed to download https://host/roa.json: 500: expected-test-error' in caplog.text

    def test_exception_handling(self, monkeypatch, config_override, tmpdir, caplog):
        tmp_roa_source = tmpdir + '/roa.json'
        with open(tmp_roa_source, 'wb') as fh:
            fh.write(b'roa_data')
        config_override({
            'rpki': {
                'roa_source': 'file://' + str(tmp_roa_source),
            }
        })

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        mock_importer = Mock(side_effect=ValueError('expected-test-error'))
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.ROADataImporter', mock_importer)

        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            ['disable_journaling', (), {}],
            ['delete_all_roa_objects', (), {}],
            ['delete_all_rpsl_objects_with_journal', ('RPKI',), {}],
            ['close', (), {}]
        ]

        assert 'expected-test-error' in caplog.text

    def test_file_error_handling(self, monkeypatch, config_override, tmpdir, caplog):
        tmp_roa_source = tmpdir + '/roa.json'
        config_override({
            'rpki': {
                'roa_source': 'file://' + str(tmp_roa_source),
            }
        })

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.DatabaseHandler', lambda: mock_dh)
        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            ['disable_journaling', (), {}],
            ['delete_all_roa_objects', (), {}],
            ['delete_all_rpsl_objects_with_journal', ('RPKI',), {}],
            ['close', (), {}]
        ]

        assert 'No such file or directory' in caplog.text


class MockROADataImporter:
    def __init__(self, text: str, database_handler: DatabaseHandler):
        assert text == 'roa_data'
        self.roa_objs = ['roa1', 'roa2']


class TestNRTMImportUpdateStreamRunner:
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
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.NRTMStreamParser', MockNRTMStreamParser)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_import.whois_query', mock_whois_query)

        NRTMImportUpdateStreamRunner('TEST').run(424242, mock_dh)

    def test_missing_source_settings(self, monkeypatch, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'nrtm_port': '4343',
                }
            }
        })

        mock_dh = Mock()
        NRTMImportUpdateStreamRunner('TEST').run(424242, mock_dh)


class MockNRTMStreamParser(object):
    def __init__(self, source, response, database_handler):
        assert source == 'TEST'
        assert response == 'response'
        self.operations = [Mock()]
