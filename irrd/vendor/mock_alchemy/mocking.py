"""A module for basic mocking of SQLAlchemy sessions and calls."""
from __future__ import absolute_import, print_function, unicode_literals

from functools import partial
from itertools import chain, takewhile
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    overload,
)
from unittest import mock

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from .comparison import ExpressionMatcher
from .utils import (
    build_identity_map,
    copy_and_update,
    get_item_attr,
    get_scalar,
    indexof,
    raiser,
    setattr_tmp,
)

Call = type(mock.call)


class UnorderedTuple(tuple):
    """Same as tuple except in comparison order does not matter.

    A tuple in which order does not matter for equality. It compares
    by remove elements from the other tuple.

    For example::

        >>> UnorderedTuple((1, 2, 3)) == (3, 2, 1)
        True
    """

    def __eq__(self, other: tuple) -> bool:
        """Compares another tuple for equality."""
        if len(self) != len(other):
            return False

        other = list(other)
        for i in self:
            try:
                other.remove(i)
            except ValueError:
                return False

        return True


class UnorderedCall(Call):
    """Same as Call except in comparison order of parameters does not matter.

    A ``mock.Call`` subclass that ensures that eqaulity does not depend on order.
    This isued to check if SQLAlchemy calls match up regardless of order. For example,
    this is useful in the case of filtering when ``.filter(y == 4).filter(y == 2)``
    is the same as ``.filter(y == 2).filter(y == 4)``.

    For example::

        >>> a = ((1, 2, 3), {'hello': 'world'})
        >>> b = ((3, 2, 1), {'hello': 'world'})
        >>> UnorderedCall(a) == Call(b)
        True
    """

    def __eq__(self, other: Call) -> bool:
        """Compares another call for equality."""
        _other = list(other)
        _other[-2] = UnorderedTuple(other[-2])
        other = Call(
            tuple(_other),
            **{k.replace("_mock_", ""): v for k, v in vars(other).items()},
        )

        return super(UnorderedCall, self).__eq__(other)


def sqlalchemy_call(call: Call, with_name: bool = False, base_call: Any = Call) -> Any:
    """Convert ``mock.call()`` into call.

    Convert ``mock.call()`` into call with all parameters
    wrapped with ``ExpressionMatcher``. This is useful for comparing
    SQLAlchemy statements for equality.

    Args:
        call: The call to convert.
        with_name: Whether to convert the name of the call.
        base_call: The type of call to convert into.

    Returns:
        Returns the converted call of the type ``base_call``.

    For example::

        >>> args, kwargs = sqlalchemy_call(mock.call(5, foo='bar'))
        >>> isinstance(args[0], ExpressionMatcher)
        True
        >>> isinstance(kwargs['foo'], ExpressionMatcher)
        True
    """
    try:
        args, kwargs = call
    except ValueError:
        name, args, kwargs = call
    else:
        name = ""

    args = tuple([ExpressionMatcher(i) for i in args])
    kwargs = {k: ExpressionMatcher(v) for k, v in kwargs.items()}

    if with_name:
        return base_call((name, args, kwargs))
    else:
        return base_call((args, kwargs), two=True)


class AlchemyMagicMock(mock.MagicMock):
    """Compares SQLAlchemy expressions for simple asserts.

    MagicMock for SQLAlchemy which can compare alchemys expressions in assertions.

    For example::

        >>> from sqlalchemy import or_
        >>> from sqlalchemy.sql.expression import column
        >>> c = column('column')
        >>> s = AlchemyMagicMock()

        >>> _ = s.filter(or_(c == 5, c == 10))

        >>> _ = s.filter.assert_called_once_with(or_(c == 5, c == 10))
        >>> _ = s.filter.assert_any_call(or_(c == 5, c == 10))
        >>> _ = s.filter.assert_has_calls([mock.call(or_(c == 5, c == 10))])

        >>> s.reset_mock()
        >>> _ = s.filter(c == 5)
        >>> _ = s.filter.assert_called_once_with(c == 10)
        Traceback (most recent call last):
        ...
        AssertionError: expected call not found.
        Expected: filter(BinaryExpression(sql='"column" = :column_1', \
        params={'column_1': 10}))
        Actual: filter(BinaryExpression(sql='"column" = :column_1', \
        params={'column_1': 5}))
    """

    @overload
    def __init__(
        self,
        spec: Optional[Any] = ...,
        side_effect: Optional[Any] = ...,
        return_value: Any = ...,
        wraps: Optional[Any] = ...,
        name: Optional[Any] = ...,
        spec_set: Optional[Any] = ...,
        parent: Optional[Any] = ...,
        _spec_state: Optional[Any] = ...,
        _new_name: Any = ...,
        _new_parent: Optional[Any] = ...,
        **kwargs: Any,
    ) -> None:
        ...  # pragma: no cover

    def __init__(self, *args, **kwargs) -> None:
        """Creates AlchemyMagicMock that can be used as limited SQLAlchemy session."""
        kwargs.setdefault("__name__", "Session")
        super(AlchemyMagicMock, self).__init__(*args, **kwargs)

    def _format_mock_call_signature(self, args: Any, kwargs: Any) -> str:
        """Formats the mock call into a string."""
        name = self._mock_name or "mock"
        args, kwargs = sqlalchemy_call(mock.call(*args, **kwargs))
        return mock._format_call_signature(name, args, kwargs)

    def assert_called_with(self, *args: Any, **kwargs: Any) -> None:
        """Assert for a specific call to have happened."""
        args, kwargs = sqlalchemy_call(mock.call(*args, **kwargs))
        return super(AlchemyMagicMock, self).assert_called_with(*args, **kwargs)

    def assert_any_call(self, *args: Any, **kwargs: Any) -> None:
        """Assert for a specific call to have happened."""
        args, kwargs = sqlalchemy_call(mock.call(*args, **kwargs))
        with setattr_tmp(
            self,
            "call_args_list",
            [sqlalchemy_call(i) for i in self.call_args_list],
        ):
            return super(AlchemyMagicMock, self).assert_any_call(*args, **kwargs)

    def assert_has_calls(self, calls: List[Call], any_order: bool = False) -> None:
        """Assert for a list of calls to have happened."""
        calls = [sqlalchemy_call(i) for i in calls]
        with setattr_tmp(
            self,
            "mock_calls",
            type(self.mock_calls)([sqlalchemy_call(i) for i in self.mock_calls]),
        ):
            return super(AlchemyMagicMock, self).assert_has_calls(calls, any_order)


class UnifiedAlchemyMagicMock(AlchemyMagicMock):
    """A MagicMock that combines SQLALchemy to mock a session.

    MagicMock which unifies common SQLALchemy session functions for easier assertions.

    Attributes:
        boundary: A dict of SQLAlchemy functions or statements that get
            or retreive data from calls. This dictionary has values
            that are the callable functions to process the function calls.
        unify: A dict of SQLAlchemy functions or statements that are to
            unifying expressions together. This dictionary has values
            that are the callable functions to process the function calls. Note
            that across query calls data and, as such, these calls are not unified.
            Check out the examples for this class for more detail about this
            limitation.
        mutate: A set of operations that mutate data. The currently supported
            operations include ``.delete()``, ``.add()``, and ``.add_all()``.
            More operations are planned and this is a future area of work.

    For example::

        >>> from sqlalchemy.sql.expression import column
        >>> c = column('column')

        >>> s = UnifiedAlchemyMagicMock()
        >>> s.query(None).filter(c == 'one').filter(c == 'two').all()
        []
        >>> s.query(None).filter(c == 'three').filter(c == 'four').all()
        []
        >>> s.filter.call_count
        2
        >>> s.filter.assert_any_call(c == 'one', c == 'two')
        >>> s.filter.assert_any_call(c == 'three', c == 'four')

    In addition, mock data be specified to stub real DB interactions.
    Result-sets are specified per filtering criteria so that unique data
    can be returned depending on query/filter/options criteria.
    Data is given as a list of ``(criteria, result)`` tuples where ``criteria``
    is a list of calls.
    Reason for passing data as a list vs a dict is that calls and SQLAlchemy
    expressions are not hashable hence cannot be dict keys.

    For example::

        >>> from sqlalchemy import Column, Integer, String
        >>> from sqlalchemy.ext.declarative import declarative_base

        >>> Base = declarative_base()

        >>> class SomeClass(Base):
        ...     __tablename__ = 'some_table'
        ...     pk1 = Column(Integer, primary_key=True)
        ...     pk2 = Column(Integer, primary_key=True)
        ...     name =  Column(String(50))
        ...     def __repr__(self):
        ...         return str(self.pk1)

        >>> s = UnifiedAlchemyMagicMock(data=[
        ...     (
        ...         [mock.call.query('foo'),
        ...          mock.call.filter(c == 'one', c == 'two')],
        ...         [SomeClass(pk1=1, pk2=1), SomeClass(pk1=2, pk2=2)]
        ...     ),
        ...     (
        ...         [mock.call.query('foo'),
        ...          mock.call.filter(c == 'one', c == 'two'),
        ...          mock.call.order_by(c)],
        ...         [SomeClass(pk1=2, pk2=2), SomeClass(pk1=1, pk2=1)]
        ...     ),
        ...     (
        ...         [mock.call.filter(c == 'three')],
        ...         [SomeClass(pk1=3, pk2=3)]
        ...     ),
        ... ])

        # .all()
        >>> s.query('foo').filter(c == 'one').filter(c == 'two').all()
        [1, 2]
        >>> s.query('bar').filter(c == 'one').filter(c == 'two').all()
        []
        >>> s.query('foo').filter(c == 'one').filter(c == 'two').order_by(c).all()
        [2, 1]
        >>> s.query('foo').filter(c == 'one').filter(c == 'three').order_by(c).all()
        []
        >>> s.query('foo').filter(c == 'three').all()
        [3]
        >>> s.query(None).filter(c == 'four').all()
        []

        # .iter()
        >>> list(s.query('foo').filter(c == 'two').filter(c == 'one'))
        [1, 2]

        # .count()
        >>> s.query('foo').filter(c == 'two').filter(c == 'one').count()
        2

        # .first()
        >>> s.query('foo').filter(c == 'one').filter(c == 'two').first()
        1
        >>> s.query('bar').filter(c == 'one').filter(c == 'two').first()

        # .one() and scalar
        >>> s.query('foo').filter(c == 'three').one()
        3
        >>> s.query('foo').filter(c == 'three').scalar()
        3
        >>> s.query('bar').filter(c == 'one').filter(c == 'two').one_or_none()

        # .get()
        >>> s.query('foo').get((1, 1))
        1
        >>> s.query('foo').get((4, 4))
        >>> s.query('foo').filter(c == 'two').filter(c == 'one').get((1, 1))
        1
        >>> s.query('foo').filter(c == 'three').get((1, 1))
        1
        >>> s.query('foo').filter(c == 'three').get((4, 4))

        # dynamic session
        >>> class Model(Base):
        ...     __tablename__ = 'model_table'
        ...     pk1 = Column(Integer, primary_key=True)
        ...     name = Column(String)
        ...     def __repr__(self):
        ...         return str(self.pk1)
        >>> s = UnifiedAlchemyMagicMock()
        >>> s.add(SomeClass(pk1=1, pk2=1))
        >>> s.add_all([SomeClass(pk1=2, pk2=2)])
        >>> s.add_all([SomeClass(pk1=4, pk2=3)])
        >>> s.add_all([Model(pk1=4, name='some_name')])
        >>> s.query(SomeClass).all()
        [1, 2, 4]
        >>> s.query(SomeClass).get((1, 1))
        1
        >>> s.query(SomeClass).get((2, 2))
        2
        >>> s.query(SomeClass).get((3, 3))
        >>> s.query(SomeClass).filter(c == 'one').all()
        [1, 2, 4]
        >>> s.query(SomeClass).get((4, 3))
        4
        >>> s.query(SomeClass).get({"pk2": 3, "pk1": 4})
        4
        >>> s.query(Model).get(4)
        4

        # .delete()
        >>> s = UnifiedAlchemyMagicMock(data=[
        ...     (
        ...         [mock.call.query('foo'),
        ...          mock.call.filter(c == 'one', c == 'two')],
        ...         [SomeClass(pk1=1, pk2=1), SomeClass(pk1=2, pk2=2)]
        ...     ),
        ...     (
        ...         [mock.call.query('foo'),
        ...          mock.call.filter(c == 'one', c == 'two'),
        ...          mock.call.order_by(c)],
        ...         [SomeClass(pk1=2, pk2=2), SomeClass(pk1=1, pk2=1)]
        ...     ),
        ...     (
        ...         [mock.call.filter(c == 'three')],
        ...         [SomeClass(pk1=3, pk2=3)]
        ...     ),
        ...     (
        ...         [mock.call.query('foo'),
        ...          mock.call.filter(
        ...             c == 'one',
        ...             c == 'two',
        ...             c == 'three',
        ...         )],
        ...         [
        ...             SomeClass(pk1=1, pk2=1),
        ...             SomeClass(pk1=2, pk2=2),
        ...             SomeClass(pk1=3, pk2=3),
        ...         ]
        ...     ),
        ... ])

        >>> s.query('foo').filter(c == 'three').all()
        [3]
        >>> s.query('foo').all()
        []
        >>> s.query('foo').filter(c == 'three').delete()
        1
        >>> s.query('foo').filter(c == 'three').all()
        []
        >>> s.query('foo').filter(c == 'one').filter(c == 'two').all()
        [1, 2]
        >>> a = s.query('foo').filter(c == 'one').filter(c == 'two')
        >>> a.filter(c == 'three').all()
        [1, 2, 3]
        >>> s = UnifiedAlchemyMagicMock()
        >>> s.add(SomeClass(pk1=1, pk2=1))
        >>> s.add_all([SomeClass(pk1=2, pk2=2)])
        >>> s.query(SomeClass).all()
        [1, 2]
        >>> s.query(SomeClass).delete()
        2
        >>> s.query(SomeClass).all()
        []
        >>> s = UnifiedAlchemyMagicMock()
        >>> s.add_all([SomeClass(pk1=2, pk2=2)])
        >>> s.query(SomeClass).delete()
        1
        >>> s.query(SomeClass).delete()
        0
        >>> s.query(SomeClass).scalar()
        None

    Also note that only within same query functions are unified.
    After ``.all()`` is called or query is iterated over, future queries
    are not unified.
    """

    boundary: Dict[str, Callable] = {
        "all": lambda x: x,
        "__iter__": lambda x: iter(x),
        "count": lambda x: len(x),
        "first": lambda x: next(iter(x), None),
        "one": lambda x: (
            x[0]
            if len(x) == 1
            else (
                raiser(MultipleResultsFound, "Multiple rows were found for one()")
                if x
                else raiser(NoResultFound, "No row was found for one()")
            )
        ),
        "one_or_none": lambda x: (
            x[0]
            if len(x) == 1
            else (
                raiser(
                    MultipleResultsFound,
                    "Multiple rows were found for one_or_none()",
                )
                if x
                else None
            )
        ),
        "get": lambda x, idmap: get_item_attr(build_identity_map(x), idmap),
        "scalar": lambda x: get_scalar(x),
        "update": lambda x, *args, **kwargs: None,
    }
    unify: Dict[str, Optional[UnorderedCall]] = {
        "add_columns": None,
        "distinct": None,
        "execute": None,
        "filter": UnorderedCall,
        "filter_by": UnorderedCall,
        "group_by": None,
        "join": None,
        "offset": None,
        "options": None,
        "order_by": None,
        "limit": None,
        "query": None,
        "scalars": None,
        "where": None,
    }

    mutate: Set[str] = {"add", "add_all", "delete"}

    @overload
    def __init__(
        self,
        spec: Optional[Any] = ...,
        side_effect: Optional[Any] = ...,
        return_value: Any = ...,
        wraps: Optional[Any] = ...,
        name: Optional[Any] = ...,
        spec_set: Optional[Any] = ...,
        parent: Optional[Any] = ...,
        _spec_state: Optional[Any] = ...,
        _new_name: Any = ...,
        _new_parent: Optional[Any] = ...,
        **kwargs: Any,
    ) -> None:
        ...  # pragma: no cover

    def __init__(self, *args, **kwargs) -> None:
        """Creates an UnifiedAlchemyMagicMock to mock a SQLAlchemy session."""
        kwargs["_mock_default"] = kwargs.pop("default", [])
        kwargs["_mock_data"] = kwargs.pop("data", None)
        kwargs.update(
            {k: AlchemyMagicMock(side_effect=partial(self._get_data, _mock_name=k)) for k in self.boundary}
        )

        kwargs.update(
            {
                k: AlchemyMagicMock(
                    return_value=self,
                    side_effect=partial(self._unify, _mock_name=k),
                )
                for k in self.unify
            }
        )

        kwargs.update(
            {
                k: AlchemyMagicMock(
                    return_value=None,
                    side_effect=partial(self._mutate_data, _mock_name=k),
                )
                for k in self.mutate
            }
        )

        super(UnifiedAlchemyMagicMock, self).__init__(*args, **kwargs)

    def _get_previous_calls(self, calls: Sequence[Call]) -> Iterator:
        """Gets the previous calls on the same line."""
        # the calls that end lines
        call_enders = list(self.boundary.keys()) + ["delete"]
        return iter(takewhile(lambda i: i[0] not in call_enders, reversed(calls)))

    def _get_previous_call(self, name: str, calls: Sequence[Call]) -> Optional[Call]:
        """Gets the previous call right before the current call."""
        # get all previous session calls within same session query
        previous_calls = self._get_previous_calls(calls)

        # skip last call
        next(previous_calls)

        return next(iter(filter(lambda i: i[0] == name, previous_calls)), None)

    @overload
    def _unify(
        self,
        value: Any = ...,
        name: Optional[Any] = ...,
        parent: Optional[Any] = ...,
        two: bool = ...,
        from_kall: bool = ...,
    ) -> None:
        ...  # pragma: no cover

    def _unify(self, *args, **kwargs) -> Any:
        """Unify the SQLAlchemy expressions."""
        _mock_name = kwargs.pop("_mock_name")
        submock = getattr(self, _mock_name)

        previous_method_call = self._get_previous_call(_mock_name, self.method_calls)
        previous_mock_call = self._get_previous_call(_mock_name, self.mock_calls)

        if previous_mock_call is None:
            return submock.return_value

        # remove immediate call from both filter mock as well as the parent mock object
        # as it already registered in self.__call__ before this side-effect is call
        submock.call_count -= 1
        submock.call_args_list.pop()
        submock.mock_calls.pop()
        self.method_calls.pop()
        self.mock_calls.pop()

        # remove previous call since we will be inserting new call instead
        submock.call_args_list.pop()
        submock.mock_calls.pop()
        self.method_calls.pop(indexof(previous_method_call, self.method_calls))
        self.mock_calls.pop(indexof(previous_mock_call, self.mock_calls))

        name, pargs, pkwargs = previous_method_call
        args = pargs + args
        kwargs = copy_and_update(pkwargs, kwargs)

        submock.call_args = Call((args, kwargs), two=True)
        submock.call_args_list.append(Call((args, kwargs), two=True))
        submock.mock_calls.append(Call(("", args, kwargs)))

        self.method_calls.append(Call((name, args, kwargs)))
        self.mock_calls.append(Call((name, args, kwargs)))

        return submock.return_value

    def _get_data(self, *args: Any, **kwargs: Any) -> Any:
        """Get the data for the SQLAlchemy expression."""
        _mock_name = kwargs.pop("_mock_name")
        _mock_default = self._mock_default
        _mock_data = self._mock_data
        if _mock_data is not None:
            previous_calls = [
                sqlalchemy_call(i, with_name=True, base_call=self.unify.get(i[0]) or Call)
                for i in self._get_previous_calls(self.mock_calls[:-1])
            ]
            sorted_mock_data = sorted(_mock_data, key=lambda x: len(x[0]), reverse=True)
            if _mock_name == "get":
                query_call = [c for c in previous_calls if c[0] in ["query", "execute"]][0]
                results = list(chain(*[result for calls, result in sorted_mock_data if query_call in calls]))
                return self.boundary[_mock_name](results, *args, **kwargs)

            else:
                for calls, result in sorted_mock_data:
                    calls = [
                        sqlalchemy_call(
                            i,
                            with_name=True,
                            base_call=self.unify.get(i[0]) or Call,
                        )
                        for i in calls
                    ]
                    if all(c in previous_calls for c in calls):
                        return self.boundary[_mock_name](result, *args, **kwargs)

        return self.boundary[_mock_name](_mock_default, *args, **kwargs)

    def _mutate_data(self, *args: Any, **kwargs: Any) -> Optional[int]:
        """Alter the data for the SQLAlchemy expression."""
        _mock_name = kwargs.get("_mock_name")
        _mock_data = self._mock_data = self._mock_data or []
        if _mock_name == "add":
            to_add = args[0]
            query_call = mock.call.query(type(to_add))

            mocked_data = next(iter(filter(lambda i: i[0] == [query_call], _mock_data)), None)
            if mocked_data:
                mocked_data[1].append(to_add)
            else:
                _mock_data.append(([query_call], [to_add]))

        elif _mock_name == "add_all":
            to_add = args[0]
            _kwargs = kwargs.copy()
            _kwargs["_mock_name"] = "add"

            for i in to_add:
                self._mutate_data(i, *args[1:], **_kwargs)
        # delete case
        else:
            _kwargs = kwargs.copy()
            # pretend like all is being called to get data
            _kwargs["_mock_name"] = "all"
            _mock_name = _kwargs.pop("_mock_name")
            _mock_data = self._mock_data
            num_deleted = 0
            previous_calls = [
                sqlalchemy_call(i, with_name=True, base_call=self.unify.get(i[0]) or Call)
                for i in self._get_previous_calls(self.mock_calls[:-1])
            ]
            sorted_mock_data = sorted(_mock_data, key=lambda x: len(x[0]), reverse=True)
            temp_mock_data = list()
            found_query = False
            for calls, result in sorted_mock_data:
                calls = [
                    sqlalchemy_call(
                        i,
                        with_name=True,
                        base_call=self.unify.get(i[0]) or Call,
                    )
                    for i in calls
                ]
                if all(c in previous_calls for c in calls) and not found_query:
                    num_deleted = len(result)
                    temp_mock_data.append((calls, []))
                    found_query = True
                else:
                    temp_mock_data.append((calls, result))
            self._mock_data = temp_mock_data
            return num_deleted
