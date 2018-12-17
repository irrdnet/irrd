from itertools import cycle, repeat

import gzip
from unittest.mock import Mock

from irrd.mirroring.mirror_runners_export import SourceExportRunner
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
                {'object_text': 'object 1 🦄\n'},
                {'object_text': 'object 2 🌈\n'},
            ],
        ])
        mock_dh.execute_query = lambda q: next(responses)

        runner = SourceExportRunner('TEST')
        runner.run()
        runner.run()

        with open(tmpdir + '/TEST.CURRENTSERIAL') as fh:
            assert fh.read() == '424242'

        with gzip.open(tmpdir + '/test.db.gz') as fh:
            assert fh.read().decode('utf-8') == 'object 1 🦄\n\nobject 2 🌈\n\n'

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
