from graphql import build_schema, get_introspection_query, parse, specified_rules

from ..validation import MAX_FRAGMENT_SPREADS, validate_query

SCHEMA = build_schema("type Query { name: String }")
RULES = list(specified_rules)


def test_excessive_fragment_spreads_refused():
    query = "{ name %s }\nfragment F on Query { name }" % ("...F " * (MAX_FRAGMENT_SPREADS + 1))
    errors = validate_query(SCHEMA, parse(query), rules=RULES)
    assert [error.message for error in errors] == [
        f"Query may not have more than {MAX_FRAGMENT_SPREADS} fragment spreads"
    ]


def test_valid_queries_accepted():
    for query in ["{ name }", get_introspection_query()]:
        assert not validate_query(SCHEMA, parse(query), rules=RULES)


def test_other_validation_rules_are_kept():
    assert validate_query(SCHEMA, parse("{ nonexistent }"), rules=RULES)
