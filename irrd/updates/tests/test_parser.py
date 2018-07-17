from irrd.utils.rpsl_samples import SAMPLE_INETNUM, SAMPLE_AS_SET
from irrd.updates.parser import UpdateRequestParser, UpdateRequestStatus


class TestUpdateRequestParser:
    def test_parse_valid(self):
        parser = UpdateRequestParser()
        unknown_class = 'unknown-object: foo\n'
        invalid_object = 'aut-num: pw1\n'

        input_data = 'password: pw1\n' + SAMPLE_INETNUM + 'delete: delete\n\r\n\r\n\r\n'
        input_data += SAMPLE_AS_SET + 'password: pw2\n\n'
        input_data += 'password: pw3\n' + unknown_class + '\r\n'
        input_data += invalid_object + '\noverride: override-pw'

        result_inetnum, result_as_set, result_unknown, result_invalid = parser.parse(input_data)

        assert result_inetnum.status == UpdateRequestStatus.PROCESSING
        assert result_inetnum.rpsl_text.startswith('inetnum:')
        assert result_inetnum.rpsl_obj.rpsl_object_class == 'inetnum'
        assert result_inetnum.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert result_inetnum.delete_request
        assert len(result_inetnum.info_messages) == 1
        assert 'reformatted as' in result_inetnum.info_messages[0]
        assert not result_inetnum.error_messages

        assert result_as_set.status == UpdateRequestStatus.PROCESSING
        assert result_as_set.rpsl_text.startswith('as-set:')
        assert result_as_set.rpsl_obj.rpsl_object_class == 'as-set'
        assert result_as_set.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert not result_as_set.delete_request
        assert not result_as_set.info_messages
        assert not result_as_set.error_messages

        assert result_unknown.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert result_unknown.rpsl_text.startswith('unknown-object:')
        assert not result_unknown.rpsl_obj
        assert result_unknown.passwords == ['pw1', 'pw2', 'pw3']
        assert result_unknown.overrides == ['override-pw']
        assert not result_unknown.delete_request
        assert not result_unknown.info_messages
        assert len(result_unknown.error_messages) == 1
        assert 'unknown object class' in result_unknown.error_messages[0]

        assert result_invalid.status == UpdateRequestStatus.ERROR_PARSING
        assert result_invalid.rpsl_text.startswith('aut-num:')
        assert result_invalid.rpsl_obj.rpsl_object_class == 'aut-num'
        assert result_invalid.passwords == ['pw1', 'pw2', 'pw3']
        assert result_invalid.overrides == ['override-pw']
        assert not result_invalid.delete_request
        assert not result_invalid.info_messages
        assert len(result_invalid.error_messages) == 6
        assert 'Mandatory attribute' in result_invalid.error_messages[0]
