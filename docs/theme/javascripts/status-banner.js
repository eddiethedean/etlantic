document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;
  // Shipped in 0.5: DATAFRAME_PLUGINS, POLARS, PANDAS.
  // Shipped in 0.6: SQL, SQL_EXECUTION, SQL_PUSHDOWN.
  // Shipped in 0.7: PYSPARK, PYSPARK_EXECUTION, SPARK_OPTIMIZATION (batch).
  // Shipped in 0.8: ORCHESTRATION_PLUGINS, AIRFLOW, COMPILATION.
  // Shipped in 0.9: GRAPHVIZ, HTML, LINEAGE tooling + CLI/SDK polish.
  // Shipped in 0.11: portable authoring.
  // Shipped in 0.12: PORTABLE_TRANSFORM_COMPILER, portable Polars kernel example.
  // Shipped in 0.13: Polars + PySpark portable-relational/1 compilers.
  // Shipped in 0.15: SQL portable-relational/1 + Extract/Load + LocalScheduler.
  // Experimental in 0.7+: STRUCTURED_STREAMING (separate experimental banner).
  const futureExecutionPages = [
    "PLUGINS",
    "STORAGE_PLUGINS",
    "RESOURCE_PLUGINS",
  ];
  const experimentalExecutionPages = ["STRUCTURED_STREAMING"];
  const isFutureExecution = futureExecutionPages.some((name) =>
    path.includes(`/06_EXECUTION/${name}/`)
  );
  const isExperimentalExecution = experimentalExecutionPages.some((name) =>
    path.includes(`/06_EXECUTION/${name}/`)
  );
  // Only these unshipped provider protocol pages are future in 0.20.
  const futurePluginSdkPages = [
    "STORAGE_PLUGIN",
    "RESOURCE_PROVIDER",
    "OBSERVABILITY_PROVIDER",
  ];
  const isPluginSdk = futurePluginSdkPages.some((name) =>
    path.includes(`/07_PLUGIN_SDK/${name}/`)
  );
  const isDesignExample =
    path.includes("/09_EXAMPLES/") &&
    !path.endsWith("/09_EXAMPLES/") &&
    !path.includes("/09_EXAMPLES/AIRFLOW_COMPILE/") &&
    !path.includes("/09_EXAMPLES/SPARKFORGE_ADAPTER/") &&
    !path.includes("/09_EXAMPLES/PORTABLE_TRANSFORMS/") &&
    !path.includes("/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS/") &&
    !path.includes("/09_EXAMPLES/CONTRACT_FIRST_TUTORIAL/") &&
    !path.includes("/09_EXAMPLES/PREFECT_RUN/") &&
    !path.includes("/09_EXAMPLES/SAMPLE_PROJECT/");
  const isFutureVisualization =
    path.includes("/08_VISUALIZATION/") &&
    !path.endsWith("/08_VISUALIZATION/") &&
    !path.includes("/08_VISUALIZATION/MERMAID/") &&
    !path.includes("/08_VISUALIZATION/GRAPHVIZ/") &&
    !path.includes("/08_VISUALIZATION/HTML/") &&
    !path.includes("/08_VISUALIZATION/LINEAGE/") &&
    !path.includes("/08_VISUALIZATION/README");
  const isProposedReference =
    path.includes("/10_REFERENCE/CONFIGURATION/") ||
    path.includes("/10_REFERENCE/ENVIRONMENT_VARIABLES/");

  const article = document.querySelector("article.md-content__inner");
  if (!article) return;

  if (isExperimentalExecution) {
    const banner = document.createElement("div");
    banner.className = "admonition warning";
    banner.dataset.etlanticStatus = "experimental";
    banner.innerHTML =
      '<p class="admonition-title">Experimental in ETLantic 0.7+</p>' +
      "<p>Structured Streaming APIs are experimental. Batch Spark via " +
      "<code>etlantic-pyspark</code> is the production path. See Current Capabilities.</p>";
    article.prepend(banner);
    return;
  }

  if (
    !isFutureExecution &&
    !isPluginSdk &&
    !isDesignExample &&
    !isFutureVisualization &&
    !isProposedReference
  ) {
    return;
  }

  const banner = document.createElement("div");
  banner.className = "admonition warning";
  banner.dataset.etlanticStatus = "future";
  banner.innerHTML =
    '<p class="admonition-title">Future design—not an ETLantic 0.21 API guide</p>' +
    "<p>This page may contain unshipped packages, commands, or interfaces. " +
    "Use Current Capabilities, the API reference, and the CLI reference for shipped behavior. " +
    "Polars, PySpark, Pandas, and SQL portable-relational compilers are shipped. " +
    "Advanced profiles (string-advanced, window, reshape, …) are shipped on Polars and PySpark; see the compiler matrix for exact claims.</p>";
  article.prepend(banner);
});
