// Adapted for IRRD from the graphiql CDN example; see graphiql.html.
var fetcher = GraphiQL.createFetcher({ url: "/graphql/" });
var explorer = GraphiQLPluginExplorer.explorerPlugin();
var initialQuery = [
  "# Welcome to IRRD GraphQL. Use the docs pane (top-right) and the",
  "# Explorer (left) to browse the schema. Ctrl-Enter runs the query.",
  "# Docs: https://irrd.readthedocs.io/en/stable/users/queries/graphql/",
  "",
  "{",
  "  rpslObjects(asn: 2121, objectClass: [\"route\", \"route6\"]) {",
  "    rpslPk",
  "    objectClass",
  "    source",
  "    mntBy",
  "    ... on RPSLRoute {",
  "      route",
  "      origin",
  "      rpkiStatus",
  "    }",
  "    ... on RPSLRoute6 {",
  "      route6",
  "      origin",
  "      rpkiStatus",
  "    }",
  "  }",
  "}",
  "",
].join("\n");
ReactDOM.createRoot(document.getElementById("graphiql")).render(
  React.createElement(GraphiQL, {
    fetcher: fetcher,
    plugins: [explorer],
    defaultQuery: initialQuery,
    defaultEditorToolsVisibility: true,
  })
);
