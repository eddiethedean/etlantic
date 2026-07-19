"""Pipeline ↔ DPCS document adaptation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dpcs
import yaml

from etlantic.diagnostics import (
    Diagnostic,
    Severity,
    ValidationReport,
)
from etlantic.exceptions import ETLanticError, ModelDefinitionError
from etlantic.identity import (
    identity_slug,
    pipeline_id,
    published_contract_id,
    transformation_id,
)
from etlantic.interchange.diagnostics import map_toolkit_diagnostics
from etlantic.interchange.dtcs import (
    DtcsError,
    dtcs_filename,
    transformation_from_dtcs,
    transformation_to_dtcs,
)
from etlantic.interchange.odcs import load_data_contract, odcs_filename
from etlantic.interchange.policy import DEFAULT_DPCS_VERSION, check_dpcs_version
from etlantic.interchange.provenance import ArtifactProvenance, ProvenanceKind
from etlantic.interchange.security import read_text_bounded, resolve_safe_path
from etlantic.model import LogicalGraph, NodeKind
from etlantic.pipeline import Extract, Load
from etlantic.refs import OutputRef


class DpcsError(ETLanticError):
    """Raised when DPCS generation or loading fails."""

    def __init__(self, message: str, *, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()


def pipeline_to_dpcs(
    pipeline_cls: type[Any],
    *,
    data_locations: dict[str, str] | None = None,
    transform_locations: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a DPCS document dict from a Pipeline subclass."""
    from etlantic.pipeline import Pipeline

    if not isinstance(pipeline_cls, type) or not issubclass(pipeline_cls, Pipeline):
        raise ModelDefinitionError("to_dpcs requires a Pipeline subclass")

    report = pipeline_cls.validate()
    if not report.valid:
        raise DpcsError(
            "Cannot generate DPCS from an invalid pipeline.",
            report=report,
        )

    graph = pipeline_cls.build_graph()
    if any(node.kind is NodeKind.SUBPIPELINE for node in graph.nodes):
        raise DpcsError(
            "DPCS generation for nested subpipelines is not supported in 0.2.",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN220",
                        severity=Severity.ERROR,
                        message="Nested subpipelines cannot be emitted to DPCS yet.",
                        path=("pipeline", pipeline_cls.__name__),
                        help="Flatten the pipeline or wait for a later milestone.",
                    )
                ]
            ),
        )

    published_id = getattr(pipeline_cls, "__published_id__", None) or pipeline_id(
        pipeline_cls
    )
    published_version = getattr(pipeline_cls, "__published_version__", None) or "0.1.0"
    data_locations = dict(data_locations or {})
    transform_locations = dict(transform_locations or {})

    contract_references: list[dict[str, Any]] = []
    seen_refs: set[str] = set()

    def _add_odcs_ref(contract_type: type[Any] | None) -> str | None:
        if contract_type is None:
            return None
        cid = published_contract_id(contract_type) or identity_slug(
            str(contract_type.__name__)
        )
        ref_id = f"odcs:{cid}"
        if ref_id not in seen_refs:
            seen_refs.add(ref_id)
            location = data_locations.get(cid) or f"data/{odcs_filename(contract_type)}"
            contract_references.append(
                {"id": ref_id, "type": "odcs", "location": location}
            )
        return ref_id

    def _add_dtcs_ref(transform: type[Any]) -> str:
        tid = getattr(transform, "__published_id__", None) or transformation_id(
            transform
        )
        ref_id = f"dtcs:{tid}"
        if ref_id not in seen_refs:
            seen_refs.add(ref_id)
            location = transform_locations.get(str(tid)) or (
                f"transformations/{dtcs_filename(transform)}"
            )
            contract_references.append(
                {"id": ref_id, "type": "dtcs", "location": location}
            )
        return ref_id

    interface_inputs: list[dict[str, Any]] = []
    interface_outputs: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    data_flow: list[dict[str, Any]] = []

    members = pipeline_cls.__pipeline_members__
    for node in graph.nodes:
        if node.kind is NodeKind.SOURCE:
            ref = _add_odcs_ref(node.contract_type)
            interface_inputs.append(
                {
                    "id": node.name,
                    "name": node.name,
                    "contractRef": ref,
                    "purpose": f"Pipeline source '{node.name}'",
                    "etlantic:binding": node.binding,
                }
            )
        elif node.kind is NodeKind.SINK:
            ref = _add_odcs_ref(node.contract_type)
            interface_outputs.append(
                {
                    "id": node.name,
                    "name": node.name,
                    "contractRef": ref,
                    "purpose": f"Pipeline sink '{node.name}'",
                    "etlantic:binding": node.binding,
                }
            )
        elif node.kind is NodeKind.STEP:
            member = members[node.name]
            transform = member.transformation
            for port in transform.inputs():
                _add_odcs_ref(port.contract_type)
            for port in transform.outputs():
                _add_odcs_ref(port.contract_type)
            dtcs_ref = _add_dtcs_ref(transform)
            step_entry: dict[str, Any] = {
                "id": node.name,
                "type": "dtcs:transform",
                "contractRef": dtcs_ref,
                "inputs": [{"id": p.name} for p in transform.inputs()],
                "outputs": [{"id": p.name} for p in transform.outputs()],
            }
            if member.parameters:
                step_entry["parameters"] = [
                    {"id": key, "value": value}
                    for key, value in sorted(member.parameters.items())
                ]
            steps.append(step_entry)

    for edge in graph.edges:
        producer_node = graph.node_map()[edge.producer_node]
        consumer_node = graph.node_map()[edge.consumer_node]
        if producer_node.kind is NodeKind.SOURCE:
            src = f"interface.inputs.{edge.producer_node}"
        else:
            src = f"steps.{edge.producer_node}.outputs.{edge.producer_port}"
        if consumer_node.kind is NodeKind.SINK:
            dst = f"interface.outputs.{edge.consumer_node}"
        else:
            dst = f"steps.{edge.consumer_node}.inputs.{edge.consumer_port}"
        data_flow.append(
            {
                "from": src,
                "to": dst,
                "dataset": f"{edge.producer_node}.{edge.producer_port}",
            }
        )

    doc: dict[str, Any] = {
        "dpcsVersion": DEFAULT_DPCS_VERSION,
        "id": published_id,
        "name": pipeline_cls.__name__,
        "version": published_version,
        "interface": {
            "inputs": interface_inputs,
            "outputs": interface_outputs,
        },
        "contractReferences": sorted(contract_references, key=lambda item: item["id"]),
        "steps": steps,
        "graph": {"edges": []},
        "dataFlow": data_flow,
    }
    validation = validate_dpcs_document(doc)
    if not validation.valid:
        raise DpcsError(validation.errors[0].message, report=validation)
    return doc


def write_dpcs(pipeline_cls: type[Any], path: str | Path, **kwargs: Any) -> Path:
    """Write a Pipeline to a DPCS YAML file."""
    doc = pipeline_to_dpcs(pipeline_cls, **kwargs)
    resolved = resolve_safe_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(_stable_yaml(doc), encoding="utf-8")
    return resolved


def pipeline_from_dpcs(
    source: str | Path | dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    root: str | Path | None = None,
    class_name: str | None = None,
) -> type[Any]:
    """Load a DPCS artifact into a dynamic Pipeline subclass."""
    from etlantic.pipeline import Pipeline

    path_str: str | None = None
    base_dir: Path | None = Path(root).resolve() if root is not None else None
    if isinstance(source, dict):
        doc = dict(source)
    else:
        resolved, text = read_text_bounded(source, root=root)
        path_str = str(resolved)
        if base_dir is None:
            # Prefer the bundle root (parent of pipelines/) when present.
            base_dir = (
                resolved.parent.parent
                if resolved.parent.name == "pipelines"
                else resolved.parent
            )
        doc = dict(dpcs.parse_yaml_str(text))

    version_report = check_dpcs_version(doc.get("dpcsVersion"), path=("dpcs",))
    if not version_report.valid:
        raise DpcsError(version_report.errors[0].message, report=version_report)

    validation = validate_dpcs_document(doc, source_path=path_str)
    if not validation.valid:
        raise DpcsError(validation.errors[0].message, report=validation)

    local_registry = dict(registry or {})
    odcs_types, transform_types = _materialize_references(
        doc,
        registry=local_registry,
        base_dir=base_dir,
    )

    # Build step transformations and wiring from dataFlow.
    flow = list(doc.get("dataFlow") or [])
    step_bindings: dict[str, dict[str, Any]] = {
        str(step["id"]): {} for step in doc.get("steps") or []
    }
    sink_inputs: dict[str, Any] = {}
    source_nodes: dict[str, Extract] = {}

    for entry in doc.get("interface", {}).get("inputs") or []:
        name = str(entry["id"])
        contract = _resolve_odcs_type(entry.get("contractRef"), odcs_types)
        binding = entry.get("etlantic:binding") or name
        source_nodes[name] = Extract(
            asset=str(binding), contract_type=contract, _compat_warn=False
        )

    for item in flow:
        src = str(item["from"])
        dst = str(item["to"])
        producer = _parse_endpoint(
            src,
            source_nodes=source_nodes,
            transform_types=transform_types,
            step_defs={str(step["id"]): step for step in doc.get("steps") or []},
        )
        _apply_binding(
            dst, producer, step_bindings=step_bindings, sink_inputs=sink_inputs
        )

    namespace: dict[str, Any] = {
        "__module__": "etlantic.interchange.generated",
        "__published_id__": str(doc["id"]),
        "__published_version__": str(doc.get("version") or "0.1.0"),
        "__provenance__": ArtifactProvenance(
            kind=ProvenanceKind.DPCS,
            path=path_str,
            identity=str(doc["id"]),
            version=str(doc.get("version") or "0.1.0"),
        ),
    }
    annotations: dict[str, Any] = {}

    for name, source in source_nodes.items():
        namespace[name] = source
        if source.contract_type is not None:
            annotations[name] = Extract[source.contract_type]  # type: ignore[index]

    for step in doc.get("steps") or []:
        step_id = str(step["id"])
        transform = transform_types[str(step["contractRef"])]
        bindings = dict(step_bindings.get(step_id, {}))
        bindings.update(_step_parameter_values(step))
        namespace[step_id] = transform.step(**bindings)

    for entry in doc.get("interface", {}).get("outputs") or []:
        name = str(entry["id"])
        contract = _resolve_odcs_type(entry.get("contractRef"), odcs_types)
        producer = sink_inputs.get(name)
        if producer is None:
            raise DpcsError(
                f"Load {name!r} has no inbound data flow.",
                report=ValidationReport.from_diagnostics(
                    [
                        Diagnostic(
                            code="PMGEN213",
                            severity=Severity.ERROR,
                            message=f"Load {name!r} has no inbound data flow.",
                            path=("dpcs", "interface", "outputs", name),
                        )
                    ]
                ),
            )
        binding = entry.get("etlantic:binding") or name
        namespace[name] = Load(
            input=producer,
            asset=str(binding),
            contract_type=contract,
            _compat_warn=False,
        )
        if contract is not None:
            annotations[name] = Load[contract]  # type: ignore[index]

    namespace["__annotations__"] = annotations
    dynamic_name = class_name or _safe_class_name(str(doc.get("name") or doc["id"]))
    return type(dynamic_name, (Pipeline,), namespace)


def validate_dpcs_document(
    doc: dict[str, Any],
    *,
    source_path: str | None = None,
) -> ValidationReport:
    """Validate a DPCS document via the dpcs toolkit and version policy."""
    version_report = check_dpcs_version(doc.get("dpcsVersion"), path=("dpcs",))
    toolkit = dpcs.validate_yaml(_stable_yaml(doc))
    toolkit_report = map_toolkit_diagnostics(
        toolkit.get("diagnostics"),
        default_code="PMGEN214",
        source_path=source_path,
        path=("dpcs",),
    )
    return version_report.merge(toolkit_report)


def dpcs_filename(pipeline_cls: type[Any]) -> str:
    """Stable DPCS filename for a pipeline class."""
    published = getattr(pipeline_cls, "__published_id__", None) or pipeline_id(
        pipeline_cls
    )
    return f"{identity_slug(str(published))}.dpcs.yaml"


def graph_fingerprint(graph: LogicalGraph) -> tuple[Any, ...]:
    """Comparable fingerprint for logical-graph equivalence checks."""
    nodes = tuple(
        (
            node.name,
            node.kind.value,
            node.binding,
            node.transformation_id,
            tuple(
                (
                    port.name,
                    port.direction,
                    published_contract_id(port.contract_type)
                    if port.contract_type is not None
                    else port.contract_id,
                )
                for port in (*node.inputs, *node.outputs)
            ),
        )
        for node in graph.nodes
    )
    edges = tuple(
        (
            edge.producer_node,
            edge.producer_port,
            edge.consumer_node,
            edge.consumer_port,
        )
        for edge in graph.edges
    )
    return nodes, edges


def _materialize_references(
    doc: dict[str, Any],
    *,
    registry: dict[str, Any],
    base_dir: Path | None,
) -> tuple[dict[str, type[Any]], dict[str, type[Any]]]:
    odcs_types: dict[str, type[Any]] = {}
    transform_types: dict[str, type[Any]] = {}
    refs = list(doc.get("contractReferences") or [])

    def _resolve_path(location: str, ref_id: str) -> Path:
        path = Path(location)
        if path.is_absolute():
            return path
        if base_dir is None:
            raise DpcsError(
                f"Cannot resolve relative location {location!r} without a root.",
                report=ValidationReport.from_diagnostics(
                    [
                        Diagnostic(
                            code="PMGEN216",
                            severity=Severity.ERROR,
                            message=(
                                f"Cannot resolve relative location {location!r} "
                                "without a root."
                            ),
                            path=("dpcs", "contractReferences", ref_id),
                        )
                    ]
                ),
            )
        return base_dir / path

    # Pass 1: ODCS so DTCS ports can resolve published contract ids.
    for ref in refs:
        ref_id = str(ref["id"])
        ref_type = str(ref.get("type") or "").lower()
        if ref_type != "odcs":
            continue
        if ref_id in registry:
            model = registry[ref_id]
        else:
            location = ref.get("location")
            if not location:
                raise DpcsError(
                    f"Contract reference {ref_id!r} has no location "
                    "and is not in the registry.",
                    report=ValidationReport.from_diagnostics(
                        [
                            Diagnostic(
                                code="PMGEN215",
                                severity=Severity.ERROR,
                                message=(
                                    f"Contract reference {ref_id!r} has no location "
                                    "and is not in the registry."
                                ),
                                path=("dpcs", "contractReferences", ref_id),
                            )
                        ]
                    ),
                )
            model = load_data_contract(
                _resolve_path(str(location), ref_id), root=base_dir
            )
        odcs_types[ref_id] = model
        published = getattr(model, "__published_id__", None)
        if isinstance(published, str):
            odcs_types[published] = model

    # Pass 2: DTCS transformations.
    for ref in refs:
        ref_id = str(ref["id"])
        ref_type = str(ref.get("type") or "").lower()
        if ref_type != "dtcs":
            continue
        if ref_id in registry:
            transform_types[ref_id] = registry[ref_id]
            continue
        location = ref.get("location")
        if not location:
            raise DpcsError(
                f"Contract reference {ref_id!r} has no location "
                "and is not in the registry.",
                report=ValidationReport.from_diagnostics(
                    [
                        Diagnostic(
                            code="PMGEN215",
                            severity=Severity.ERROR,
                            message=(
                                f"Contract reference {ref_id!r} has no location "
                                "and is not in the registry."
                            ),
                            path=("dpcs", "contractReferences", ref_id),
                        )
                    ]
                ),
            )
        transform = transformation_from_dtcs(
            _resolve_path(str(location), ref_id),
            contracts=odcs_types,
            root=base_dir,
        )
        transform_types[ref_id] = transform

    unsupported = [
        str(ref["id"])
        for ref in refs
        if str(ref.get("type") or "").lower() not in {"odcs", "dtcs"}
    ]
    if unsupported:
        raise DpcsError(
            f"Unsupported contract reference type for {unsupported[0]!r}.",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN217",
                        severity=Severity.ERROR,
                        message=(
                            f"Unsupported contract reference type for {unsupported[0]!r}."
                        ),
                        path=("dpcs", "contractReferences", unsupported[0]),
                    )
                ]
            ),
        )
    return odcs_types, transform_types


def _resolve_odcs_type(ref: Any, odcs_types: dict[str, type[Any]]) -> type[Any] | None:
    if ref is None:
        return None
    key = str(ref)
    if key in odcs_types:
        return odcs_types[key]
    # Allow bare published ids as well as odcs:<id>
    if key.startswith("odcs:") and key[5:] in odcs_types:
        return odcs_types[key[5:]]
    for value in odcs_types.values():
        published = getattr(value, "__published_id__", None)
        if published == key or f"odcs:{published}" == key:
            return value
    raise DpcsError(
        f"Unresolved ODCS reference {key!r}.",
        report=ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN218",
                    severity=Severity.ERROR,
                    message=f"Unresolved ODCS reference {key!r}.",
                    path=("dpcs", "contractRef", key),
                )
            ]
        ),
    )


def _parse_endpoint(
    endpoint: str,
    *,
    source_nodes: dict[str, Extract],
    transform_types: dict[str, type[Any]],
    step_defs: dict[str, dict[str, Any]],
) -> Any:
    parts = endpoint.split(".")
    if endpoint.startswith("interface.inputs.") and len(parts) >= 3:
        return source_nodes[parts[2]]
    if endpoint.startswith("steps.") and len(parts) >= 4:
        step_name = parts[1]
        direction = parts[2]
        port = parts[3]
        if direction == "outputs":
            contract_type = None
            step_def = step_defs.get(step_name)
            if step_def is not None:
                transform = transform_types.get(str(step_def.get("contractRef")))
                if transform is not None:
                    for output in transform.outputs():
                        if output.name == port:
                            contract_type = output.contract_type
                            break
            return OutputRef(
                node_name=step_name,
                port_name=port,
                contract_type=contract_type,
                node_kind="step",
            )
        raise DpcsError(f"Cannot use step input endpoint as producer: {endpoint}")
    raise DpcsError(f"Unsupported data-flow endpoint: {endpoint}")


def _step_parameter_values(step: dict[str, Any]) -> dict[str, Any]:
    """Extract step parameter overrides from DPCS step entries."""
    values: dict[str, Any] = {}
    raw = step.get("parameters") or []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id") is not None:
                values[str(item["id"])] = item.get("value")
    vendor = step.get("etlantic:parameters")
    if isinstance(vendor, dict):
        values.update(vendor)
    return values


def _apply_binding(
    endpoint: str,
    producer: Any,
    *,
    step_bindings: dict[str, dict[str, Any]],
    sink_inputs: dict[str, Any],
) -> None:
    parts = endpoint.split(".")
    if endpoint.startswith("steps.") and len(parts) >= 4 and parts[2] == "inputs":
        step_bindings[parts[1]][parts[3]] = producer
        return
    if endpoint.startswith("interface.outputs.") and len(parts) >= 3:
        sink_inputs[parts[2]] = producer
        return
    raise DpcsError(f"Unsupported data-flow consumer endpoint: {endpoint}")


def _safe_class_name(name: str) -> str:
    parts = [p for p in name.replace("-", "_").replace(".", "_").split("_") if p]
    cleaned = "".join(p[:1].upper() + p[1:] for p in parts) or "GeneratedPipeline"
    if cleaned[0].isdigit():
        cleaned = f"P{cleaned}"
    return cleaned


def _stable_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


# Re-export helpers used by bundles.
__all__ = [
    "DpcsError",
    "DtcsError",
    "dpcs_filename",
    "graph_fingerprint",
    "pipeline_from_dpcs",
    "pipeline_to_dpcs",
    "transformation_to_dtcs",
    "validate_dpcs_document",
    "write_dpcs",
]
