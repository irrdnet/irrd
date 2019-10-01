import os
from itertools import cycle, repeat

import gzip
from unittest.mock import Mock

from irrd.mirroring.mirror_runners_export import SourceExportRunner, EXPORT_PERMISSIONS
from irrd.utils.test_utils import flatten_mock_calls


class TestSourceExportRunner:
    def test_export(self, tmpdir, config_override, monkeypatch, caplog):
        config_override({
            'sources': {
                'TEST': {
                    'export_destination': str(tmpdir),
                }
            }
        })

        mock_dh = Mock()
        mock_dq = Mock()
        mock_dsq = Mock()

        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseStatusQuery', lambda: mock_dsq)

        responses = cycle([
            repeat({'serial_newest_seen': '424242'}),
            [
                # The CRYPT-PW hash must not appear in the output
                {'object_text': 'object 1 🦄\nauth: CRYPT-PW foobar\n'},
                {'object_text': 'object 2 🌈\n'},
            ],
        ])
        mock_dh.execute_query = lambda q: next(responses)

        runner = SourceExportRunner('TEST')
        runner.run()
        runner.run()

        serial_filename = tmpdir + '/TEST.CURRENTSERIAL'
        assert oct(os.lstat(serial_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with open(serial_filename) as fh:
            assert fh.read() == '424242'

        export_filename = tmpdir + '/test.db.gz'
        assert oct(os.lstat(export_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with gzip.open(export_filename) as fh:
            assert fh.read().decode('utf-8') == 'object 1 🦄\nauth: CRYPT-PW DummyValue  # Filtered for security\n\n' \
                                                'object 2 🌈\n\n'

        assert flatten_mock_calls(mock_dh) == [
            ['record_serial_exported', ('TEST', '424242'), {}],
            ['commit', (), {}],
            ['close', (), {}],
            ['record_serial_exported', ('TEST', '424242'), {}],
            ['commit', (), {}],
            ['close', (), {}]
        ]
        assert 'Starting a source export for TEST' in caplog.text
        assert 'Export for TEST complete, ' in caplog.text

    def test_failure(self, tmpdir, config_override, monkeypatch, caplog):
        config_override({
            'sources': {
                'TEST': {
                    'export_destination': str(tmpdir),
                }
            }
        })

        mock_dh = Mock()
        mock_dsq = Mock()
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseStatusQuery', lambda: mock_dsq)
        mock_dh.execute_query = Mock(side_effect=ValueError('expected-test-error'))

        runner = SourceExportRunner('TEST')
        runner.run()

        assert 'An exception occurred while attempting to run an export for TEST' in caplog.text
        assert 'expected-test-error' in caplog.text

    def test_no_status(self, tmpdir, config_override, monkeypatch, caplog):
        config_override({
            'sources': {
                'TEST': {
                    'export_destination': str(tmpdir),
                }
            }
        })

        mock_dh = Mock()
        mock_dsq = Mock()
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseHandler', lambda: mock_dh)
        monkeypatch.setattr('irrd.mirroring.mirror_runners_export.DatabaseStatusQuery', lambda: mock_dsq)
        mock_dh.execute_query = Mock(side_effect=StopIteration())

        runner = SourceExportRunner('TEST')
        runner.run()

        assert 'Unable to run export for TEST, internal database status is empty.' in caplog.text
