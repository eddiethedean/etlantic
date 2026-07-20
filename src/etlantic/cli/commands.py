"""CLI command implementations for ETLantic 0.9 surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from etlantic.cli.cmds.compile import register_compile_commands
from etlantic.cli.cmds.context import CliContext, emit_payload, report_to_payload
from etlantic.cli.context import get_cli_context
from etlantic.plan.planner import plan_pipeline_with_report
from etlantic.profile import resolve_profile
from etlantic.registry import PlanningContext
from etlantic.schema_drift import (
    diff_normalized_schemas,
    normalize_schema_from_model,
)
from etlantic.schema_history import FileSchemaHistoryProvider
from etlantic.schema_policy import observe_model_schema
from etlantic.viz import (
    graph_to_dot,
    graph_to_html,
    lineage_export,
    logical_graph_to_ir,
)


def register_commands(
    app: typer.Typer,
    *,
    context_factory: Any,
) -> None:
    """Attach 0.9 CLI commands onto the root Typer app."""

    def _ctx(ctx: typer.Context) -> CliContext:
        cli = get_cli_context(ctx)
        return cli

    def load_target(target: str) -> Any:
        return context_factory().load_target(target)

    def runtime(ctx: typer.Context | None = None) -> Any:
        if ctx is not None:
            return get_cli_context(ctx).runtime
        return context_factory().runtime

    plugin_app = typer.Typer(help="Inspect discovered plugins.")
    schema_app = typer.Typer(help="Schema drift and history operations.")
    reliability_app = typer.Typer(help="Reliability operations.")
    viz_app = typer.Typer(help="Visualization and lineage exporters.")
    app.add_typer(plugin_app, name="plugin")
    app.add_typer(schema_app, name="schema")
    app.add_typer(reliability_app, name="reliability")
    app.add_typer(viz_app, name="viz")

    register_compile_commands(app, context_factory)

    @plugin_app.command("list")
    def plugin_list_cmd(
        profile: str = typer.Option("local", "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option("json", "--format"),
        kind: str = typer.Option(
            "all",
            "--kind",
            help="all|dataframe|sql|spark|orchestrator|scheduler|transform_compiler",
        ),
    ) -> None:
        """List discovered plugins (honors profile allowlist)."""
        from etlantic.dataframe.discovery import discover_dataframe_plugins
        from etlantic.orchestration.discovery import discover_orchestrator_plugins
        from etlantic.runtime.scheduler_discovery import (
            builtin_local_scheduler,
            discover_scheduler_plugins,
        )
        from etlantic.spark.discovery import discover_spark_plugins
        from etlantic.sql.discovery import discover_sql_plugins

        resolved = resolve_profile(profile, allow_adhoc_profile=allow_adhoc_profile)
        groups: dict[str, dict[str, Any]] = {}
        if kind in {"all", "dataframe"}:
            groups["dataframe"] = discover_dataframe_plugins(profile=resolved)
        if kind in {"all", "sql"}:
            groups["sql"] = discover_sql_plugins(profile=resolved)
        if kind in {"all", "spark"}:
            groups["spark"] = discover_spark_plugins(profile=resolved)
        if kind in {"all", "orchestrator"}:
            groups["orchestrator"] = discover_orchestrator_plugins(profile=resolved)
        if kind in {"all", "scheduler"}:
            sched = dict(discover_scheduler_plugins(profile=resolved))
            sched.setdefault("local", builtin_local_scheduler())
            groups["scheduler"] = sched
        if kind in {"all", "transform_compiler"}:
            from etlantic.transform.discovery import (
                discover_transform_compilers_for_profile,
            )

            groups["transform_compiler"] = discover_transform_compilers_for_profile(
                resolved
            )
        items: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for group_name, plugins in groups.items():
            for engine, plugin in plugins.items():
                info = getattr(plugin, "info", None)
                item: dict[str, Any] = {
                    "kind": group_name,
                    "engine": engine,
                    "name": getattr(info, "name", engine),
                    "version": getattr(info, "version", None),
                }
                if group_name == "transform_compiler" and info is not None:
                    caps = getattr(info, "capabilities", None)
                    item["compiler_protocol"] = getattr(info, "compiler_protocol", None)
                    item["dtcs_plan_versions"] = list(
                        getattr(info, "dtcs_plan_versions", ()) or ()
                    )
                    item["capabilities"] = (
                        caps.to_dict()
                        if caps is not None and hasattr(caps, "to_dict")
                        else None
                    )
                    item["runtime_engine"] = getattr(info, "engine", engine)
                items.append(item)
        emit_payload({"plugins": items, "diagnostics": diagnostics}, fmt=fmt)
        if any(d.get("severity") == "error" for d in diagnostics):
            raise typer.Exit(1)

    @plugin_app.command("info")
    def plugin_info_cmd(
        engine: str = typer.Argument(..., help="Plugin engine name"),
        kind: str = typer.Option("dataframe", "--kind"),
        profile: str = typer.Option("local", "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Show details for one discovered plugin."""
        resolved = resolve_profile(profile, allow_adhoc_profile=allow_adhoc_profile)
        plugins: dict[str, Any] = {}
        if kind == "dataframe":
            from etlantic.dataframe.discovery import discover_dataframe_plugins

            plugins = discover_dataframe_plugins(profile=resolved)
        elif kind == "sql":
            from etlantic.sql.discovery import discover_sql_plugins

            plugins = discover_sql_plugins(profile=resolved)
        elif kind == "spark":
            from etlantic.spark.discovery import discover_spark_plugins

            plugins = discover_spark_plugins(profile=resolved)
        elif kind == "orchestrator":
            from etlantic.orchestration.discovery import discover_orchestrator_plugins

            plugins = discover_orchestrator_plugins(profile=resolved)
        elif kind == "scheduler":
            from etlantic.runtime.scheduler_discovery import (
                builtin_local_scheduler,
                discover_scheduler_plugins,
            )

            plugins = dict(discover_scheduler_plugins(profile=resolved))
            plugins.setdefault("local", builtin_local_scheduler())
        elif kind == "transform_compiler":
            from etlantic.transform.discovery import (
                discover_transform_compilers_for_profile,
            )

            plugins = discover_transform_compilers_for_profile(resolved)
        else:
            emit_payload(
                {
                    "ok": False,
                    "error": (
                        f"Unknown kind {kind!r}; expected dataframe|sql|spark|"
                        "orchestrator|scheduler|transform_compiler"
                    ),
                },
                fmt=fmt,
            )
            raise typer.Exit(1)

        plugin = plugins.get(engine)
        if plugin is None:
            emit_payload({"ok": False, "error": f"Unknown plugin {engine!r}"}, fmt=fmt)
            raise typer.Exit(1)
        info = getattr(plugin, "info", None)
        payload = (
            info.to_dict()
            if info is not None and hasattr(info, "to_dict")
            else {"engine": engine}
        )
        emit_payload(payload, fmt=fmt)

    def _history_root(path: str | None) -> Path:
        return Path(path or ".etlantic/schema-history")

    @schema_app.command("inspect")
    def schema_inspect_cmd(
        target: str = typer.Argument(..., help="module:Class data contract"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        model = load_target(target)
        schema = normalize_schema_from_model(model)
        emit_payload(schema.to_dict(), fmt=fmt)

    @schema_app.command("check")
    def schema_check_cmd(
        target: str = typer.Argument(...),
        subject_id: str = typer.Option(..., "--subject"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        model = load_target(target)
        provider = FileSchemaHistoryProvider(_history_root(history))
        current = observe_model_schema(subject_id, model, layer="current")
        previous = provider.latest(subject_id)
        change_set = None
        if previous is not None and current is not None:
            change_set = diff_normalized_schemas(previous.schema, current.schema)
        payload = {
            "subject_id": subject_id,
            "previous_fingerprint": (
                previous.schema.fingerprint() if previous else None
            ),
            "current_fingerprint": (current.schema.fingerprint() if current else None),
            "changes": change_set.to_dict() if change_set is not None else None,
        }
        emit_payload(payload, fmt=fmt)
        if change_set is not None and change_set.overall_impact.value == "breaking":
            raise typer.Exit(1)

    @schema_app.command("diff")
    def schema_diff_cmd(
        previous: str = typer.Argument(...),
        current: str = typer.Argument(...),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        left = normalize_schema_from_model(load_target(previous))
        right = normalize_schema_from_model(load_target(current))
        change_set = diff_normalized_schemas(left, right)
        emit_payload(change_set.to_dict(), fmt=fmt)
        raise typer.Exit(1 if change_set.overall_impact.value == "breaking" else 0)

    @schema_app.command("history")
    def schema_history_cmd(
        subject_id: str = typer.Argument(...),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        provider = FileSchemaHistoryProvider(_history_root(history))
        items = [o.to_dict() for o in provider.history(subject_id)]
        emit_payload({"subject_id": subject_id, "history": items}, fmt=fmt)

    @schema_app.command("impact")
    def schema_impact_cmd(
        previous: str = typer.Argument(...),
        current: str = typer.Argument(...),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        left = normalize_schema_from_model(load_target(previous))
        right = normalize_schema_from_model(load_target(current))
        change_set = diff_normalized_schemas(left, right)
        emit_payload(
            {
                "breaking": change_set.overall_impact.value == "breaking",
                "change_count": len(change_set.changes),
                "impact": change_set.to_dict(),
            },
            fmt=fmt,
        )

    @schema_app.command("acknowledge")
    def schema_ack_cmd(
        subject_id: str = typer.Argument(...),
        note: str | None = typer.Option(None, "--note"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        provider = FileSchemaHistoryProvider(_history_root(history))
        emit_payload(provider.acknowledge(subject_id, note=note), fmt=fmt)

    @schema_app.command("propose")
    def schema_propose_cmd(
        target: str = typer.Argument(...),
        subject_id: str = typer.Option(..., "--subject"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Propose recording a new observation (does not mutate contracts)."""
        model = load_target(target)
        obs = observe_model_schema(subject_id, model, layer="proposed")
        if obs is None:
            emit_payload({"ok": False, "error": "No schema observed"}, fmt=fmt)
            raise typer.Exit(1)
        emit_payload(
            {
                "ok": True,
                "proposal": obs.to_dict(),
                "history_root": str(_history_root(history)),
                "note": "Call schema monitor/record separately; contracts are unchanged.",
            },
            fmt=fmt,
        )

    @schema_app.command("monitor")
    def schema_monitor_cmd(
        target: str = typer.Argument(...),
        subject_id: str = typer.Option(..., "--subject"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Record a schema observation into file history (no source rows)."""
        model = load_target(target)
        provider = FileSchemaHistoryProvider(_history_root(history))
        obs = observe_model_schema(subject_id, model, layer="current")
        if obs is None:
            emit_payload({"ok": False, "error": "No schema observed"}, fmt=fmt)
            raise typer.Exit(1)
        provider.record(obs)
        emit_payload(
            {
                "ok": True,
                "subject_id": subject_id,
                "fingerprint": obs.schema.fingerprint(),
            },
            fmt=fmt,
        )

    @reliability_app.command("freshness")
    def freshness_cmd(
        subject_id: str = typer.Argument(...),
        max_age_seconds: float = typer.Option(3600, "--max-age"),
        observed_age_seconds: float | None = typer.Option(None, "--observed-age"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        from datetime import UTC, datetime, timedelta

        from etlantic.reliability import FreshnessExpectation
        from etlantic.reliability_runtime import check_freshness

        expectation = FreshnessExpectation(
            subject_id=subject_id, max_age_seconds=max_age_seconds
        )
        observed_at = None
        if observed_age_seconds is not None:
            observed_at = datetime.now(UTC) - timedelta(seconds=observed_age_seconds)
        result = check_freshness(expectation, observed_at=observed_at)
        emit_payload(
            {
                "subject_id": subject_id,
                "ok": result.ok,
                "expectation": expectation.to_dict(),
                "observed_age_seconds": result.age_seconds
                if result.age_seconds is not None
                else observed_age_seconds,
                "message": result.message,
            },
            fmt=fmt,
        )
        raise typer.Exit(0 if result.ok else 1)

    @reliability_app.command("partition-check")
    def partition_check_cmd(
        subject_id: str = typer.Argument(...),
        keys: str = typer.Option(..., "--keys", help="Comma-separated partition keys"),
        count: int = typer.Option(0, "--count"),
        minimum_count: int = typer.Option(1, "--minimum-count"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        from etlantic.reliability import PartitionCompletenessExpectation

        expectation = PartitionCompletenessExpectation(
            subject_id=subject_id,
            partition_keys=tuple(k.strip() for k in keys.split(",") if k.strip()),
            minimum_count=minimum_count,
        )
        ok = count >= (expectation.minimum_count or 0)
        emit_payload(
            {
                "ok": ok,
                "expectation": expectation.to_dict(),
                "count": count,
            },
            fmt=fmt,
        )
        raise typer.Exit(0 if ok else 1)

    @reliability_app.command("repair-explain")
    def repair_explain_cmd(
        subject_id: str = typer.Argument(...),
        reason: str = typer.Option("unknown", "--reason"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        emit_payload(
            {
                "subject_id": subject_id,
                "reason": reason,
                "actions": [
                    "inspect latest run report",
                    "diff plan fingerprints",
                    "preview backfill window",
                    "reconcile counts before rewrite",
                ],
            },
            fmt=fmt,
        )

    @reliability_app.command("backfill-preview")
    def backfill_preview_cmd(
        subject_id: str = typer.Argument(...),
        start: str = typer.Option(..., "--start"),
        end: str = typer.Option(..., "--end"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        emit_payload(
            {
                "subject_id": subject_id,
                "window": {"start": start, "end": end},
                "write_mode": "idempotent_replace_partitions",
                "preview_only": True,
            },
            fmt=fmt,
        )

    @reliability_app.command("reconcile")
    def reconcile_cmd(
        subject_id: str = typer.Argument(...),
        left_count: int = typer.Option(..., "--left"),
        right_count: int = typer.Option(..., "--right"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        from etlantic.reliability_providers import (
            InMemoryReconciliationEvidence,
            ReconciliationEvidence,
        )

        evidence = ReconciliationEvidence(
            subject_id=subject_id,
            left_count=left_count,
            right_count=right_count,
            matched=min(left_count, right_count),
            mismatched=abs(left_count - right_count),
            status="matched" if left_count == right_count else "mismatched",
        )
        store = InMemoryReconciliationEvidence()
        store.put(evidence)
        emit_payload(evidence.to_dict(), fmt=fmt)
        raise typer.Exit(0 if evidence.status == "matched" else 1)

    @reliability_app.command("plan-diff")
    def plan_diff_cmd(
        ctx: typer.Context,
        left_target: str = typer.Argument(...),
        right_target: str = typer.Argument(...),
        profile: str = typer.Option("local", "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Deprecated: use ``etlantic plan diff`` instead."""
        import warnings

        warnings.warn(
            "reliability plan-diff is deprecated; use `etlantic plan diff`",
            DeprecationWarning,
            stacklevel=2,
        )
        cli = get_cli_context(ctx)
        resolved = resolve_profile(profile, allow_adhoc_profile=allow_adhoc_profile)
        context = PlanningContext.create(
            profile=resolved, registry=cli.runtime.registry
        )
        left_plan, left_report = plan_pipeline_with_report(
            load_target(left_target), context=context
        )
        right_plan, right_report = plan_pipeline_with_report(
            load_target(right_target), context=context
        )
        if left_plan is None or right_plan is None:
            emit_payload(
                {
                    "ok": False,
                    "left": report_to_payload(left_report),
                    "right": report_to_payload(right_report),
                },
                fmt=fmt,
            )
            raise typer.Exit(1)
        emit_payload(
            {
                "ok": True,
                "left_fingerprint": left_plan.fingerprint,
                "right_fingerprint": right_plan.fingerprint,
                "equal": left_plan.fingerprint == right_plan.fingerprint,
            },
            fmt=fmt,
        )

    @reliability_app.command("env-diff")
    def env_diff_cmd(
        left: str = typer.Option(..., "--left", help="JSON inventory path"),
        right: str = typer.Option(..., "--right", help="JSON inventory path"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        left_data = json.loads(Path(left).read_text(encoding="utf-8"))
        right_data = json.loads(Path(right).read_text(encoding="utf-8"))
        left_names = {item.get("name") for item in left_data.get("items", [])}
        right_names = {item.get("name") for item in right_data.get("items", [])}
        emit_payload(
            {
                "only_left": sorted(left_names - right_names),
                "only_right": sorted(right_names - left_names),
                "shared": sorted(left_names & right_names),
            },
            fmt=fmt,
        )

    @reliability_app.command("quality-trends")
    def quality_trends_cmd(
        subject_id: str = typer.Argument(...),
        values: str = typer.Option(
            "", "--values", help="Comma-separated metric samples"
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        samples = [float(x) for x in values.split(",") if x.strip()]
        mean = sum(samples) / len(samples) if samples else None
        emit_payload(
            {
                "subject_id": subject_id,
                "n": len(samples),
                "mean": mean,
                "min": min(samples) if samples else None,
                "max": max(samples) if samples else None,
            },
            fmt=fmt,
        )

    @viz_app.command("dot")
    def viz_dot_cmd(
        target: str = typer.Argument(...),
        output: str | None = typer.Option(None, "--output", "-o"),
    ) -> None:
        graph = load_target(target).inspect()
        text = graph_to_dot(logical_graph_to_ir(graph))
        if output:
            Path(output).write_text(text, encoding="utf-8")
            typer.echo(f"Wrote {output}")
        else:
            typer.echo(text, nl=False)

    @viz_app.command("html")
    def viz_html_cmd(
        target: str = typer.Argument(...),
        output: str = typer.Option("lineage.html", "--output", "-o"),
    ) -> None:
        graph = load_target(target).inspect()
        html = graph_to_html(logical_graph_to_ir(graph))
        Path(output).write_text(html, encoding="utf-8")
        typer.echo(f"Wrote {output}")

    @viz_app.command("lineage")
    def viz_lineage_cmd(
        target: str = typer.Argument(...),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        graph = load_target(target).inspect()
        emit_payload(lineage_export(logical_graph_to_ir(graph)), fmt=fmt)
