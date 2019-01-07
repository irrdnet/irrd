import time

from ..scheduler import MirrorScheduler

thread_run_count = 0


class TestMirrorScheduler:
    def test_scheduler_runs_import(self, monkeypatch, config_override):
        global thread_run_count
        thread_run_count = 0

        config_override({
            'sources': {
                'TEST': {
                    'import_source': 'url',
                    'import_timer': 0,
                }
            }
        })

        monkeypatch.setattr("irrd.mirroring.scheduler.MirrorImportUpdateRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        # Second run will not start the thread, as the current one is still running.psql
        scheduler.run()

        assert thread_run_count == 1

    def test_scheduler_import_ignores_timer_not_expired(self, monkeypatch, config_override):
        global thread_run_count
        thread_run_count = 0

        config_override({
            'sources': {
                'TEST': {
                    'import_source': 'url',
                    'import_timer': 100,
                }
            }
        })

        monkeypatch.setattr("irrd.mirroring.scheduler.MirrorImportUpdateRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()
        assert thread_run_count == 1

        # Second run will not start due to timer not expired yet
        time.sleep(0.5)
        scheduler.run()
        assert thread_run_count == 1

    def test_scheduler_runs_export(self, monkeypatch, config_override):
        global thread_run_count
        thread_run_count = 0

        config_override({
            'sources': {
                'TEST': {
                    'export_destination': 'url',
                    'export_timer': 0,
                }
            }
        })

        monkeypatch.setattr("irrd.mirroring.scheduler.SourceExportRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        # Second run will not start the thread, as the current one is still running.psql
        scheduler.run()

        assert thread_run_count == 1

    def test_scheduler_export_ignores_timer_not_expired(self, monkeypatch, config_override):
        global thread_run_count
        thread_run_count = 0

        config_override({
            'sources': {
                'TEST': {
                    'export_destination': 'url',
                    'export_timer': 100,
                }
            }
        })

        monkeypatch.setattr("irrd.mirroring.scheduler.SourceExportRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()
        assert thread_run_count == 1

        # Second run will not start due to timer not expired yet
        time.sleep(0.5)
        scheduler.run()
        assert thread_run_count == 1


class MockRunner:
    run_sleep = True

    def __init__(self, source):
        assert source == 'TEST'
        global thread_run_count

    def run(self):
        global thread_run_count
        thread_run_count += 1
        if self.run_sleep:
            time.sleep(1)
