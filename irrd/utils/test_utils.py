import enum
import inspect
from collections import abc
from datetime import datetime
from typing import Any

from irrd.rpsl.parser import RPSLObject
from irrd.storage.database_handler import (
    DatabaseHandler,
    QueryType,
    RPSLDatabaseResponse,
)
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
    _instances: dict[Any, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]


class MockSingletonMeta(Singleton):
    """
    This is a sort of Mock class with some special behaviour to help
    mocking a DatabaseHandler.

    First, it will create a method for each method of DatabaseHandler,
    except for dunder methods and methods already defined.
    Then, on each method call, the call is logged in self.other_calls,
    resolving all arguments to their names, applying defaults,
    and translating a number of arguments to make tests easier.
    """

    def __new__(cls, name, bases, attrs):
        original_class = attrs.pop("DeriveFrom")
        new_class = super().__new__(cls, name, bases, attrs)
        for name, method in inspect.getmembers(original_class, predicate=inspect.isfunction):
            if name not in attrs and not name.startswith("__"):
                defined_method = cls.create_mock_method(method)
                setattr(new_class, name, defined_method)
        return new_class

    @staticmethod
    def create_mock_method(orig_method):
        method_sig = inspect.signature(orig_method)

        def mock_method(self, *args, **kwargs):
            bind = method_sig.bind(self, *args, **kwargs)
            bind.apply_defaults()
            all_args = {}
            for key, value in bind.arguments.items():
                if key == "self":
                    continue
                if isinstance(value, RPSLObject):
                    value = str(value) if value else None
                if isinstance(value, enum.Enum):
                    value = value.name
                if isinstance(value, abc.Iterator):
                    value = list(value)
                all_args[key] = value

            self.other_calls.append((orig_method.__name__, all_args))

        mock_method.__name__ = orig_method.__name__
        return mock_method


class MockDatabaseHandler(metaclass=MockSingletonMeta):
    """
    This mock is a new approach to handle database mocking in unit tests
    and is currently only used in limited tests.
    If extended, it has a lot of potential to improve other tests
    in clarity and debugging - perhaps combined with factoryboy.
    """

    DeriveFrom = DatabaseHandler

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

    def _default_rpsl_database_status_query_iterator(self):
        return iter(
            [
                {
                    "source": "TEST",
                    "created": datetime.utcnow(),
                }
            ]
        )

    def reset_mock(self):
        self.query_responses = {
            RPSLDatabaseJournalQuery: self._default_rpsl_database_journal_query_iterator(),
            DatabaseStatusQuery: self._default_rpsl_database_status_query_iterator(),
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
        else:
            try:
                result = self.query_responses[type(query)]
                if type(result) == list:
                    return iter(result)
                return result
            except KeyError:  # pragma: no cover
                raise ValueError(f"Unknown query in MockDatabaseHandler: {query}")

    def close(self):
        self.closed = True
