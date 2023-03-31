import threading
import time

from ..scheduler import MAX_SIMULTANEOUS_RUNS, MirrorScheduler, ScheduledTaskProcess

thread_run_count = 0


class TestMirrorScheduler:
    def test_scheduler_database_readonly(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "database_readonly": True,
                "sources": {
                    "TEST": {
                        "import_source": "url",
                        "import_timer": 0,
                    }
                },
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.RPSLMirrorImportUpdateRunner", MockRunner)
        scheduler = MirrorScheduler()
        scheduler.run()
        assert thread_run_count == 0

    def test_scheduler_runs_rpsl_import(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_source": "url",
                        "import_timer": 0,
                    }
                }
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.RPSLMirrorImportUpdateRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        # Second run will not start the thread, as the current one is still running
        time.sleep(0.5)
        scheduler.run()

        time.sleep(0.5)
        assert thread_run_count == 1

        # update_process_state() should clean up the status,
        # but only once the thread has completed
        scheduler.update_process_state()
        time.sleep(0.5)
        assert len(scheduler.processes.items()) == 1
        scheduler.update_process_state()
        assert len(scheduler.processes.items()) == 0

    def test_scheduler_limits_simultaneous_runs(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_source": "url",
                        "import_timer": 0,
                    },
                    "TEST2": {
                        "import_source": "url",
                        "import_timer": 0,
                    },
                    "TEST3": {
                        "import_source": "url",
                        "import_timer": 0,
                    },
                    "TEST4": {
                        "import_source": "url",
                        "import_timer": 0,
                    },
                }
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.RPSLMirrorImportUpdateRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()

        time.sleep(0.5)
        assert thread_run_count == MAX_SIMULTANEOUS_RUNS

    def test_scheduler_runs_roa_import(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override({"rpki": {"roa_source": "https://example.com/roa.json"}})

        monkeypatch.setattr("irrd.mirroring.scheduler.ROAImportRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        # Second run will not start the thread, as the current one is still running
        time.sleep(0.5)
        scheduler.run()

        assert thread_run_count == 1

    def test_scheduler_runs_scopefilter(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "rpki": {"roa_source": None},
                "scopefilter": {
                    "prefixes": ["192.0.2.0/24"],
                },
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.ScopeFilterUpdateRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()

        # Second run will not start the thread, as the config hasn't changed
        config_override(
            {
                "rpki": {"roa_source": None},
                "scopefilter": {
                    "prefixes": ["192.0.2.0/24"],
                },
            }
        )
        scheduler.run()
        time.sleep(0.2)
        assert thread_run_count == 1

        config_override(
            {
                "rpki": {"roa_source": None},
                "scopefilter": {
                    "asns": [23456],
                },
            }
        )

        # Should run now, because config has changed
        scheduler.update_process_state()
        scheduler.run()
        time.sleep(0.2)
        assert thread_run_count == 2

        config_override(
            {
                "rpki": {"roa_source": None},
                "scopefilter": {
                    "asns": [23456],
                },
                "sources": {"TEST": {"scopefilter_excluded": True}},
            }
        )

        # Should run again, because exclusions have changed
        scheduler.update_process_state()
        scheduler.run()
        time.sleep(0.2)
        assert thread_run_count == 3

    def test_scheduler_runs_route_preference(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "rpki": {"roa_source": None},
                "sources": {
                    "TEST": {"route_object_preference": 200},
                },
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.RoutePreferenceUpdateRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        # Second run will not start the thread, as the current one is still running
        time.sleep(0.5)
        scheduler.run()

        assert thread_run_count == 1

    def test_scheduler_import_ignores_timer_not_expired(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_source": "url",
                        "import_timer": 100,
                    }
                }
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.RPSLMirrorImportUpdateRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()
        time.sleep(0.5)
        assert thread_run_count == 1

        # Second run will not start due to timer not expired yet
        time.sleep(0.5)
        scheduler.run()
        assert thread_run_count == 1

    def test_scheduler_runs_export(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination": "url",
                        "export_timer": 0,
                    }
                }
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.SourceExportRunner", MockRunner)
        MockRunner.run_sleep = True

        scheduler = MirrorScheduler()
        scheduler.run()
        time.sleep(0.5)
        # Second run will not start the thread, as the current one is still running
        scheduler.run()

        assert thread_run_count == 1

    def test_scheduler_export_ignores_timer_not_expired(self, monkeypatch, config_override):
        monkeypatch.setattr("irrd.mirroring.scheduler.ScheduledTaskProcess", MockScheduledTaskProcess)
        global thread_run_count
        thread_run_count = 0

        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination": "url",
                        "export_timer": 100,
                    }
                }
            }
        )

        monkeypatch.setattr("irrd.mirroring.scheduler.SourceExportRunner", MockRunner)
        MockRunner.run_sleep = False

        scheduler = MirrorScheduler()
        scheduler.run()
        time.sleep(0.5)
        assert thread_run_count == 1

        # Second run will not start due to timer not expired yet
        scheduler.run()
        time.sleep(0.5)
        assert thread_run_count == 1


class TestScheduledTaskProcess:
    def test_task(self):
        global thread_run_count
        thread_run_count = 0
        MockRunner.run_sleep = True
        ScheduledTaskProcess(runner=MockRunner("TEST"), name="test").run()
        assert thread_run_count == 1


class MockRunner:
    run_sleep = True

    def __init__(self, source):
        assert source in ["TEST", "TEST2", "TEST3", "TEST4", "RPKI", "scopefilter", "routepref"]

    def run(self):
        global thread_run_count
        thread_run_count += 1
        if self.run_sleep:
            time.sleep(1.5)


class MockScheduledTaskProcess(threading.Thread):
    def __init__(self, runner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runner = runner

    def run(self):
        self.runner.run()

    def close(self):
        pass  # process have close(), threads do not
