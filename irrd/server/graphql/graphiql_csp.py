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
from typing import NamedTuple

from ariadne.explorer.graphiql import ExplorerGraphiQL

GRAPHIQL_CDN_ORIGIN = "https://esm.sh"

GRAPHIQL_EXTERNAL_SRI = {
    "https://esm.sh/@graphiql/plugin-explorer@5.1.1/dist/style.css": (
        "sha384-vTFGj0krVqwFXLB7kq/VHR0/j2+cCT/B63rge2mULaqnib2OX7DVLUVksTlqvMab"
    ),
    "https://esm.sh/@graphiql/plugin-explorer@5.1.1?standalone&external=react,@graphiql/react,graphql": (
        "sha384-rR9phbzRkwb/HINixBgg9De/Z/S6G9/OiRX7cVR1AKhP+2AUTfX7wmDT76y5HeSf"
    ),
    "https://esm.sh/@graphiql/react@0.37.3?standalone&external=react,react-dom,graphql,@graphiql/toolkit,@emotion/is-prop-valid": (
        "sha384-iZsbTy9B0VcX2BOTdqMuX0uJ9Hff5GbG2QeOt4OeMp0GHza76dwQaYQYNYkZkIVq"
    ),
    "https://esm.sh/@graphiql/toolkit@0.11.3?standalone&external=graphql": (
        "sha384-ZsnupyYmzpNjF1Z/81zwi4nV352n4P7vm0JOFKiYnAwVGOf9twnEMnnxmxabMBXe"
    ),
    "https://esm.sh/graphiql@5.2.2/dist/style.css": (
        "sha384-f6GHLfCwoa4MFYUMd3rieGOsIVAte/evKbJhMigNdzUf52U9bV2JQBMQLke0ua+2"
    ),
    "https://esm.sh/graphiql@5.2.2/setup-workers/esm.sh": (
        "sha384-Frkk7gyhh5CAzmHTmWV9pKp1MX4JfJQybqf0W4SSWh4mTpHac4yGoITih4dzTeS2"
    ),
    "https://esm.sh/graphiql@5.2.2?standalone&external=react,react-dom,@graphiql/react,graphql": (
        "sha384-SzHBEbcQfhvmwqh5Vtat9k7b/kIzmdVO3KMzQiAYwcxCA9x7vZwFRUgjzN1AeV3q"
    ),
    "https://esm.sh/graphql@16.11.0": (
        "sha384-uhRXaGfgCFqosYlwSLNd7XpDF9kcSUycv5yVbjjhH5OrE675kd0+MNIAAaSc+1Pi"
    ),
    "https://esm.sh/react-dom@19.1.0": (
        "sha384-CKiqgCWLo5oVMbiCv36UR0pLRrzeRKhw1jFUpx0j/XdZOpZ43zOHhjf8yjLNuLEy"
    ),
    "https://esm.sh/react-dom@19.1.0/client": (
        "sha384-QH8CM8CiVIQ+RoTOjDp6ktXLkc0ix+qbx2mo7SSnwMeUQEoM4XJffjoSPY85X6VH"
    ),
    "https://esm.sh/react@19.1.0": "sha384-C3ApUaeHIj1v0KX4cY/+K3hQZ/8HcAbbmkw1gBK8H5XN4LCEguY7+A3jga11SaHF",
}


class GraphiQLExplorerBuild(NamedTuple):
    explorer: ExplorerGraphiQL
    script_hashes: list[str]
    style_hashes: list[str]


class _ExplorerScan(HTMLParser):
    """Collect inline <script>/<style> bodies and external resource attrs
    from ariadne's rendered HTML."""

    def __init__(self):
        super().__init__()
        self.inline_scripts: list[str] = []
        self.inline_styles: list[str] = []
        self.external_loads: list[dict] = []
        # When inside an inline <script>/<style>, _capturing is the tag name
        # and _inline_chunks accumulates the body; otherwise both are unset.
        self._capturing: str | None = None
        self._inline_chunks: list[str] = []

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
    # ariadne already emits `crossorigin="anonymous"` on its external loads;
    # we add `integrity=` so SRI verification runs. If ariadne ever changes
    # attribute quoting from double quotes, these literal replacements no-op
    # and build_explorer()'s `integrity not in attrs` check then raises.
    for url, sri in GRAPHIQL_EXTERNAL_SRI.items():
        html = html.replace(f'src="{url}"', f'src="{url}" integrity="{sri}"')
        html = html.replace(f'href="{url}"', f'href="{url}" integrity="{sri}"')
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
    explorer = ExplorerGraphiQL(title="IRRD GraphQL", explorer_plugin=True)
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
    scan.feed(ExplorerGraphiQL(explorer_plugin=True).parsed_html)
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
