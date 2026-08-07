"""Refresh the vendored GraphiQL bundle under irrd/webui/static/js/graphiql/.

Do not bump past graphiql@3.x / react@18.x: this page self-hosts UMD builds
loaded as plain <script> globals, and UMD is being retired. react@19 dropped
its UMD build, so graphiql@4 deprecates UMD and graphiql@5 removes it (and
switches to monaco-editor, which needs separate worker scripts). Going newer
means bundling ESM (or an esm.sh importmap) instead of vendoring static files.
See https://graphql.org/blog/2025-07-17-graphiql-5/.
"""

import urllib.request
from pathlib import Path

BUNDLE_DIR = Path(__file__).resolve().parents[1] / "webui/static/js/graphiql"
HOST = "unpkg.com"

# GRAPHIQL_VERSION is also embedded in graphiql.html's upstream-example link,
# which test_explorer.py keeps in sync.
REACT_VERSION = "18.3.1"
GRAPHIQL_VERSION = "3.9.0"
PLUGIN_EXPLORER_VERSION = "3.2.6"

DOWNLOADS = {
    "react.production.min.js": f"https://{HOST}/react@{REACT_VERSION}/umd/react.production.min.js",
    "react-dom.production.min.js": (
        f"https://{HOST}/react-dom@{REACT_VERSION}/umd/react-dom.production.min.js"
    ),
    "graphiql.min.js": f"https://{HOST}/graphiql@{GRAPHIQL_VERSION}/graphiql.min.js",
    "graphiql.min.css": f"https://{HOST}/graphiql@{GRAPHIQL_VERSION}/graphiql.min.css",
    "plugin-explorer.umd.js": (
        f"https://{HOST}/@graphiql/plugin-explorer@{PLUGIN_EXPLORER_VERSION}/dist/index.umd.js"
    ),
    "plugin-explorer.style.css": (
        f"https://{HOST}/@graphiql/plugin-explorer@{PLUGIN_EXPLORER_VERSION}/dist/style.css"
    ),
}


def main() -> None:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in DOWNLOADS.items():
        print(f"fetch {url}")
        with urllib.request.urlopen(url, timeout=30) as resp:
            (BUNDLE_DIR / filename).write_bytes(resp.read())


if __name__ == "__main__":
    main()
