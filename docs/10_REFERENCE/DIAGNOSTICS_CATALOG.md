# Diagnostics catalog (generated)

> **Status: Available in ETLantic 0.25.1.** Machine-readable inventory of
> diagnostic code literals found under `src/etlantic`. Regenerate with:
>
> ```bash
> uv run python scripts/generate_diagnostics_catalog.py --markdown \
>   > docs/10_REFERENCE/DIAGNOSTICS_CATALOG.md
> ```
>
> Prefer the curated tables in [Diagnostics](DIAGNOSTICS.md) for human-oriented
> meanings. This page is the exhaustive code→source index.

| Code | Example source paths |
|---|---|
| `PMAUTH201` | `src/etlantic/authoring/lifecycle.py` |
| `PMAUTH410` | `src/etlantic/authoring/resolve.py` |
| `PMCFG200` | `src/etlantic/cli/cmds/profile.py` |
| `PMCFG201` | `src/etlantic/cli/cmds/profile.py` |
| `PMDATA101` | `src/etlantic/interchange/odcs.py`, `src/etlantic/validation/__init__.py` |
| `PMDATA102` | `src/etlantic/validation/__init__.py` |
| `PMDATA103` | `src/etlantic/validation/__init__.py` |
| `PMDATA201` | `src/etlantic/interchange/policy.py` |
| `PMDATA202` | `src/etlantic/interchange/policy.py` |
| `PMDATA301` | `src/etlantic/interchange/diff.py` |
| `PMDATA302` | `src/etlantic/interchange/diff.py` |
| `PMDF000` | `src/etlantic/runtime/orchestrator.py` |
| `PMDF410` | `src/etlantic/dataframe/helpers.py` |
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
| `PMEXEC400` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC401` | `src/etlantic/secrets/env.py` |
| `PMEXEC402` | `src/etlantic/secrets/file.py` |
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
| `PMEXEC432` | `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC433` | `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC434` | `src/etlantic/runtime/orchestrator.py`, `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC436` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC437` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC440` | `src/etlantic/runtime/spark_exec.py` |
| `PMEXEC441` | `src/etlantic/runtime/spark_exec.py` |
| `PMEXEC450` | `src/etlantic/storage/json_binding.py` |
| `PMEXEC451` | `src/etlantic/storage/json_binding.py` |
| `PMEXEC452` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC453` | `src/etlantic/storage/csv_binding.py` |
| `PMEXEC454` | `src/etlantic/storage/csv_binding.py` |
| `PMEXEC455` | `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC456` | `src/etlantic/runtime/sql_exec.py` |
| `PMEXEC500` | `src/etlantic/runtime/orchestrator.py` |
| `PMEXEC501` | `src/etlantic/reliability_runtime.py` |
| `PMEXEC502` | `src/etlantic/reliability_runtime.py` |
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
| `PMPLAN301` | `src/etlantic/authoring/lifecycle.py`, `src/etlantic/validation/__init__.py` |
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
| `PMPLAN501` | `src/etlantic/plan/planner.py` |
| `PMPLUG401` | `src/etlantic/cli/cmds/profile.py`, `src/etlantic/plugin_lifecycle/policies.py`, `src/etlantic/plugin_trust.py` |
| `PMPLUG402` | `src/etlantic/plugin_lifecycle/policies.py`, `src/etlantic/plugin_trust.py` |
| `PMPLUG403` | `src/etlantic/plugin_trust.py` |
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
| `PMPLUG421` | `src/etlantic/plugin_lifecycle/__init__.py`, `src/etlantic/plugins/coordinator.py` |
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
