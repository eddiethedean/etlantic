# Diagnostics catalog (generated)

> **Status: Available in ETLantic 0.47.0.** Machine-readable inventory of
> diagnostic code literals found under `src/etlantic`. Regenerate with:
>
> ```bash
> uv run python scripts/generate_diagnostics_catalog.py --markdown \
>   > docs/10_REFERENCE/DIAGNOSTICS_CATALOG.md
> ```
>
> Prefer the curated tables in [Diagnostics](DIAGNOSTICS.md) for human-oriented
> meanings. This page is the exhaustive code→source index. Family
> stability tiers (`stable` / `provisional` / `experimental`):
> [Diagnostic-code stability tiers](DIAGNOSTIC_STABILITY_TIERS.md).

| Code | Example source paths |
|---|---|
| `PMAUTH201` | `src/etlantic/authoring/lifecycle.py` |
| `PMAUTH410` | `src/etlantic/authoring/resolve.py` |
| `PMCAT100` | `src/etlantic/catalog_policy.py` |
| `PMCFG200` | `src/etlantic/cli/cmds/profile.py` |
| `PMCFG201` | `src/etlantic/cli/cmds/profile.py` |
| `PMCONN501` | `src/etlantic/connectors/compatibility.py` |
| `PMCONN502` | `src/etlantic/connectors/compatibility.py` |
| `PMCONN601` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN602` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN603` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN604` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN606` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN607` | `src/etlantic/connectors/checkpoint.py` |
| `PMCONN701` | `src/etlantic/connectors/local_files.py` |
| `PMCONN702` | `src/etlantic/connectors/local_files.py` |
| `PMCONN703` | `src/etlantic/connectors/local_files.py` |
| `PMCONN710` | `src/etlantic/connectors/local_files.py` |
| `PMCONN720` | `src/etlantic/connectors/local_files.py` |
| `PMCONN721` | `src/etlantic/connectors/local_files.py` |
| `PMCONN722` | `src/etlantic/connectors/local_files.py` |
| `PMCONN730` | `src/etlantic/connectors/local_files.py` |
| `PMCONN740` | `src/etlantic/connectors/local_files.py` |
| `PMCONN741` | `src/etlantic/connectors/local_files.py` |
| `PMCONN750` | `src/etlantic/connectors/local_files.py` |
| `PMCONN751` | `src/etlantic/connectors/local_files.py` |
| `PMCONN752` | `src/etlantic/connectors/local_files.py` |
| `PMCONN753` | `src/etlantic/connectors/local_files.py` |
| `PMCONN760` | `src/etlantic/connectors/local_files.py` |
| `PMCONN761` | `src/etlantic/connectors/local_files.py` |
| `PMCONN762` | `src/etlantic/connectors/local_files.py` |
| `PMCONN763` | `src/etlantic/connectors/local_files.py` |
| `PMCONN764` | `src/etlantic/connectors/local_files.py` |
| `PMCONN765` | `src/etlantic/connectors/local_files.py` |
| `PMCONN766` | `src/etlantic/connectors/local_files.py` |
| `PMCONN770` | `src/etlantic/connectors/local_files.py` |
| `PMCONN771` | `src/etlantic/connectors/local_files.py` |
| `PMCONN772` | `src/etlantic/connectors/local_files.py` |
| `PMCONN773` | `src/etlantic/connectors/local_files.py` |
| `PMCONN774` | `src/etlantic/connectors/local_files.py` |
| `PMCONN775` | `src/etlantic/connectors/local_files.py` |
| `PMCONN776` | `src/etlantic/connectors/local_files.py` |
| `PMCONN801` | `src/etlantic/connectors/session.py` |
| `PMCONN850` | `src/etlantic/connectors/negotiate.py` |
| `PMCONN901` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN902` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN903` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN904` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN905` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN906` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN907` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN908` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN909` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN910` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN911` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN912` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN913` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN914` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN915` | `src/etlantic/connectors/cdk/config.py` |
| `PMCONN920` | `src/etlantic/connectors/cdk/context.py` |
| `PMCONN921` | `src/etlantic/connectors/cdk/context.py` |
| `PMCONN922` | `src/etlantic/connectors/cdk/context.py` |
| `PMCONN930` | `src/etlantic/connectors/cdk/batching.py` |
| `PMCONN931` | `src/etlantic/connectors/cdk/batching.py` |
| `PMCONN932` | `src/etlantic/connectors/cdk/batching.py` |
| `PMCONN933` | `src/etlantic/connectors/cdk/batching.py` |
| `PMCONN940` | `src/etlantic/connectors/cdk/publication.py`, `src/etlantic/connectors/local_files.py` |
| `PMCP400` | `src/etlantic/control_plane/attestation_memory.py`, `src/etlantic/control_plane/registry_ops.py` |
| `PMCP401` | `src/etlantic/control_plane/errors.py` |
| `PMCP403` | `src/etlantic/control_plane/errors.py` |
| `PMCP404` | `src/etlantic/control_plane/errors.py` |
| `PMCP409` | `src/etlantic/control_plane/errors.py` |
| `PMCP410` | `src/etlantic/control_plane/errors.py` |
| `PMCP503` | `src/etlantic/control_plane/policy_gates.py`, `src/etlantic/control_plane/policy_memory.py`, `src/etlantic/control_plane/policy_opa.py` |
| `PMDATA101` | `src/etlantic/interchange/odcs.py`, `src/etlantic/validation/__init__.py` |
| `PMDATA102` | `src/etlantic/validation/__init__.py` |
| `PMDATA103` | `src/etlantic/validation/__init__.py` |
| `PMDATA201` | `src/etlantic/interchange/policy.py` |
| `PMDATA202` | `src/etlantic/interchange/policy.py` |
| `PMDATA301` | `src/etlantic/interchange/diff.py` |
| `PMDATA302` | `src/etlantic/interchange/diff.py` |
| `PMDF000` | `src/etlantic/runtime/orchestrator.py` |
| `PMDF410` | `src/etlantic/dataframe/helpers.py` |
| `PMDLQ100` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ110` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ120` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ121` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ130` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ140` | `src/etlantic/streaming/diagnostics.py` |
| `PMDLQ999` | `src/etlantic/streaming/diagnostics.py` |
| `PMDYN100` | `src/etlantic/streaming/diagnostics.py` |
| `PMDYN101` | `src/etlantic/streaming/diagnostics.py` |
| `PMDYN110` | `src/etlantic/streaming/diagnostics.py` |
| `PMDYN120` | `src/etlantic/streaming/diagnostics.py` |
| `PMDYN130` | `src/etlantic/orchestration/compile.py`, `src/etlantic/streaming/diagnostics.py` |
| `PMDYN999` | `src/etlantic/streaming/diagnostics.py` |
| `PMEXEC100` | `src/etlantic/runtime/execute.py` |
| `PMEXEC300` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC301` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC310` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC320` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC321` | `src/etlantic/runtime/dataframe_exec.py`, `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC330` | `src/etlantic/runtime/dataframe_exec.py`, `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC340` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC350` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC351` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC353` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC400` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC401` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/secrets/env.py` |
| `PMEXEC402` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/secrets/file.py` |
| `PMEXEC408` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC409` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC410` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC411` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC412` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC413` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC414` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC415` | `src/etlantic/storage/callable_binding.py` |
| `PMEXEC416` | `src/etlantic/storage/callable_binding.py` |
| `PMEXEC420` | `src/etlantic/runtime/dataframe_exec.py` |
| `PMEXEC421` | `src/etlantic/runtime/dataframe_exec.py` |
| `PMEXEC422` | `src/etlantic/runtime/dataframe_exec.py` |
| `PMEXEC423` | `src/etlantic/runtime/dataframe_exec.py` |
| `PMEXEC430` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC431` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC432` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC433` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC434` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC436` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC437` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC440` | `src/etlantic/runtime/spark_exec.py` |
| `PMEXEC441` | `src/etlantic/runtime/spark_exec.py` |
| `PMEXEC450` | `src/etlantic/storage/json_binding.py` |
| `PMEXEC451` | `src/etlantic/storage/json_binding.py` |
| `PMEXEC452` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/storage/json_binding.py` |
| `PMEXEC453` | `src/etlantic/storage/csv_binding.py` |
| `PMEXEC454` | `src/etlantic/storage/csv_binding.py` |
| `PMEXEC455` | `src/etlantic/runtime/sql_exec.py`, `src/etlantic/storage/csv_binding.py` |
| `PMEXEC456` | `src/etlantic/runtime/sql_exec.py`, `src/etlantic/storage/memory.py` |
| `PMEXEC500` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC501` | `src/etlantic/reliability_runtime.py` |
| `PMEXEC502` | `src/etlantic/reliability_runtime.py` |
| `PMFED100` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED101` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED110` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED120` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED130` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED140` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFED999` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE100` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE110` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE120` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE130` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE140` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE150` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMFIRE999` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMGEN201` | `src/etlantic/interchange/policy.py` |
| `PMGEN202` | `src/etlantic/interchange/policy.py` |
| `PMGEN203` | `src/etlantic/interchange/diff.py`, `src/etlantic/interchange/dtcs.py` |
| `PMGEN204` | `src/etlantic/interchange/dtcs.py` |
| `PMGEN205` | `src/etlantic/interchange/dtcs.py` |
| `PMGEN206` | `src/etlantic/interchange/dtcs.py` |
| `PMGEN211` | `src/etlantic/interchange/policy.py` |
| `PMGEN212` | `src/etlantic/interchange/policy.py` |
| `PMGEN213` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN214` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN215` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN216` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN217` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN218` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN220` | `src/etlantic/interchange/dpcs.py` |
| `PMGEN230` | `src/etlantic/interchange/bundle.py` |
| `PMGEN231` | `src/etlantic/interchange/bundle.py` |
| `PMGEN232` | `src/etlantic/interchange/bundle.py` |
| `PMGEN233` | `src/etlantic/interchange/bundle.py` |
| `PMGEN301` | `src/etlantic/interchange/diff.py` |
| `PMGEN311` | `src/etlantic/interchange/diff.py` |
| `PMID001` | `src/etlantic/ide/analysis/index.py` |
| `PMID002` | `src/etlantic/ide/analysis/index.py` |
| `PMOPT100` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT101` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT102` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT110` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT111` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT112` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT120` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT121` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT130` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT140` | `src/etlantic/optimization/diagnostics.py`, `src/etlantic/testing/optimizer_conformance.py` |
| `PMOPT141` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT150` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT160` | `src/etlantic/optimization/diagnostics.py` |
| `PMOPT999` | `src/etlantic/optimization/diagnostics.py` |
| `PMORCH300` | `src/etlantic/orchestration/compile.py` |
| `PMORCH301` | `src/etlantic/orchestration/compile.py` |
| `PMORCH310` | `src/etlantic/orchestration/reliability.py` |
| `PMORCH340` | `src/etlantic/orchestration/artifacts.py` |
| `PMORCH341` | `src/etlantic/orchestration/artifacts.py` |
| `PMORCH342` | `src/etlantic/orchestration/artifacts.py` |
| `PMORCH400` | `src/etlantic/orchestration/lifecycle.py` |
| `PMPIPE110` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
| `PMPIPE201` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
| `PMPIPE210` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
| `PMPIPE220` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
| `PMPIPE301` | `src/etlantic/validation/__init__.py` |
| `PMPIPE302` | `src/etlantic/validation/__init__.py` |
| `PMPLAN201` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
| `PMPLAN202` | `src/etlantic/validation/__init__.py` |
| `PMPLAN301` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/plan/planner.py`, `src/etlantic/validation/__init__.py` |
| `PMPLAN302` | `src/etlantic/plan/planner.py` |
| `PMPLAN401` | `src/etlantic/validation/phases/capability.py` |
| `PMPLAN402` | `src/etlantic/validation/phases/capability.py` |
| `PMPLAN403` | `src/etlantic/validation/phases/capability.py` |
| `PMPLAN410` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN411` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN412` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN413` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN414` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN415` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN420` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN421` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN430` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN431` | `src/etlantic/planning/capabilities.py`, `src/etlantic/runtime/orchestrator.py` |
| `PMPLAN440` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN441` | `src/etlantic/planning/capabilities.py` |
| `PMPLAN501` | `src/etlantic/plan/planner.py` |
| `PMPLUG401` | `src/etlantic/cli/cmds/profile.py`, `src/etlantic/lifecycle/runtime.py`, `src/etlantic/plugin_lifecycle/policies.py` |
| `PMPLUG402` | `src/etlantic/lifecycle/runtime.py`, `src/etlantic/plugin_lifecycle/policies.py`, `src/etlantic/plugin_trust.py` |
| `PMPLUG403` | `src/etlantic/plugin_lifecycle/policies.py`, `src/etlantic/plugin_trust.py` |
| `PMPLUG404` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/validation/phases/plugin_trust.py` |
| `PMPLUG410` | `src/etlantic/plugin_manifest.py` |
| `PMPLUG411` | `src/etlantic/plugin_manifest.py` |
| `PMPLUG412` | `src/etlantic/plugin_compatibility.py`, `src/etlantic/plugin_manifest.py` |
| `PMPLUG413` | `src/etlantic/plugin_compatibility.py`, `src/etlantic/plugin_lifecycle/__init__.py`, `src/etlantic/plugin_manifest.py` |
| `PMPLUG414` | `src/etlantic/plugin_manifest.py` |
| `PMPLUG415` | `src/etlantic/plugin_manifest.py` |
| `PMPLUG416` | `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG417` | `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG418` | `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG419` | `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG420` | `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG421` | `src/etlantic/plugins/coordinator.py` |
| `PMPLUG422` | `src/etlantic/plugins/coordinator.py` |
| `PMPLUG423` | `src/etlantic/plugins/coordinator.py` |
| `PMPLUG424` | `src/etlantic/plugin_lifecycle/__init__.py`, `src/etlantic/plugins/coordinator.py` |
| `PMPLUG430` | `src/etlantic/capability_probe.py` |
| `PMPLUG431` | `src/etlantic/capability_probe.py` |
| `PMPLUG432` | `src/etlantic/capability_probe.py`, `src/etlantic/plugin_lifecycle/__init__.py` |
| `PMPLUG440` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG441` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG442` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG443` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG444` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG445` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG446` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG447` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG448` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG449` | `src/etlantic/plugin_compatibility.py` |
| `PMPLUG450` | `src/etlantic/plugin_compatibility.py` |
| `PMQTY400` | `src/etlantic/quality/evaluate.py` |
| `PMQTY410` | `src/etlantic/quality/evaluate.py` |
| `PMREG100` | `src/etlantic/cli/cmds/stream.py`, `src/etlantic/streaming/diagnostics.py` |
| `PMREG101` | `src/etlantic/streaming/diagnostics.py` |
| `PMREG102` | `src/etlantic/streaming/diagnostics.py` |
| `PMREG110` | `src/etlantic/cli/cmds/stream.py`, `src/etlantic/streaming/diagnostics.py` |
| `PMREG140` | `src/etlantic/cli/cmds/stream.py`, `src/etlantic/streaming/diagnostics.py` |
| `PMREG150` | `src/etlantic/streaming/diagnostics.py` |
| `PMREG999` | `src/etlantic/streaming/diagnostics.py` |
| `PMRES100` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMRES110` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMRES140` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMRES999` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMSCHED101` | `src/etlantic/runtime/scheduler.py` |
| `PMSCHED102` | `src/etlantic/runtime/scheduler.py`, `src/etlantic/testing/scheduler.py` |
| `PMSEC050` | `src/etlantic/outbound.py` |
| `PMSEC051` | `src/etlantic/outbound.py` |
| `PMSEC060` | `src/etlantic/serialization_policy.py` |
| `PMSPARK000` | `src/etlantic/runtime/orchestrator.py` |
| `PMSPARK220` | `src/etlantic/spark/schema.py` |
| `PMSPARK221` | `src/etlantic/spark/schema.py` |
| `PMSPARK310` | `src/etlantic/runtime/spark_exec.py` |
| `PMSPARK311` | `src/etlantic/runtime/spark_exec.py` |
| `PMSPARK320` | `src/etlantic/runtime/spark_exec.py` |
| `PMSPARK330` | `src/etlantic/runtime/spark_exec.py` |
| `PMSPARK331` | `src/etlantic/runtime/spark_exec.py` |
| `PMSQL000` | `src/etlantic/runtime/orchestrator.py` |
| `PMSQL440` | `src/etlantic/runtime/sql_exec.py` |
| `PMSRC101` | `src/etlantic/interchange/security.py`, `src/etlantic/io_policy.py` |
| `PMSRC102` | `src/etlantic/interchange/security.py`, `src/etlantic/io_policy.py` |
| `PMSRC103` | `src/etlantic/interchange/security.py`, `src/etlantic/io_policy.py` |
| `PMSRC104` | `src/etlantic/interchange/bundle.py` |
| `PMSRC110` | `src/etlantic/io_policy.py` |
| `PMSRC111` | `src/etlantic/io_policy.py` |
| `PMSRC112` | `src/etlantic/io_policy.py` |
| `PMSRC113` | `src/etlantic/io_policy.py` |
| `PMSTR100` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR110` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR200` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR201` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR210` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR300` | `src/etlantic/streaming/diagnostics.py` |
| `PMSTR999` | `src/etlantic/streaming/diagnostics.py` |
| `PMSVC100` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMSVC101` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMSVC110` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMSVC120` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMSVC999` | `src/etlantic/control_plane/schedule_diagnostics.py` |
| `PMTRN001` | `src/etlantic/validation/__init__.py` |
| `PMTRN101` | `src/etlantic/validation/__init__.py` |
| `PMTRN102` | `src/etlantic/validation/__init__.py` |
| `PMXFORM201` | `src/etlantic/transform/validate.py` |
| `PMXFORM202` | `src/etlantic/transform/validate.py` |
| `PMXFORM301` | `src/etlantic/plan/planner.py`, `src/etlantic/transform/capabilities.py`, `src/etlantic/validation/__init__.py` |
| `PMXFORM302` | `src/etlantic/plan/planner.py`, `src/etlantic/runtime/dataframe_exec.py`, `src/etlantic/runtime/orchestrator.py` |
| `PMXFORM501` | `src/etlantic/runtime/dataframe_exec.py`, `src/etlantic/runtime/spark_exec.py` |
| `PMXFORM801` | `src/etlantic/transform/validate.py` |
| `PMXFORM802` | `src/etlantic/transform/validate.py` |
| `PMXFORM803` | `src/etlantic/transform/validate.py` |
| `PMXFORM810` | `src/etlantic/transform/validate.py` |
| `PMXFORM811` | `src/etlantic/transform/validate.py` |
| `PMXFORM812` | `src/etlantic/transform/validate.py` |
