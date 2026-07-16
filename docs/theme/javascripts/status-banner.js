document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;
  const futureExecutionPages = [
    "PLUGINS",
    "ORCHESTRATION_PLUGINS",
    "STORAGE_PLUGINS",
    "RESOURCE_PLUGINS",
    "PYSPARK",
    "PYSPARK_EXECUTION",
    "SPARK_OPTIMIZATION",
    "STRUCTURED_STREAMING",
    "AIRFLOW",
    "COMPILATION",
  ];
  // Shipped in 0.5: DATAFRAME_PLUGINS, POLARS, PANDAS.
  // Shipped in 0.6: SQL, SQL_EXECUTION, SQL_PUSHDOWN stay out of this list.
  const isFutureExecution = futureExecutionPages.some((name) =>
    path.includes(`/06_EXECUTION/${name}/`)
  );
  // Dataframe and SQL plugin protocols are shipped; other Plugin SDK pages are future.
  const isPluginSdk =
    path.includes("/07_PLUGIN_SDK/") &&
    !path.includes("/07_PLUGIN_SDK/DATAFRAME_PLUGIN/") &&
    !path.includes("/07_PLUGIN_SDK/SQL_PLUGIN/") &&
    !path.includes("/07_PLUGIN_SDK/SQL_DIALECT/");
  const isDesignExample =
    path.includes("/09_EXAMPLES/") && !path.endsWith("/09_EXAMPLES/");
  const isFutureVisualization =
    path.includes("/08_VISUALIZATION/") &&
    !path.endsWith("/08_VISUALIZATION/") &&
    !path.includes("/08_VISUALIZATION/MERMAID/") &&
    !path.includes("/08_VISUALIZATION/README");
  const isProposedReference =
    path.includes("/10_REFERENCE/CONFIGURATION/") ||
    path.includes("/10_REFERENCE/ENVIRONMENT_VARIABLES/");

  if (
    !isFutureExecution &&
    !isPluginSdk &&
    !isDesignExample &&
    !isFutureVisualization &&
    !isProposedReference
  ) {
    return;
  }

  const article = document.querySelector("article.md-content__inner");
  if (!article) return;

  const banner = document.createElement("div");
  banner.className = "admonition warning";
  banner.innerHTML =
    '<p class="admonition-title">Future design—not a Pipelantic 0.6 API guide</p>' +
    "<p>This page may contain unshipped packages, commands, or interfaces. " +
    "Use Current Capabilities, the API reference, and the CLI reference for shipped behavior.</p>";
  article.prepend(banner);
});
