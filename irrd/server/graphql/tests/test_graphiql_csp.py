"""Tests for the strict-CSP adapter around ariadne's GraphiQL explorer."""

import re

import pytest

from irrd.server.graphql import graphiql_csp
from irrd.server.graphql.graphiql_csp import GRAPHIQL_EXTERNAL_SRI, build_explorer


class TestBuildExplorer:
    def test_sri_tags_have_correct_crossorigin(self):
        # ariadne emits a bare crossorigin on <script> tags but not on <link>;
        # _inject_sri adds it on links. Regression check that integrity-bearing
        # tags carry exactly one crossorigin: neither missing nor duplicated.
        served = build_explorer().explorer.html(None)
        for tag in re.findall(r"<(?:script|link)[^>]*>", served):
            if "integrity=" not in tag:
                continue
            assert tag.count("crossorigin") == 1, tag

    def test_unpinned_url_fails(self, monkeypatch):
        smaller = dict(GRAPHIQL_EXTERNAL_SRI)
        dropped_url, _ = smaller.popitem()
        monkeypatch.setattr(graphiql_csp, "GRAPHIQL_EXTERNAL_SRI", smaller)
        with pytest.raises(RuntimeError, match=re.escape(dropped_url)):
            build_explorer()

    def test_inject_sri_silent_noop_fails(self, monkeypatch):
        monkeypatch.setattr(graphiql_csp, "_inject_sri", lambda html: html)
        with pytest.raises(RuntimeError, match="integrity"):
            build_explorer()
