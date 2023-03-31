from datetime import datetime
from typing import Any, Dict, Iterable

from irrd.storage.database_handler import QueryType, RPSLDatabaseResponse
from irrd.storage.models import DatabaseOperation, JournalEntryOrigin
from irrd.storage.queries import (
    DatabaseStatusQuery,
    RPSLDatabaseJournalQuery,
    RPSLDatabaseJournalStatisticsQuery,
)
from irrd.utils.rpsl_samples import SAMPLE_MNTNER


def flatten_mock_calls(mock, flatten_objects=False):
    """
    Flatten the calls performed on a particular mock object,
    into a list of calls with arguments.

    If flatten_objects is set to True, objects of classes not in
    retained_classes are converted to strings.
    """
    result = []
    retained_classes = (int, list, tuple, set, bytes, bytearray)

    for call in mock.mock_calls:
        call = list(call)
        call_name = call[0]
        if "." in str(call_name):
            call_name = str(call_name).split(".")[-1]
        if flatten_objects:
            args = tuple([str(a) if not isinstance(a, retained_classes) else a for a in call[1]])
        else:
            args = call[1]
        kwargs = call[2]
        result.append([call_name, args, kwargs])
    return result


class Singleton(type):
    _instances: Dict[Any, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]


class MockDatabaseHandler(metaclass=Singleton):
    """
    This mock is a new approach to handle database mocking in unit tests
    and is currently only used in the HTTP event stream tests.
    If extended, it has a lot of potential to improve other tests
    in clarity and debugging - perhaps combined with factoryboy.
    """

    def _default_rpsl_database_journal_query_iterator(self):
        yield {
            "rpsl_pk": "TEST-MNT",
            "source": "TEST",
            "operation": DatabaseOperation.add_or_update,
            "object_class": "mntner",
            "serial_global": self.serial_global,
            "serial_nrtm": self.serial_nrtm,
            "origin": JournalEntryOrigin.auth_change,
            "timestamp": datetime.utcnow(),
            "object_text": SAMPLE_MNTNER,
        }

    def reset_mock(self):
        self.query_responses = {
            RPSLDatabaseJournalQuery: self._default_rpsl_database_journal_query_iterator()
        }
        self.queries = []
        self.other_calls = []

    @classmethod
    async def create_async(cls, readonly=False):
        return cls(readonly=readonly)

    def __init__(self, readonly=False):
        self._connection = None
        self.closed = False
        self.readonly = readonly
        self.serial_global = 0
        self.serial_nrtm = 0

    async def execute_query_async(
        self, query: QueryType, flush_rpsl_buffer=True, refresh_on_error=False
    ) -> RPSLDatabaseResponse:
        return self.execute_query(query, flush_rpsl_buffer, refresh_on_error)

    def execute_query(
        self, query: QueryType, flush_rpsl_buffer=True, refresh_on_error=False
    ) -> RPSLDatabaseResponse:
        self.serial_nrtm += 1
        self.serial_global += 2
        self.queries.append(query)

        if type(query) == RPSLDatabaseJournalStatisticsQuery:
            return iter(
                [
                    {
                        "max_timestamp": datetime.utcnow(),
                        "max_serial_global": 42,
                    }
                ]
            )
        elif type(query) == DatabaseStatusQuery:
            return iter(
                [
                    {
                        "source": "TEST",
                        "created": datetime.utcnow(),
                    }
                ]
            )
        else:
            try:
                return self.query_responses[type(query)]
            except KeyError:  # pragma: no cover
                raise ValueError(f"Unknown query in MockDatabaseHandler: {query}")

    def update_route_preference_status(
        self,
        rpsl_objs_now_visible: Iterable[Dict[str, Any]] = [],
        rpsl_objs_now_suppressed: Iterable[Dict[str, Any]] = [],
    ) -> None:
        self.other_calls.append(
            (
                "update_route_preference_status",
                {
                    "rpsl_objs_now_visible": list(rpsl_objs_now_visible),
                    "rpsl_objs_now_suppressed": list(rpsl_objs_now_suppressed),
                },
            )
        )

    def delete_journal_entries_before_date(self, timestamp: datetime, source: str):
        self.other_calls.append(
            (
                "delete_journal_entries_before_date",
                {"timestamp": timestamp, "source": source},
            )
        )

    def commit(self):
        self.other_calls.append(("commit", {}))

    def close(self):
        self.closed = True
