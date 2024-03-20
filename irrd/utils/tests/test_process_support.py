from pathlib import Path

from irrd.utils.process_support import get_lockfile


def test_get_lockfile_blocking(tmpdir):
    lockfile_path = Path(tmpdir) / "lockfile"
    file_handle = get_lockfile(lockfile_path, blocking=True)
    assert file_handle is not None
    file_handle.close()


def test_get_lockfile_non_blocking(tmpdir):
    lockfile_path = Path(tmpdir) / "lockfile"
    file_handle = get_lockfile(lockfile_path, blocking=False)
    assert file_handle is not None
    file_handle.close()


def test_get_lockfile_failed_lock(tmpdir, monkeypatch):
    def mock_lockf(fd, operation):
        raise OSError

    lockfile_path = Path(tmpdir) / "lockfile"
    monkeypatch.setattr("irrd.utils.process_support.fcntl.lockf", mock_lockf)
    file_handle = get_lockfile(lockfile_path, blocking=False)
    assert file_handle is None
