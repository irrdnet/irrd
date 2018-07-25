from unittest.mock import Mock

from pytest import raises

from irrd.utils.rpsl_samples import SAMPLE_INETNUM, SAMPLE_AS_SET, SAMPLE_PERSON, SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..parser import parse_update_requests
from irrd.updates.parser import UpdateRequestType, UpdateRequestStatus
from irrd.updates.validators import ReferenceValidator


class TestUpdateRequestHandler:

    def test_parse_valid(self):
        pass
