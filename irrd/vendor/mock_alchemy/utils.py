"""A module for utils for the ``mock-alchemy`` library."""
from __future__ import absolute_import, print_function, unicode_literals

from contextlib import contextmanager
from typing import Any, Dict, Sequence, Tuple, Type, Union

from sqlalchemy import inspect
from sqlalchemy.orm.exc import MultipleResultsFound


def match_type(s: Union[bytes, str], t: Union[Type[bytes], Type[str]]) -> Union[bytes, str]:
    """Match the string type.

    Matches the string type with the provided type and returns the string
    of the desired type.

    Args:
        s: The string to match the type with.
        t: The type to make the string with.

    Returns:
        An object of the desired type of type ``t``.

    For example::

        >>> assert type(match_type(b'hello', bytes)) is bytes
        >>> assert type(match_type(u'hello', str)) is str
        >>> assert type(match_type(b'hello', str)) is str
        >>> assert type(match_type(u'hello', bytes)) is bytes
    """
    if isinstance(s, t):
        return s
    if t is str:
        return s.decode("utf-8")
    else:
        return s.encode("utf-8")


def copy_and_update(target: Dict, updater: Dict) -> Dict:
    """Copy and update dictionary.

    Copy dictionary and update it all in one operation.

    Args:
        target: The dictionary to copy and update.
        updater: The updating dictionary.

    Returns:
        Dict: A new dictionary of the ``target`` copied and
        updated by ``updater``.

    For example::

        >>> a = {'foo': 'bar'}
        >>> b = copy_and_update(a, {1: 2})
        >>> a is b
        False
        >>> b == {'foo': 'bar', 1: 2}
        True
    """
    result = target.copy()
    result.update(updater)
    return result


def indexof(needle: Any, haystack: Sequence[Any]) -> int:
    """Gets the index of some item in a sequence.

    Find an index of ``needle`` in ``haystack`` by looking for exact same
    item by pointer ids vs usual ``list.index()`` which finds
    by object comparison.

    Args:
        needle: The object or item to find in the sequence.
        haystack: The sequence of items to search for the ``needle``.

    Returns:
        The index of the needle in the haystack.

    Raises:
        ValueError: If the needle is not found inside the haystack.

    For example::

        >>> a = {}
        >>> b = {}
        >>> haystack = [1, a, 2, b]
        >>> indexof(b, haystack)
        3
        >>> indexof(None, haystack)
        Traceback (most recent call last):
        ...
        ValueError: None is not in [1, {}, 2, {}]
    """
    for i, item in enumerate(haystack):
        if needle is item:
            return i
    raise ValueError("{!r} is not in {!r}".format(needle, haystack))


@contextmanager
def setattr_tmp(obj: object, name: str, value: Any) -> Any:
    """Set the atrributes of object temporarily.

    Utility for temporarily setting value in an object.

    Args:
        obj: An object to set the attribute of.
        name: The name of the attribute.
        value: The value to set the attribute to.

    Returns:
        A context manager that can be used.

    Yields:
        Used for the context manager so that this function can be used
        as ``with setattr_tmp``.

    For example::

        >>> class Foo(object):
        ...     foo = 'foo'
        >>> print(Foo.foo)
        foo
        >>> with setattr_tmp(Foo, 'foo', 'bar'):
        ...     print(Foo.foo)
        bar
        >>> print(Foo.foo)
        foo

        >>> Foo.foo = None
        >>> with setattr_tmp(Foo, 'foo', 'bar'):
        ...     print(Foo.foo)
        None
    """
    original = getattr(obj, name)

    if original is None:
        yield
        return

    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, original)


def raiser(exp: Type[Exception], *args: Any, **kwargs: Any) -> Type[Exception]:
    """Raises an exception with the given args.

    Utility for raising exceptions
    Useful in one-liners.

    Args:
        exp: The exception to raise.
        args: The args to use for the exception.
        kwargs: The kwargs to use for the exception.

    Raises:
        exp: The parameterized exception of the specified kind.

    For example::

        >>> a = lambda x: not x and raiser(ValueError, 'error message')
        >>> _ = a(True)
        >>> _ = a(False)
        Traceback (most recent call last):
        ...
        ValueError: error message
    """
    raise exp(*args, **kwargs)


def build_identity_map(items: Sequence[Any]) -> Dict:
    """Builds identity map.

    Utility for building identity map from given SQLAlchemy models.

    Args:
        items: A sequence of SQLAlchemy objects.

    Returns:
        An identity map of the given SQLAlchemy objects.

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

        >>> build_identity_map([SomeClass(pk1=1, pk2=2)])
        {(1, 2): 1}
    """
    idmap = {}

    for i in items:
        mapper = inspect(type(i)).mapper
        pk_keys = tuple(mapper.get_property_by_column(c).key for c in mapper.primary_key)
        pk = tuple(getattr(i, k) for k in sorted(pk_keys))
        idmap[pk] = i

    return idmap


def get_item_attr(idmap: Dict, access: Union[Dict, Tuple, Any]) -> Any:
    """Access dictionary in different methods.

    Utility for accessing dict by different key types (for get).

    Args:
        idmap: A dictionary of identity map of SQLAlchemy objects.
        access: The access pattern which should either be basic data type, dictionary,
            or a tuple. If it is dictionary it should map to the names of the primary
            keys of the SQLAlchemy objects. If it is a tuple, it should be a set of
            keys to search for. If it is not a dict or a tuple, then the objects in
            question must have only one primary key of the type passed
            (such as a string, integer, etc.).

    Returns:
        An SQlAlchemy object that was requested.

    For example::
        >>> idmap = {(1,): 2}
        >>> get_item_attr(idmap, 1)
        2
        >>> idmap = {(1,): 2}
        >>> get_item_attr(idmap, {"pk": 1})
        2
        >>> get_item_attr(idmap, (1,))
        2
    """
    if isinstance(access, dict):
        keys = []
        for names in sorted(access):
            keys.append(access[names])
        return idmap.get(tuple(keys))
    elif isinstance(access, tuple):
        return idmap.get(access)
    else:
        return idmap.get((access,))


def get_scalar(rows: Sequence[Any]) -> Any:
    """Utility for mocking sqlalchemy.orm.Query.scalar()."""
    if len(rows) == 1:
        try:
            return rows[0][0]
        except TypeError:
            return rows[0]
    elif len(rows) > 1:
        raise MultipleResultsFound("Multiple rows were found when exactly one was required")
    return None
