"""Strict-CSP adapter around ariadne.explorer.graphiql.ExplorerGraphiQL.

Ariadne's stock GraphiQL HTML uses inline <script>/<style> blocks and loads
React + GraphiQL from a public CDN without SRI, neither of which is
compatible with a strict CSP. `build_explorer()` returns an explorer whose
external loads carry SRI integrity attributes plus the CSP `sha256-...`
sources that allow its inline blocks, and raises at startup on any
inconsistencies. `GRAPHIQL_CDN_ORIGIN` is exported for CSP composition.
Regenerate the SRI dict via `python -m irrd.server.graphql.graphiql_csp`.
"""

import base64
import hashlib
from html.parser import HTMLParser
from typing import Dict, List, NamedTuple, Optional

from ariadne.explorer.graphiql import ExplorerGraphiQL

GRAPHIQL_CDN_ORIGIN = "https://unpkg.com"

GRAPHIQL_EXTERNAL_SRI = {
    "https://unpkg.com/graphiql@3.3.2/graphiql.min.css": (
        "sha384-PNLpacmXJKoE7OSGX9OropkrZb2wdZx12taF1om8oQKkwJmzbqWEW9rKK8WT7IZ1"
    ),
    "https://unpkg.com/react@17/umd/react.production.min.js": (
        "sha384-7Er69WnAl0+tY5MWEvnQzWHeDFjgHSnlQfDDeWUvv8qlRXtzaF/pNo18Q2aoZNiO"
    ),
    "https://unpkg.com/react-dom@17/umd/react-dom.production.min.js": (
        "sha384-vj2XpC1SOa8PHrb0YlBqKN7CQzJYO72jz4CkDQ+ePL1pwOV4+dn05rPrbLGUuvCv"
    ),
    "https://unpkg.com/graphiql@3.3.2/graphiql.min.js": (
        "sha384-/jufPMBJpSyP7vyv2ht40LRJmcmVS5SWfhAYFyfsumlltrrnl/XjZljb5+cxgZUM"
    ),
}


class GraphiQLExplorerBuild(NamedTuple):
    explorer: ExplorerGraphiQL
    script_hashes: List[str]
    style_hashes: List[str]


class _ExplorerScan(HTMLParser):
    """Collect inline <script>/<style> bodies and external resource attrs
    from ariadne's rendered HTML."""

    def __init__(self):
        super().__init__()
        self.inline_scripts: List[str] = []
        self.inline_styles: List[str] = []
        self.external_loads: List[Dict] = []
        # When inside an inline <script>/<style>, _capturing is the tag name
        # and _inline_chunks accumulates the body; otherwise both are unset.
        self._capturing: Optional[str] = None
        self._inline_chunks: List[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" in attrs:
            self.external_loads.append(attrs)
        elif tag == "link" and "href" in attrs:
            self.external_loads.append(attrs)
        elif tag in ("script", "style"):
            self._capturing = tag
            self._inline_chunks = []

    def handle_data(self, data):
        if self._capturing:
            self._inline_chunks.append(data)

    def handle_endtag(self, tag):
        if self._capturing != tag:
            return
        body = "".join(self._inline_chunks)
        bucket = self.inline_scripts if tag == "script" else self.inline_styles
        bucket.append(body)
        self._capturing = None


def _inject_sri(html: str) -> str:
    # ariadne emits a bare `crossorigin` on its <script> tags but not on <link>
    # tags; SRI on a stylesheet needs CORS so we add `crossorigin="anonymous"`
    # there too. If ariadne ever changes attribute quoting from double quotes,
    # these literal replacements no-op and build_explorer()'s `integrity not
    # in attrs` check then raises.
    for url, sri in GRAPHIQL_EXTERNAL_SRI.items():
        html = html.replace(f'src="{url}"', f'src="{url}" integrity="{sri}"')
        html = html.replace(
            f'href="{url}"',
            f'href="{url}" integrity="{sri}" crossorigin="anonymous"',
        )
    return html


def _csp_hash(content: str) -> str:
    digest = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
    return f"'sha256-{digest}'"


def build_explorer() -> GraphiQLExplorerBuild:
    """Construct the CSP-safe GraphiQL explorer and the CSP `sha256-...` hash
    sources that allow its inline <script>/<style> blocks. Raises if ariadne
    references an unpinned URL or if SRI injection silently no-ops; call at
    import time so the failure is loud.
    """
    # Ariadne 0.25.2's GraphiQL explorer plugin template is broken: it calls a
    # `useExplorerPlugin` hook that no longer exists in plugin-explorer 3.1.0
    # (the same version ariadne's template references). Disable the plugin.
    explorer = ExplorerGraphiQL(title="IRRD GraphQL", explorer_plugin=False)
    explorer.parsed_html = _inject_sri(explorer.parsed_html)

    scan = _ExplorerScan()
    scan.feed(explorer.parsed_html)
    for attrs in scan.external_loads:
        url = attrs.get("src") or attrs.get("href")
        if url not in GRAPHIQL_EXTERNAL_SRI:
            raise RuntimeError(
                f"unpinned external resource {url}; regenerate via"
                " `python -m irrd.server.graphql.graphiql_csp`"
            )
        if "integrity" not in attrs:
            raise RuntimeError(f"no integrity= attribute on {url}; ariadne template format changed")

    script_hashes = [_csp_hash(s) for s in scan.inline_scripts]
    style_hashes = [_csp_hash(s) for s in scan.inline_styles]
    return GraphiQLExplorerBuild(explorer, script_hashes, style_hashes)


def _print_regenerated_sri() -> None:  # pragma: no cover
    """Print a fresh GRAPHIQL_EXTERNAL_SRI literal from ariadne's current
    template. Network errors raise; the browser's SRI check on next deploy
    is the backstop if a printed hash is wrong.
    """
    import urllib.request

    scan = _ExplorerScan()
    scan.feed(ExplorerGraphiQL(explorer_plugin=False).parsed_html)
    urls = sorted({attrs["src"] if "src" in attrs else attrs["href"] for attrs in scan.external_loads})
    rows = []
    for url in urls:
        data = urllib.request.urlopen(url, timeout=30).read()
        digest = base64.b64encode(hashlib.sha384(data).digest()).decode()
        rows.append((url, f"sha384-{digest}"))

    print("GRAPHIQL_EXTERNAL_SRI = {")
    for url, sri in rows:
        print(f'    "{url}": "{sri}",')
    print("}")


if __name__ == "__main__":
    _print_regenerated_sri()
