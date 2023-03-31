from unittest.mock import Mock

from ..rpsl_read import RPSLParse

# First an entirely valid object with an as-block that should be reformatted,
# then an object with an extra unkown attributes,
# then an entirely unknown object.
TEST_DATA = """# TEST
% TEST

as-block:       AS65536 - as065538
descr:          TEST ASN block
remarks:        test remark
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
source:         TEST

as-block:       AS65536 - as065538
descr:          TEST ASN block
remarks:        test remark
mnt-by:         TEST-MNT
unknown-obj:    unknown value should be caught in strict validation
changed:        changed@example.com 20190701 # comment
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
source:         TEST

foo-block:       AS65536 - as065538
descr:          TEST ASN block
remarks:        test remark
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
source:         TEST
remarks:        remark

"""


def test_rpsl_read(capsys, tmpdir, monkeypatch):
    mock_database_handler = Mock()
    monkeypatch.setattr("irrd.scripts.rpsl_read.DatabaseHandler", lambda: mock_database_handler)

    tmp_file = tmpdir + "/rpsl_parse_test.rpsl"
    fh = open(tmp_file, "w")
    fh.write(TEST_DATA)
    fh.close()

    RPSLParse().main(filename=tmp_file, strict_validation=True, database=True)
    captured = capsys.readouterr().out
    assert "ERROR: Unrecognised attribute unknown-obj on object as-block" in captured
    assert "INFO: AS range AS65536 - as065538 was reformatted as AS65536 - AS65538" in captured
    assert "Processed 3 objects, 1 with errors" in captured
    assert "Ignored 1 objects due to unknown object classes: foo-block" in captured

    assert mock_database_handler.mock_calls[0][0] == "disable_journaling"
    assert mock_database_handler.mock_calls[1][0] == "upsert_rpsl_object"
    assert mock_database_handler.mock_calls[1][1][0].pk() == "AS65536 - AS65538"
    assert mock_database_handler.mock_calls[2][0] == "commit"
    mock_database_handler.reset_mock()

    RPSLParse().main(filename=tmp_file, strict_validation=False, database=True)
    captured = capsys.readouterr().out
    assert "ERROR: Unrecognised attribute unknown-obj on object as-block" not in captured
    assert "INFO: AS range AS65536 - as065538 was reformatted as AS65536 - AS65538" in captured
    assert "Processed 3 objects, 0 with errors" in captured
    assert "Ignored 1 objects due to unknown object classes: foo-block" in captured

    assert mock_database_handler.mock_calls[0][0] == "disable_journaling"
    assert mock_database_handler.mock_calls[1][0] == "upsert_rpsl_object"
    assert mock_database_handler.mock_calls[1][1][0].pk() == "AS65536 - AS65538"
    assert mock_database_handler.mock_calls[2][0] == "upsert_rpsl_object"
    assert mock_database_handler.mock_calls[2][1][0].pk() == "AS65536 - AS65538"
    assert mock_database_handler.mock_calls[3][0] == "commit"
    mock_database_handler.reset_mock()

    RPSLParse().main(filename=tmp_file, strict_validation=False, database=False)
    assert not mock_database_handler.mock_calls
