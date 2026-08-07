"""Tests for the self-hosted GraphiQL explorer and its vendored bundle."""

import re
from pathlib import Path

from irrd.scripts.update_graphiql_vendor import BUNDLE_DIR, DOWNLOADS, GRAPHIQL_VERSION
from irrd.server.graphql import explorer
from irrd.server.graphql.explorer import IRRDGraphiQLExplorer

TEMPLATE = Path(explorer.__file__).parent / "graphiql.html"
VENDORED_FILES = list(DOWNLOADS)


def test_html_references_only_same_origin_assets():
    html = IRRDGraphiQLExplorer().html(None)
    for cdn in ("esm.sh", "unpkg.com", "cdn.jsdelivr"):
        assert cdn not in html, cdn
    for url in re.findall(r'(?:src|href)="([^"]+)"', html):
        assert url.startswith("/static/"), url


def test_referenced_static_files_exist():
    html = TEMPLATE.read_text()
    for name in re.findall(r"/static/js/graphiql/([^\"]+)", html):
        path = BUNDLE_DIR / name
        assert path.is_file(), name
        assert path.stat().st_size > 0, name


def test_template_references_every_vendored_file():
    html = TEMPLATE.read_text()
    for filename in VENDORED_FILES:
        assert filename in html, filename


def test_graphiql_html_example_url_matches_pinned_version():
    # Keep graphiql.html's pinned upstream-example tag in sync with the bundle.
    assert f"graphiql@{GRAPHIQL_VERSION}" in TEMPLATE.read_text()


def test_mount_target_id_matches_template():
    mount = (BUNDLE_DIR / "mount.js").read_text()
    match = re.search(r"""getElementById\(["']([^"']+)["']\)""", mount)
    assert match, "mount.js has no getElementById(...) call"
    target = match.group(1)
    assert f'id="{target}"' in TEMPLATE.read_text(), target
