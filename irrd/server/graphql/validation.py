"""
Limit the number of fragment spreads to prevent a DoS.
Introspection queries from common clients use less than ten.
"""

from collections.abc import Collection

from graphql import (
    ASTValidationRule,
    DocumentNode,
    GraphQLError,
    GraphQLSchema,
    Visitor,
    validate,
    visit,
)

MAX_FRAGMENT_SPREADS = 25


class FragmentSpreadCounter(Visitor):
    count = 0

    def enter_fragment_spread(self, *_args) -> None:
        self.count += 1


def validate_query(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    type_info=None,
) -> list[GraphQLError]:
    counter = FragmentSpreadCounter()
    visit(document_ast, counter)
    if counter.count > MAX_FRAGMENT_SPREADS:
        return [GraphQLError(f"Query may not have more than {MAX_FRAGMENT_SPREADS} fragment spreads")]
    return validate(schema, document_ast, rules=rules, max_errors=max_errors)
