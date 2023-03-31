import datetime
import uuid
from unittest.mock import Mock

from pytz import timezone

from irrd.utils.rpsl_samples import SAMPLE_RTR_SET
from irrd.utils.test_utils import flatten_mock_calls

from ..set_last_modified_auth import set_last_modified


def test_set_last_modified(capsys, monkeypatch, config_override):
    config_override(
        {
            "sources": {
                "TEST": {"authoritative": True},
                "TEST2": {},
            }
        }
    )
    mock_dh = Mock()
    monkeypatch.setattr("irrd.scripts.set_last_modified_auth.DatabaseHandler", lambda: mock_dh)
    mock_dq = Mock()
    monkeypatch.setattr(
        "irrd.scripts.set_last_modified_auth.RPSLDatabaseQuery", lambda column_names, enable_ordering: mock_dq
    )

    object_pk = uuid.uuid4()
    mock_query_result = [
        {
            "pk": object_pk,
            "object_text": SAMPLE_RTR_SET + "last-modified: old\n",
            "updated": datetime.datetime(2020, 1, 1, tzinfo=timezone("UTC")),
        },
    ]
    mock_dh.execute_query = lambda query: mock_query_result

    set_last_modified()

    assert flatten_mock_calls(mock_dq) == [["sources", (["TEST"],), {}]]
    assert mock_dh.mock_calls[0][0] == "execute_statement"
    statement = mock_dh.mock_calls[0][1][0]
    new_text = statement.parameters["object_text"]
    assert new_text == SAMPLE_RTR_SET + "last-modified:  2020-01-01T00:00:00Z\n"

    assert flatten_mock_calls(mock_dh)[1:] == [["commit", (), {}], ["close", (), {}]]
    assert capsys.readouterr().out == "Updating 1 objects in sources ['TEST']\n"
