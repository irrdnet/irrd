import time

from irrd.conf import DEFAULT_SETTINGS
from ..scheduler import MirrorScheduler

thread_run_count = 0


class TestMirrorScheduler:
    def test_scheduler(self, monkeypatch):
        global thread_run_count
        thread_run_count = 0

        DEFAULT_SETTINGS['sources'] = {'TEST': {'export_source': 'url'}}
        monkeypatch.setattr("irrd.mirroring.scheduler.MirrorUpdateRunner", MockUpdateRunner)

        scheduler = MirrorScheduler()
        scheduler.run()
        scheduler.run()

        assert thread_run_count == 1


class MockUpdateRunner:
    def __init__(self, source):
        assert source == 'TEST'
        global thread_run_count

    def run(self):
        global thread_run_count
        thread_run_count += 1
        time.sleep(1)
