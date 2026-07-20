"""Airflow reference orchestrator plugin for ETLantic 0.8."""

from __future__ import annotations

import json
from textwrap import dedent, indent
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.orchestration.mapping import dag_id_for_plan, map_plan_to_tasks
from etlantic.orchestration.protocol import (
    ORCHESTRATION_PROTOCOL_VERSION,
    CompilationContext,
    CompilationDiagnostic,
    CompiledOrchestrationArtifact,
    OrchestratorPluginInfo,
)
from etlantic.plan.model import PipelinePlan

__version__ = "0.21.0"


def create_plugin() -> AirflowOrchestratorPlugin:
    """Entry-point factory for ``etlantic.orchestrator_plugins``."""
    return AirflowOrchestratorPlugin()


class AirflowOrchestratorPlugin:
    """Compile a PipelinePlan into a deterministic Airflow DAG module."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="airflow",
            dataframe=False,
            orchestration=True,
            orch_scheduling=True,
            orch_retries=True,
            orch_timeouts=True,
            orch_parallel=True,
            orch_sensors=False,
            orch_artifacts_only_xcom=True,
            cancellation=True,
            extras=frozenset({"airflow_dag", "artifact_xcom"}),
        )
        self._info = OrchestratorPluginInfo(
            name="etlantic-airflow",
            engine="airflow",
            version=__version__,
            protocol_version=ORCHESTRATION_PROTOCOL_VERSION,
            capabilities=caps,
            metadata={"dag_format": "python_module"},
        )

    @property
    def info(self) -> OrchestratorPluginInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def compile(
        self,
        plan: PipelinePlan,
        *,
        context: CompilationContext,
    ) -> CompiledOrchestrationArtifact:
        diagnostics: list[CompilationDiagnostic] = []

        # Sensors are not supported in the 0.8 reference compiler.
        if context.schedule.type == "event":
            diagnostics.append(
                CompilationDiagnostic(
                    code="PMORCH320",
                    severity="error",
                    message=(
                        "Event-driven schedule intent requires sensors; "
                        "etlantic-airflow 0.8 does not preserve this semantic."
                    ),
                    subject_id="schedule",
                )
            )

        tasks, dep_map, map_diags = map_plan_to_tasks(plan, context=context)
        diagnostics.extend(map_diags)

        dag_id = dag_id_for_plan(plan)
        source = render_dag_module(
            plan=plan,
            dag_id=dag_id,
            tasks=tasks,
            context=context,
        )

        # Capability-loss: dynamic branching not supported.
        if any(
            (t.metadata or {}).get("dynamic_branching") for t in tasks
        ) or plan.metadata.get("dynamic_branching"):
            diagnostics.append(
                CompilationDiagnostic(
                    code="PMORCH321",
                    severity="error",
                    message=(
                        "Dynamic branching is not preserved by the Airflow "
                        "reference compiler; failing closed."
                    ),
                    subject_id=dag_id,
                )
            )

        return CompiledOrchestrationArtifact(
            target="airflow",
            dag_id=dag_id,
            protocol_version=ORCHESTRATION_PROTOCOL_VERSION,
            plan_id=plan.plan_id,
            pipeline_id=plan.pipeline_id,
            fingerprint=plan.fingerprint,
            tasks=tasks,
            dependencies={k: tuple(v) for k, v in dep_map.items()},
            schedule=context.schedule,
            execution=context.execution,
            source=source,
            diagnostics=tuple(diagnostics),
            metadata={
                "plugin": self.info.name,
                "plugin_version": self.info.version,
                "task_count": len(tasks),
            },
        )

    def explain(self, artifact: CompiledOrchestrationArtifact) -> dict[str, Any]:
        return artifact.explain()


def render_dag_module(
    *,
    plan: PipelinePlan,
    dag_id: str,
    tasks: tuple[Any, ...],
    context: CompilationContext,
) -> str:
    """Render a deterministic Airflow DAG Python module (no secrets)."""
    schedule = context.schedule
    execution = context.execution

    if schedule.type == "cron" and schedule.expression:
        schedule_arg = repr(schedule.expression)
    else:
        schedule_arg = "None"

    catchup = "True" if schedule.catchup else "False"
    max_active = (
        str(execution.max_active_runs) if execution.max_active_runs is not None else "1"
    )
    default_retries = int(execution.retries)
    retry_delay = float(execution.retry_delay_seconds)

    plan_meta = {
        "plan_id": plan.plan_id,
        "pipeline_id": plan.pipeline_id,
        "pipeline_name": plan.pipeline_name,
        "fingerprint": plan.fingerprint,
        "profile_name": plan.profile_name,
        "protocol_version": ORCHESTRATION_PROTOCOL_VERSION,
    }
    plan_meta_json = json.dumps(plan_meta, sort_keys=True, separators=(",", ":"))

    task_blocks: list[str] = []
    for task in tasks:
        retries = int(task.retries)
        if task.timeout_seconds is not None:
            timeout_expr = f"timedelta(seconds={int(task.timeout_seconds)})"
        elif execution.timeout_seconds is not None:
            timeout_expr = f"timedelta(seconds={int(execution.timeout_seconds)})"
        else:
            timeout_expr = "None"
        op_kwargs = {
            "plan_id": plan.plan_id,
            "pipeline_id": plan.pipeline_id,
            "node_name": task.node_name,
            "node_kind": task.node_kind,
            "artifact_outputs": [a.to_dict() for a in task.artifact_outputs],
            "write_intent": task.write_intent,
            "retry_policy": task.retry_policy.value,
        }
        op_kwargs_json = json.dumps(op_kwargs, sort_keys=True, separators=(",", ":"))
        task_blocks.append(
            dedent(
                f"""\
                {task.task_id} = PythonOperator(
                    task_id={task.task_id!r},
                    python_callable=_etlantic_step,
                    op_kwargs=json.loads({op_kwargs_json!r}),
                    retries={retries},
                    retry_delay=timedelta(seconds={retry_delay}),
                    execution_timeout={timeout_expr},
                )
                """
            ).rstrip()
        )

    dep_lines: list[str] = []
    for task in tasks:
        for upstream in task.dependencies:
            dep_lines.append(f"{upstream} >> {task.task_id}")

    body = dedent(
        f'''\
        """Auto-generated ETLantic Airflow DAG — do not edit by hand.

        Generated from PipelinePlan {plan.plan_id}
        Protocol: {ORCHESTRATION_PROTOCOL_VERSION}
        """

        from __future__ import annotations

        import json
        from datetime import datetime, timedelta

        from airflow import DAG
        from airflow.operators.python import PythonOperator

        from etlantic_airflow.operator import etlantic_step as _etlantic_step

        ETLANTIC_PLAN_META = json.loads({plan_meta_json!r})

        with DAG(
            dag_id={dag_id!r},
            description="ETLantic pipeline {plan.pipeline_name}",
            schedule={schedule_arg},
            start_date=datetime(2024, 1, 1),
            catchup={catchup},
            max_active_runs={max_active},
            default_args={{
                "owner": "etlantic",
                "retries": {default_retries},
                "retry_delay": timedelta(seconds={retry_delay}),
            }},
            tags=["etlantic", "generated"],
            params={{"etlantic": ETLANTIC_PLAN_META}},
        ) as dag:
        '''
    )

    indented_tasks = "\n\n".join(indent(block, "    ") for block in task_blocks)
    indented_deps = "\n".join(indent(line, "    ") for line in dep_lines)
    parts = [body.rstrip(), "", indented_tasks]
    if indented_deps:
        parts.extend(["", indented_deps])
    parts.append("")
    return "\n".join(parts)
