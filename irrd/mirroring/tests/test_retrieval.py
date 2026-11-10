import gzip
from functools import partial
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from irrd.mirroring.retrieval import check_file_hash_sha256, retrieve_file


@pytest.fixture()
def tmp_download_dir(monkeypatch, tmp_path):
    """Keep the temporary files of retrievals in their own directory, so leftovers show up."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    monkeypatch.setattr(
        "irrd.mirroring.retrieval.NamedTemporaryFile", partial(NamedTemporaryFile, dir=download_dir)
    )
    return download_dir


def _mock_download(monkeypatch, content: bytes):
    monkeypatch.setattr(
        "irrd.mirroring.retrieval._download_file",
        lambda destination, url, url_parsed: destination.write(content),
    )


def test_download_unlinks_temporary_file_on_invalid_hash(monkeypatch, tmp_download_dir):
    _mock_download(monkeypatch, b"test")
    with pytest.raises(ValueError):
        retrieve_file("https://example.com/source", return_contents=False, expected_hash="9f")
    assert not list(tmp_download_dir.iterdir())


def test_download_unlinks_temporary_files_on_invalid_gzip(monkeypatch, tmp_download_dir):
    _mock_download(monkeypatch, b"not gzipped")
    with pytest.raises(gzip.BadGzipFile):
        retrieve_file("https://example.com/source.gz", return_contents=False)
    assert not list(tmp_download_dir.iterdir())


def test_download_gz_removes_the_compressed_file(monkeypatch, tmp_download_dir):
    _mock_download(monkeypatch, gzip.compress(b"payload"))
    path, _ = retrieve_file("https://example.com/source.gz", return_contents=False)
    assert [p.name for p in tmp_download_dir.iterdir()] == [Path(path).name]


def test_local_unlinks_temporary_file_on_invalid_gzip(tmp_path, tmp_download_dir):
    source = tmp_path / "source.gz"
    source.write_bytes(b"not gzipped")
    with pytest.raises(gzip.BadGzipFile):
        retrieve_file(f"file://{source}", return_contents=False)
    assert not list(tmp_download_dir.iterdir())
    assert source.exists()


def test_check_expected_hash(tmp_path):
    f = NamedTemporaryFile(delete=False, dir=tmp_path)
    f.write(b"test")
    f.close()

    check_file_hash_sha256(f.name, expected_hash=None)
    check_file_hash_sha256(
        f.name, expected_hash="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    )
    with pytest.raises(ValueError):
        check_file_hash_sha256(f.name, expected_hash="9f")


def test_hash_not_supported_with_contents():
    with pytest.raises(ValueError):
        retrieve_file("https://example.com/file", return_contents=True, expected_hash="9f")
