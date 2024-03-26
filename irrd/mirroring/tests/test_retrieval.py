# These tests are very limited, as most retrieval behaviour
# is tested in test_parsers. In the past, the retrieval code was part
# of the parsers. These tests should be split up.
from tempfile import NamedTemporaryFile

import pytest

from irrd.mirroring.retrieval import check_file_hash_sha256


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
