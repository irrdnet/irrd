from ..rpsl_parse import main

# First an entirely valid object with an as-block that should be reformatted,
# then an object with an extra unkown attributes,
# then an entirely unknown object.
TEST_DATA = """# TEST
% TEST

as-block:       AS2043 - as02043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
changed:        2014-02-24T13:15:13Z
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE

as-block:       AS2043 - as02043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
changed:        2014-02-24T13:15:13Z
tech-c:         DUMY-RIPE
unknown-obj:    unknown value should be caught in strict validation
admin-c:        DUMY-RIPE
source:         RIPE

foo-block:       AS2043 - as02043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
changed:        2014-02-24T13:15:13Z
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE


"""


def test_rpsl_parse(capsys, tmpdir):
    tmp_file = tmpdir + "/rpsl_parse_test.rpsl"
    fh = open(tmp_file, "w")
    fh.write(TEST_DATA)
    fh.close()

    main(filename=tmp_file, strict_validation=True)
    captured = capsys.readouterr().out
    assert "ERROR: Unrecognised attribute unknown-obj on object as-block" in captured
    assert "INFO: AS range AS2043 - as02043 was reformatted as AS2043 - AS2043" in captured
    assert "Processed 3 objects, 1 with errors" in captured
    assert "Ignored 1 objects due to unknown object classes: foo-block" in captured

    main(filename=tmp_file, strict_validation=False)
    captured = capsys.readouterr().out
    print(captured)
    assert "ERROR: Unrecognised attribute unknown-obj on object as-block" not in captured
    assert "INFO: AS range AS2043 - as02043 was reformatted as AS2043 - AS2043" in captured
    assert "Processed 3 objects, 0 with errors" in captured
    assert "Ignored 1 objects due to unknown object classes: foo-block" in captured
