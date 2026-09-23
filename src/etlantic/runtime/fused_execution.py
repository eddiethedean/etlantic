# pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""One admitted source/filter/project invocation with owned native lifetime."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

import anyio

from etlantic.exceptions import NodeExecutionError
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
)
from etlantic.transform.fusion import FusionDescriptor


class _FusedTimeout(Exception):
    """Carry a deadline through providers that sanitize OSError on scope exit."""


@contextmanager
def _timeout_boundary(scan_context: Any):
    with scan_context as scan:
        try:
            yield scan
        except TimeoutError:
            # TimeoutError is an OSError. Do not let source cleanup misclassify
            # a query deadline as a source-open error or retain native payloads.
            raise _FusedTimeout("Fused execution timed out") from None


async def execute_fused_scan(
    descriptor: FusionDescriptor,
    *,
    compiler: Any,
    source: Any,
    context: Mapping[str, Any],
    pipeline_id: str,
    plan_id: str,
    profile_name: str,
    run_id: str,
    native: Any,
) -> tuple[Any, dict[str, Any]]:
    """Return a private boundary frame only after the native worker succeeds."""
    # Initialize the optional Arrow registry before starting a fresh worker.
    from importlib import import_module

    import_module("pyarrow.parquet")

    def operation() -> tuple[Any, dict[str, Any]]:
        from polars.exceptions import PanicException

        from etlantic_polars.fusion import inspect_fusion_query, validate_fusion_schema
        from etlantic_polars.parquet_storage import SnapshotCleanupError

        try:
            with _timeout_boundary(
                source.open_scan(
                    location=descriptor.source_binding["location"], context=context
                )
            ) as scan:
                validate_fusion_schema(scan, descriptor.source_contract)
                try:
                    compiled = compiler.compile_fusion(
                        descriptor,
                        context=TransformCompileContext(
                            pipeline_id,
                            plan_id,
                            descriptor.members[0].logical_node,
                            profile_name,
                            "polars",
                        ),
                    )
                except TimeoutError:
                    raise
                except (Exception, PanicException):
                    raise NodeExecutionError(
                        "Fused portable compilation failed",
                        node_name=descriptor.members[0].logical_node,
                        stage="transform",
                        code="PMADP520",
                    ) from None

                async def execute() -> Any:
                    return await compiler.execute(
                        compiled,
                        inputs={"fusion_source": scan},
                        parameters=descriptor.parameters,
                        context=TransformExecutionContext(
                            run_id,
                            pipeline_id,
                            plan_id,
                            descriptor.members[0].logical_node,
                            "polars",
                            collect=False,
                        ),
                    )

                bundle = anyio.run(execute)
                query = bundle.valid[descriptor.members[-1].output_port]
                try:
                    validate_fusion_schema(
                        query, descriptor.members[-1].output_contract
                    )
                except TimeoutError:
                    raise
                except (Exception, PanicException):
                    raise NodeExecutionError(
                        "Fused projected schema failed",
                        node_name=descriptor.members[-1].logical_node,
                        stage="validate",
                        code="PMADP520",
                    ) from None
                proof = inspect_fusion_query(query, descriptor)
                if not proof["scan_predicate"] or not proof["scan_projection"]:
                    raise NodeExecutionError(
                        "Native scan did not realize the stored fusion",
                        node_name=descriptor.members[
                            0 if not proof["scan_predicate"] else -1
                        ].logical_node,
                        stage="transform",
                        code="PMADP520",
                    )
                result = query.collect()
                proof["main_collections"] += 1
                return result, proof
        except SnapshotCleanupError as exc:
            native.obligations.append(
                {
                    "unit_id": native.unit_id,
                    "member": descriptor.source_node,
                    "attempt": native.attempt,
                    "owner": "etlantic.polars-parquet.snapshot",
                    "operation": "snapshot_cleanup",
                    "cleanup_id": exc.cleanup_id,
                    "code": "PMADP523",
                }
            )
            raise NodeExecutionError(
                "Bounded snapshot cleanup requires reconciliation",
                node_name=descriptor.source_node,
                stage="cleanup",
                code="PMADP523",
            ) from None
        except NodeExecutionError:
            raise
        except _FusedTimeout:
            raise TimeoutError("Fused execution timed out") from None
        except TimeoutError:
            raise
        except (Exception, PanicException):
            # Native exceptions/explain strings may contain paths, rows, values
            # or provider text. Preserve the named boundary, not that payload.
            raise NodeExecutionError(
                "Bounded fused source/query failed",
                node_name=descriptor.source_node,
                stage="read",
                code="PMADP520",
            ) from None

    return await native.run(operation)
