"""CLI command implementations for ETLantic 0.9 surfaces."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.cmds.compile import register_compile_commands
from etlantic.cli.cmds.context import emit_payload, report_to_payload
from etlantic.cli.context import get_cli_context
from etlantic.plan.planner import plan_pipeline_with_report
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

_LOG = logging.getLogger(__name__)


def register_commands(
    app: typer.Typer,
    *,
    context_factory: Any,
) -> None:
    """Attach 0.9 CLI commands onto the root Typer app."""

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
        ctx: typer.Context,
        profile: str | None = typer.Option(None, "--profile", "-p"),
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

        resolved, _ = get_cli_context(ctx).resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
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
            raise typer.Exit(ec.TRUST_FAILURE)

    @plugin_app.command("info")
    def plugin_info_cmd(
        ctx: typer.Context,
        engine: str = typer.Argument(..., help="Plugin engine name"),
        kind: str = typer.Option("dataframe", "--kind"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Show details for one discovered plugin."""
        resolved, _ = get_cli_context(ctx).resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
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
            raise typer.Exit(ec.GENERAL_FAILURE)

        plugin = plugins.get(engine)
        if plugin is None:
            emit_payload({"ok": False, "error": f"Unknown plugin {engine!r}"}, fmt=fmt)
            raise typer.Exit(ec.GENERAL_FAILURE)
        info = getattr(plugin, "info", None)
        payload = (
            info.to_dict()
            if info is not None and hasattr(info, "to_dict")
            else {"engine": engine}
        )
        emit_payload(payload, fmt=fmt)

    @plugin_app.command("compatibility")
    def plugin_compatibility_cmd(
        ctx: typer.Context,
        plugins: list[str] | None = typer.Argument(  # noqa: B008
            None,
            help=(
                "Installed plugin package names (e.g. etlantic-polars). "
                "When omitted, report all packages that ship an "
                "etlantic-plugin-manifest.json."
            ),
        ),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option(
            "json",
            "--format",
            help="json|human",
        ),
    ) -> None:
        """Report protocol/vocabulary/pin compatibility for installed plugins."""
        from etlantic.plugin_compatibility import (
            build_compatibility_report,
            render_compatibility_human,
        )
        from etlantic.plugin_manifest import read_distribution_manifest_text

        resolved, _ = get_cli_context(ctx).resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
        allowlist = dict(resolved.plugin_allowlist) if resolved is not None else None
        package_names = list(plugins or [])
        if not package_names:
            from importlib.metadata import distributions

            for dist in distributions():
                try:
                    if read_distribution_manifest_text(dist) is not None:
                        package_names.append(str(dist.metadata["Name"]))
                except Exception as exc:
                    _LOG.debug(
                        "Skipping distribution during plugin compatibility scan: %s",
                        exc,
                    )
                    continue
            package_names = sorted(set(package_names), key=str.lower)
        report = build_compatibility_report(package_names, allowlist=allowlist)
        if fmt == "human":
            typer.echo(render_compatibility_human(report))
        else:
            emit_payload(report.to_dict(), fmt="json")
        if not report.ok:
            raise typer.Exit(ec.ENVIRONMENT_FAILURE)

    def _history_root(ctx: typer.Context, path: str | None) -> Path:
        if path:
            return Path(path)
        return get_cli_context(ctx).workspace().schema_history

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
        ctx: typer.Context,
        target: str = typer.Argument(...),
        subject_id: str = typer.Option(..., "--subject"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        model = load_target(target)
        provider = FileSchemaHistoryProvider(
            _history_root(ctx, history), fail_closed=True
        )
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
            raise typer.Exit(ec.BREAKING_CHANGE)

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
        raise typer.Exit(
            ec.BREAKING_CHANGE
            if change_set.overall_impact.value == "breaking"
            else ec.SUCCESS
        )

    @schema_app.command("history")
    def schema_history_cmd(
        ctx: typer.Context,
        subject_id: str = typer.Argument(...),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        provider = FileSchemaHistoryProvider(
            _history_root(ctx, history), fail_closed=True
        )
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
        ctx: typer.Context,
        subject_id: str = typer.Argument(...),
        note: str | None = typer.Option(None, "--note"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        provider = FileSchemaHistoryProvider(
            _history_root(ctx, history), fail_closed=True
        )
        emit_payload(provider.acknowledge(subject_id, note=note), fmt=fmt)

    @schema_app.command("propose")
    def schema_propose_cmd(
        ctx: typer.Context,
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
            raise typer.Exit(ec.GENERAL_FAILURE)
        emit_payload(
            {
                "ok": True,
                "proposal": obs.to_dict(),
                "history_root": str(_history_root(ctx, history)),
                "note": "Call schema monitor/record separately; contracts are unchanged.",
            },
            fmt=fmt,
        )

    @schema_app.command("monitor")
    def schema_monitor_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(...),
        subject_id: str = typer.Option(..., "--subject"),
        history: str | None = typer.Option(None, "--history"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Record a schema observation into file history (no source rows)."""
        model = load_target(target)
        provider = FileSchemaHistoryProvider(
            _history_root(ctx, history), fail_closed=True
        )
        obs = observe_model_schema(subject_id, model, layer="current")
        if obs is None:
            emit_payload({"ok": False, "error": "No schema observed"}, fmt=fmt)
            raise typer.Exit(ec.GENERAL_FAILURE)
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
        raise typer.Exit(ec.SUCCESS if result.ok else ec.GENERAL_FAILURE)

    @reliability_app.command("partition-check")
    def partition_check_cmd(
        subject_id: str = typer.Argument(...),
        keys: str = typer.Option(..., "--keys", help="Comma-separated partition keys"),
        observed: str = typer.Option(
            ...,
            "--observed",
            help="Comma-separated observed partition ids (required evidence)",
        ),
        expected: str = typer.Option(
            "",
            "--expected",
            help="Optional comma-separated expected partition ids",
        ),
        minimum_count: int = typer.Option(1, "--minimum-count"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        from etlantic.reliability import PartitionCompletenessExpectation
        from etlantic.reliability_runtime import check_partition_completeness

        partition_keys = tuple(k.strip() for k in keys.split(",") if k.strip())
        observed_partitions = {
            part.strip() for part in observed.split(",") if part.strip()
        }
        if not observed_partitions:
            emit_payload(
                {
                    "ok": False,
                    "error": "partition-check requires non-empty --observed evidence",
                    "subject_id": subject_id,
                },
                fmt=fmt,
            )
            raise typer.Exit(ec.GENERAL_FAILURE)
        expectation = PartitionCompletenessExpectation(
            subject_id=subject_id,
            partition_keys=partition_keys,
            minimum_count=minimum_count,
        )
        expected_partitions = {
            part.strip() for part in expected.split(",") if part.strip()
        }
        ok, reason = check_partition_completeness(
            expectation,
            observed_partitions=observed_partitions,
            expected_partitions=expected_partitions or None,
        )
        emit_payload(
            {
                "ok": ok,
                "reason": reason,
                "expectation": expectation.to_dict(),
                "observed_partitions": sorted(observed_partitions),
                "expected_partitions": sorted(expected_partitions) or None,
            },
            fmt=fmt,
        )
        raise typer.Exit(ec.SUCCESS if ok else ec.GENERAL_FAILURE)

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
        raise typer.Exit(
            ec.SUCCESS if evidence.status == "matched" else ec.GENERAL_FAILURE
        )

    @reliability_app.command("plan-diff")
    def plan_diff_cmd(
        ctx: typer.Context,
        left_target: str = typer.Argument(...),
        right_target: str = typer.Argument(...),
        profile: str | None = typer.Option(None, "--profile", "-p"),
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
        resolved, _ = cli.resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
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
            raise typer.Exit(ec.PLANNING_FAILURE)
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

    @reliability_app.command(
        "quality-trends",
        help="Preview-only trend summary from inline --values samples.",
    )
    def quality_trends_cmd(
        subject_id: str = typer.Argument(...),
        values: str = typer.Option(
            "",
            "--values",
            help="Comma-separated metric samples (required for preview)",
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        if not values.strip():
            emit_payload(
                {
                    "ok": False,
                    "error": (
                        "quality-trends is preview-only and requires --values "
                        "(comma-separated metric samples); refusing empty summary"
                    ),
                    "subject_id": subject_id,
                },
                fmt=fmt,
            )
            raise typer.Exit(ec.GENERAL_FAILURE)
        samples = [float(x) for x in values.split(",") if x.strip()]
        if not samples:
            emit_payload(
                {
                    "ok": False,
                    "error": "quality-trends requires at least one numeric sample",
                    "subject_id": subject_id,
                },
                fmt=fmt,
            )
            raise typer.Exit(ec.GENERAL_FAILURE)
        mean = sum(samples) / len(samples)
        payload = {
            "ok": True,
            "subject_id": subject_id,
            "n": len(samples),
            "mean": mean,
            "min": min(samples),
            "max": max(samples),
            "source": "inline",
            "preview_only": True,
        }
        emit_payload(payload, fmt=fmt)

    @viz_app.command("dot")
    def viz_dot_cmd(
        target: str = typer.Argument(...),
        output: str | None = typer.Option(None, "--output", "-o"),
    ) -> None:
        from etlantic.authoring.lifecycle import inspect_pipeline_like

        graph = inspect_pipeline_like(load_target(target))
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
        from etlantic.authoring.lifecycle import inspect_pipeline_like

        graph = inspect_pipeline_like(load_target(target))
        html = graph_to_html(logical_graph_to_ir(graph))
        Path(output).write_text(html, encoding="utf-8")
        typer.echo(f"Wrote {output}")

    @viz_app.command("lineage")
    def viz_lineage_cmd(
        target: str = typer.Argument(...),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        from etlantic.authoring.lifecycle import inspect_pipeline_like

        graph = inspect_pipeline_like(load_target(target))
        emit_payload(lineage_export(logical_graph_to_ir(graph)), fmt=fmt)
