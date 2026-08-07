"""Self-hosted GraphiQL explorer.

Serves graphiql.html same-origin; its vendored bundle is served from the /static
mount, so the CSP can stay strict.
Refresh the bundle via `python -m irrd.scripts.update_graphiql_vendor`.
"""

from pathlib import Path

from ariadne.explorer import Explorer

_TEMPLATE = (Path(__file__).parent / "graphiql.html").read_text(encoding="utf-8")


class IRRDGraphiQLExplorer(Explorer):
    def html(self, request) -> str:
        return _TEMPLATE
