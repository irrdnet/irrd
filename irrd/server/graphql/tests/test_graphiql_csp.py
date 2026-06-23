"""Tests for the strict-CSP adapter around ariadne's GraphiQL explorer."""

import re

import pytest

from irrd.server.graphql import graphiql_csp
from irrd.server.graphql.graphiql_csp import (
    GRAPHIQL_EXTERNAL_SRI,
    build_explorer,
)


class TestBuildExplorer:
    def test_sri_tags_have_correct_crossorigin(self):
        # Ariadne emits crossorigin="anonymous" on its external loads; SRI
        # requires it. Regression check that there's exactly one: neither
        # missing nor duplicated by us.
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

    def test_hoist_importmap_noop_when_already_correct(self):
        html = '<script type="importmap"></script>\n<link rel="modulepreload" />'
        assert graphiql_csp._hoist_importmap(html) == html

    def test_explorer_scan_captures_script_src(self):
        # ariadne 1.1.0 emits ESM via <link rel=modulepreload>, but _ExplorerScan
        # still recognises <script src=...> as defense if ariadne ever reverts.
        scan = graphiql_csp._ExplorerScan()
        scan.feed('<script src="https://example.com/x.js" integrity="sha384-x"></script>')
        assert len(scan.external_loads) == 1
        assert scan.external_loads[0]["src"] == "https://example.com/x.js"
        assert scan.external_loads[0]["integrity"] == "sha384-x"
