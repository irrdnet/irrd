"""A module for comparing SQLAlchemy expressions."""
from __future__ import absolute_import, annotations, print_function, unicode_literals

import itertools
from collections.abc import Mapping
from typing import Any, Optional
from unittest import mock

from sqlalchemy import func
from sqlalchemy.sql.expression import column, or_

from .utils import match_type

ALCHEMY_UNARY_EXPRESSION_TYPE = type(column("").asc())
ALCHEMY_BINARY_EXPRESSION_TYPE = type(column("") == "")
ALCHEMY_BOOLEAN_CLAUSE_LIST = type(or_(column("") == "", column("").is_(None)))
ALCHEMY_FUNC_TYPE = type(func.dummy(column("")))
ALCHEMY_LABEL_TYPE = type(column("").label(""))
ALCHEMY_TYPES = (
    ALCHEMY_UNARY_EXPRESSION_TYPE,
    ALCHEMY_BINARY_EXPRESSION_TYPE,
    ALCHEMY_BOOLEAN_CLAUSE_LIST,
    ALCHEMY_FUNC_TYPE,
    ALCHEMY_LABEL_TYPE,
)


class PrettyExpression(object):
    """Wrapper around given expression with pretty representations.

    Wraps any expression in order to represent in a string in a pretty
    fashion. This also enables easier comparison through string representations.

    Attributes:
        expr: Some kind of expression or a PrettyExpression itself.

    For example::

        >>> c = column('column')
        >>> PrettyExpression(c == 5)
        BinaryExpression(sql='"column" = :column_1', params={'column_1': 5})
        >>> PrettyExpression(10)
        10
        >>> PrettyExpression(PrettyExpression(15))
        15
    """

    __slots__ = ["expr"]

    def __init__(self, e: Any) -> None:
        """Create a PrettyExpression using an expression."""
        if isinstance(e, PrettyExpression):
            e = e.expr
        self.expr = e

    def __repr__(self) -> str:
        """Get the string representation of a PrettyExpression."""
        if not isinstance(self.expr, ALCHEMY_TYPES):
            return repr(self.expr)

        compiled = self.expr.compile()

        return "{}(sql={!r}, params={!r})".format(
            self.expr.__class__.__name__,
            match_type(str(compiled).replace("\n", " "), str),
            {match_type(k, str): v for k, v in compiled.params.items()},
        )


class ExpressionMatcher(PrettyExpression):
    """Matcher for comparing SQLAlchemy expressions.

    Similar to
    http://www.voidspace.org.uk/python/mock/examples.html#more-complex-argument-matching

    For example::

        >>> c = column('column')
        >>> c2 = column('column2')
        >>> l1 = c.label('foo')
        >>> l2 = c.label('foo')
        >>> l3 = c.label('bar')
        >>> l4 = c2.label('foo')
        >>> e1 = c.in_(['foo', 'bar'])
        >>> e2 = c.in_(['foo', 'bar'])
        >>> e3 = c.in_(['cat', 'dog'])
        >>> e4 = c == 'foo'
        >>> e5 = func.lower(c)

        >>> ExpressionMatcher(e1) == mock.ANY
        True
        >>> ExpressionMatcher(e1) == 5
        False
        >>> ExpressionMatcher(e1) == e2
        True
        >>> ExpressionMatcher(e1) != e2
        False
        >>> ExpressionMatcher(e1) == e3
        False
        >>> ExpressionMatcher(e1) == e4
        False
        >>> ExpressionMatcher(e5) == func.lower(c)
        True
        >>> ExpressionMatcher(e5) == func.upper(c)
        False
        >>> ExpressionMatcher(e1) == ExpressionMatcher(e2)
        True
        >>> ExpressionMatcher(c) == l1
        False
        >>> ExpressionMatcher(l1) == l2
        True
        >>> ExpressionMatcher(l1) == l3
        True
        >>> ExpressionMatcher(l1) == l4
        False

    It also works with nested structures::

        >>> ExpressionMatcher([c == 'foo']) == [c == 'foo']
        True
        >>> a = {'foo': c == 'foo', 'bar': 5, 'hello': 'world'}
        >>> ExpressionMatcher(a) == a
        True
    """

    def __eq__(self, other: Any) -> bool:
        """Compares two expressions using the ExpressionMatcher."""
        if isinstance(other, type(self)):
            other = other.expr

        # if the right hand side is mock.ANY,
        # mocks comparison will not be used hence
        # we hard-code comparison here
        if isinstance(self.expr, type(mock.ANY)) or isinstance(other, type(mock.ANY)):
            return True

        # handle string comparison bytes vs unicode in dict keys
        if isinstance(self.expr, str) and isinstance(other, str):
            other = match_type(other, type(self.expr))

        # compare sqlalchemy public api attributes
        if type(self.expr) is not type(other):
            return False

        equal = self._equals_alchemy(other)
        if equal is not None:
            return equal

        expr_compiled = self.expr.compile()
        other_compiled = other.compile()

        if str(expr_compiled) != str(other_compiled):
            return False
        if expr_compiled.params != other_compiled.params:
            return False

        return True

    def _equals_alchemy(self, other: Any) -> Optional[bool]:
        """Compares for equality in the case of non ALCHEMY_TYPES."""
        if not isinstance(self.expr, ALCHEMY_TYPES):

            def _(v: Any) -> Any:
                return type(self)(v)

            if isinstance(self.expr, (list, tuple)):
                return all(_(i) == j for i, j in itertools.zip_longest(self.expr, other))

            elif isinstance(self.expr, Mapping):
                same_keys = self.expr.keys() == other.keys()
                return same_keys and all(_(self.expr[k]) == other[k] for k in self.expr.keys())

            else:
                return self.expr is other or self.expr == other

    def __ne__(self, other: Any) -> bool:
        """Compares an expression to determine inequality."""
        return not (self == other)
