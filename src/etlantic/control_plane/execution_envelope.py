"""Immutable, versioned input accepted by a managed ETL worker."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.serialize import (
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
)
from etlantic.plan.adaptive_model import (
    ADAPTIVE_PLAN_SCHEMA,
    AdaptivePipelinePlan,
    PlanDocument,
)
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import plan_from_json, verify_plan_fingerprint
from etlantic.runtime.logging import is_sensitive_key, redact_message
from etlantic.runtime.request import (
    RunRequest,
    request_setting_provenance,
    resolve_request_policies,
)

_EXECUTION_ENVELOPE_SCHEMA_V1 = "etlantic.execution_envelope/1"
EXECUTION_ENVELOPE_SCHEMA = "etlantic.execution_envelope/2"
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _validate_secret_free(name: str, value: Any) -> None:
    """Reject secret-bearing content without matching harmless key names."""

    def visit(current: Any, path: str) -> None:
        if isinstance(current, Mapping):
            entries = cast(Mapping[object, Any], current)
            for key, child in entries.items():
                if is_sensitive_key(key):
                    if (
                        str(key).lower() == "authorization"
                        and ".plugin_trust_records[" in path
                        and isinstance(child, str)
                        and child in {"allowed", "denied", "skipped", "pending"}
                    ):
                        continue
                    raise ValueError(
                        f"{name} contains a sensitive field at {path}.{key}"
                    )
                visit(child, f"{path}.{key}")
        elif isinstance(current, (list, tuple)):
            values = cast(Sequence[Any], current)
            for index, child in enumerate(values):
                visit(child, f"{path}[{index}]")
        elif isinstance(current, str) and redact_message(current) != current:
            raise ValueError(f"{name} contains inline credentials at {path}")

    visit(value, "$")
    # Also require a JSON boundary here, before an envelope can be accepted.
    _canonical_json(mutable_copy(value))


def _require_fingerprint(value: Any, name: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")
    return value


def _decode_plan(value: Mapping[str, Any]) -> PlanDocument:
    """Decode a closed, fingerprinted plan document from its schema tag."""
    payload = _canonical_json(mutable_copy(value))
    return plan_from_json(payload, verify=True)


def _plan_settings(plan: PlanDocument) -> Mapping[str, Any]:
    """Return settings resolved by a plan family, if it has that contract."""
    if isinstance(plan, PipelinePlan):
        return plan.execution_settings
    return {}


def _plan_intents(plan: PlanDocument) -> Mapping[str, Any]:
    """Return inherited intent defaults for a plan family, if present."""
    if isinstance(plan, PipelinePlan):
        return plan.intents
    return {}


def _effective_request(plan: PlanDocument, request: RunRequest) -> RunRequest:
    """Resolve request defaults and verify adaptive plans bind exact controls."""
    if isinstance(plan, AdaptivePipelinePlan):
        runtime_record = plan.metadata.get("etlantic.runtime")
        stored_request = (
            cast(Mapping[str, Any], runtime_record).get("request")
            if isinstance(runtime_record, Mapping)
            else None
        )
        if mutable_copy(stored_request or {}) != request.to_dict():
            raise ValueError("Adaptive plan does not bind the accepted run request")
        return request
    return resolve_request_policies(request, plan.execution_settings, plan.intents)


@dataclass(frozen=True, slots=True)
class ExecutionEnvelope:
    """Verified plan and request snapshot for one accepted execution.

    The envelope contains canonical definitions and plans, typed run controls,
    their profile and resource revision selectors, and the settings provenance
    used at admission. It contains no resolved credentials or source rows.
    """

    definition_id: str
    revision_selector: str
    revision_id: str | None
    definition_fingerprint: str
    definition_document: Mapping[str, Any]
    plan_fingerprint: str
    plan_document: Mapping[str, Any]
    profile_name: str
    run_request: Mapping[str, Any]
    effective_request: Mapping[str, Any]
    effective_settings: Mapping[str, Any]
    setting_provenance: Mapping[str, str]
    plugin_fingerprint: str | None = None
    policy_fingerprint: str | None = None
    resource_versions: Mapping[str, str] | None = None
    evidence_refs: Mapping[str, str] | None = None
    schema: str = EXECUTION_ENVELOPE_SCHEMA

    @classmethod
    def create(
        cls,
        *,
        definition_id: str,
        revision_selector: str,
        revision_id: str | None,
        definition: PipelineDefinition,
        plan: PlanDocument,
        profile_name: str,
        request: RunRequest,
        setting_provenance: Mapping[str, str] | None = None,
        plugin_fingerprint: str | None = None,
        policy_fingerprint: str | None = None,
        resource_versions: Mapping[str, str] | None = None,
        evidence_refs: Mapping[str, str] | None = None,
    ) -> ExecutionEnvelope:
        """Create an envelope after validating all immutable inputs."""
        effective_request = _effective_request(plan, request)
        provenance = request_setting_provenance(
            request,
            _plan_settings(plan),
            profile_name=profile_name,
            intents=_plan_intents(plan),
        )
        if setting_provenance is not None and dict(setting_provenance) != provenance:
            raise ValueError(
                "setting_provenance must match provenance derived from the request and plan"
            )
        return cls.from_dict(
            {
                "schema": EXECUTION_ENVELOPE_SCHEMA,
                "definition_id": definition_id,
                "revision_selector": revision_selector,
                "revision_id": revision_id,
                "definition_fingerprint": definition.fingerprint
                or pipeline_fingerprint(definition),
                "definition_document": pipeline_to_dict(definition),
                "plan_fingerprint": plan.fingerprint,
                "plan_document": plan.to_dict(),
                "profile_name": profile_name,
                "run_request": request.to_dict(),
                "effective_request": effective_request.to_dict(),
                "effective_settings": dict(_plan_settings(plan)),
                "setting_provenance": provenance,
                "plugin_fingerprint": plugin_fingerprint,
                "policy_fingerprint": policy_fingerprint,
                "resource_versions": dict(resource_versions or {}),
                "evidence_refs": dict(evidence_refs or {}),
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExecutionEnvelope:
        """Validate and decode a serialized envelope, rejecting unknown fields."""
        allowed = {
            "schema",
            "definition_id",
            "revision_selector",
            "revision_id",
            "definition_fingerprint",
            "definition_document",
            "plan_fingerprint",
            "plan_document",
            "profile_name",
            "run_request",
            "effective_request",
            "effective_settings",
            "setting_provenance",
            "plugin_fingerprint",
            "policy_fingerprint",
            "resource_versions",
            "evidence_refs",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "Unknown execution-envelope field(s): " + ", ".join(sorted(unknown))
            )
        schema_raw = data.get("schema")
        if schema_raw not in {
            _EXECUTION_ENVELOPE_SCHEMA_V1,
            EXECUTION_ENVELOPE_SCHEMA,
        }:
            raise ValueError("Unsupported execution-envelope schema")

        def text_field(name: str, *, allow_empty: bool = False) -> str:
            value = data.get(name)
            if not isinstance(value, str) or (not allow_empty and not value.strip()):
                raise TypeError(f"{name} must be a non-empty string")
            return value

        definition_id = text_field("definition_id")
        revision_selector = text_field("revision_selector")
        revision_id_raw = data.get("revision_id")
        if revision_id_raw is not None and not isinstance(revision_id_raw, str):
            raise TypeError("revision_id must be a string or null")
        profile_name = text_field("profile_name")
        definition_raw = data.get("definition_document")
        plan_raw = data.get("plan_document")
        request_raw = data.get("run_request")
        effective_request_raw = data.get("effective_request")
        effective_raw = data.get("effective_settings")
        provenance_raw = data.get("setting_provenance")
        required_mappings = [
            ("definition_document", definition_raw),
            ("plan_document", plan_raw),
            ("run_request", request_raw),
            ("effective_settings", effective_raw),
            ("setting_provenance", provenance_raw),
        ]
        if schema_raw == EXECUTION_ENVELOPE_SCHEMA:
            required_mappings.append(("effective_request", effective_request_raw))
        for name, value in required_mappings:
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be an object")
        definition_data = cast(Mapping[str, Any], definition_raw)
        plan_data = cast(Mapping[str, Any], plan_raw)
        request_data = cast(Mapping[str, Any], request_raw)
        effective_request_data = (
            cast(Mapping[str, Any], effective_request_raw)
            if isinstance(effective_request_raw, Mapping)
            else None
        )
        effective_data = cast(Mapping[str, Any], effective_raw)
        provenance_entries = cast(Mapping[object, object], provenance_raw)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in provenance_entries.items()
        ):
            raise TypeError("setting_provenance must map strings to strings")
        provenance_data = cast(Mapping[str, Any], provenance_entries)

        definition_fingerprint = _require_fingerprint(
            data.get("definition_fingerprint"), "definition_fingerprint"
        )
        plan_fingerprint = _require_fingerprint(
            data.get("plan_fingerprint"), "plan_fingerprint"
        )
        plugin_fingerprint_raw = data.get("plugin_fingerprint")
        policy_fingerprint_raw = data.get("policy_fingerprint")
        plugin_fingerprint = (
            _require_fingerprint(plugin_fingerprint_raw, "plugin_fingerprint")
            if plugin_fingerprint_raw is not None
            else None
        )
        policy_fingerprint = (
            _require_fingerprint(policy_fingerprint_raw, "policy_fingerprint")
            if policy_fingerprint_raw is not None
            else None
        )
        resource_versions_raw = data.get("resource_versions", {})
        evidence_refs_raw = data.get("evidence_refs", {})
        if not isinstance(resource_versions_raw, Mapping) or not isinstance(
            evidence_refs_raw, Mapping
        ):
            raise TypeError("resource_versions and evidence_refs must be objects")
        resource_versions_data = cast(Mapping[object, object], resource_versions_raw)
        evidence_refs_data = cast(Mapping[object, object], evidence_refs_raw)
        for field_name, mapping in (
            ("resource_versions", resource_versions_data),
            ("evidence_refs", evidence_refs_data),
        ):
            if not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in mapping.items()
            ):
                raise TypeError(f"{field_name} must map strings to strings")
        definition = pipeline_from_dict(dict(definition_data), verify=True)
        if definition.pipeline_id != definition_data.get("pipeline_id"):
            raise ValueError("Definition pipeline identity changed during decoding")
        actual_definition_fingerprint = definition.fingerprint
        if actual_definition_fingerprint != definition_fingerprint:
            raise ValueError("Definition fingerprint does not match its content")
        plan = _decode_plan(plan_data)
        verify_plan_fingerprint(plan)
        if plan.fingerprint != plan_fingerprint:
            raise ValueError("Plan fingerprint does not match its content")
        if plan.pipeline_id != definition.pipeline_id:
            raise ValueError("Plan and definition identify different pipelines")
        if plan.profile_name != profile_name:
            raise ValueError("Plan profile does not match the envelope profile")
        request = RunRequest.from_dict(request_data)
        selected_nodes = plan.selected_nodes or tuple(
            node.name for node in plan.logical_graph.nodes
        )
        requested_nodes = request.selection.resolve(plan.logical_graph)
        if tuple(selected_nodes) != tuple(requested_nodes):
            raise ValueError("Plan selection does not match the run request")
        settings = _plan_settings(plan)
        intents = _plan_intents(plan)
        if _canonical_json(dict(effective_data)) != _canonical_json(
            mutable_copy(settings)
        ):
            raise ValueError("Effective settings do not match the verified plan")
        _validate_secret_free("setting_provenance", dict(provenance_data))
        if effective_request_data is not None:
            _validate_secret_free("effective_request", dict(effective_request_data))

        effective_request = _effective_request(plan, request)
        expected_effective_request = effective_request.to_dict()
        expected_provenance = request_setting_provenance(
            request,
            settings,
            profile_name=profile_name,
            intents=intents,
        )
        if schema_raw == EXECUTION_ENVELOPE_SCHEMA:
            if effective_request_data is None or _canonical_json(
                dict(effective_request_data)
            ) != _canonical_json(expected_effective_request):
                raise ValueError(
                    "Effective request does not match its plan and request"
                )
            if _canonical_json(dict(provenance_data)) != _canonical_json(
                expected_provenance
            ):
                raise ValueError("Setting provenance does not match resolved settings")

        _validate_secret_free("definition_document", dict(definition_data))
        _validate_secret_free("plan_document", dict(plan_data))
        _validate_secret_free("run_request", request.to_dict())
        _validate_secret_free("effective_request", expected_effective_request)
        _validate_secret_free("effective_settings", dict(effective_data))
        _validate_secret_free("resource_versions", dict(resource_versions_data))
        _validate_secret_free("evidence_refs", dict(evidence_refs_data))
        return cls(
            definition_id=definition_id,
            revision_selector=revision_selector,
            revision_id=revision_id_raw,
            definition_fingerprint=definition_fingerprint,
            definition_document=deep_freeze(mutable_copy(definition_data)),
            plan_fingerprint=plan_fingerprint,
            plan_document=deep_freeze(mutable_copy(plan_data)),
            profile_name=profile_name,
            run_request=deep_freeze(request.to_dict()),
            effective_request=deep_freeze(expected_effective_request),
            effective_settings=deep_freeze(mutable_copy(effective_data)),
            setting_provenance=deep_freeze(expected_provenance),
            plugin_fingerprint=plugin_fingerprint,
            policy_fingerprint=policy_fingerprint,
            resource_versions=deep_freeze(
                {
                    cast(str, key): cast(str, value)
                    for key, value in resource_versions_data.items()
                }
            ),
            evidence_refs=deep_freeze(
                {
                    cast(str, key): cast(str, value)
                    for key, value in evidence_refs_data.items()
                }
            ),
        )

    @classmethod
    def from_json(cls, value: str) -> ExecutionEnvelope:
        """Decode an envelope from canonical JSON text."""
        raw = json.loads(value)
        if not isinstance(raw, Mapping):
            raise TypeError("Execution envelope must be a JSON object")
        return cls.from_dict(cast(Mapping[str, Any], raw))

    def to_dict(self) -> dict[str, Any]:
        """Return the immutable envelope as a JSON-friendly mapping."""
        return {
            "schema": self.schema,
            "definition_id": self.definition_id,
            "revision_selector": self.revision_selector,
            "revision_id": self.revision_id,
            "definition_fingerprint": self.definition_fingerprint,
            "definition_document": mutable_copy(self.definition_document),
            "plan_fingerprint": self.plan_fingerprint,
            "plan_document": mutable_copy(self.plan_document),
            "profile_name": self.profile_name,
            "run_request": mutable_copy(self.run_request),
            "effective_request": mutable_copy(self.effective_request),
            "effective_settings": mutable_copy(self.effective_settings),
            "setting_provenance": mutable_copy(self.setting_provenance),
            "plugin_fingerprint": self.plugin_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "resource_versions": mutable_copy(self.resource_versions or {}),
            "evidence_refs": mutable_copy(self.evidence_refs or {}),
        }

    def with_request(self, request: RunRequest) -> ExecutionEnvelope:
        """Return a verified envelope with a new request and resolved policies."""
        payload = self.to_dict()
        payload["run_request"] = request.to_dict()
        if self.plan_document.get("schema") == ADAPTIVE_PLAN_SCHEMA:
            raise ValueError(
                "Adaptive plan requests are fingerprint-bound and cannot be amended"
            )
        payload["effective_request"] = resolve_request_policies(
            request,
            self.effective_settings,
            cast(Mapping[str, Any], self.plan_document.get("intents") or {}),
        ).to_dict()
        payload["setting_provenance"] = request_setting_provenance(
            request,
            self.effective_settings,
            profile_name=self.profile_name,
            intents=cast(Mapping[str, Any], self.plan_document.get("intents") or {}),
        )
        return self.from_dict(payload)

    def to_json(self) -> str:
        """Serialize the envelope deterministically for durable acceptance."""
        payload = self.to_dict()
        _validate_secret_free("execution envelope", payload)
        return _canonical_json(payload)

    @property
    def canonical_intent_fingerprint(self) -> str:
        """Fingerprint caller intent independently from revision resolution."""
        return self.intent_fingerprint(
            definition_id=self.definition_id,
            revision_selector=self.revision_selector,
            profile_name=self.profile_name,
            request=RunRequest.from_dict(self.run_request),
        )

    @property
    def effective_fingerprint(self) -> str:
        """Fingerprint the verified executable plan, controls and dependencies."""
        effective = {
            "definition_fingerprint": self.definition_fingerprint,
            "revision_id": self.revision_id,
            "plan_fingerprint": self.plan_fingerprint,
            "effective_request": mutable_copy(self.effective_request),
            "effective_settings": mutable_copy(self.effective_settings),
            "resource_versions": mutable_copy(self.resource_versions or {}),
            "plugin_fingerprint": self.plugin_fingerprint,
        }
        return hashlib.sha256(_canonical_json(effective).encode("utf-8")).hexdigest()

    @staticmethod
    def intent_fingerprint(
        *,
        definition_id: str,
        revision_selector: str,
        profile_name: str,
        request: RunRequest,
    ) -> str:
        """Fingerprint submitted choices before resolving a mutable selector."""
        intent = {
            "definition_id": definition_id,
            "revision_selector": revision_selector,
            "profile_name": profile_name,
            "run_request": request.to_dict(),
        }
        return hashlib.sha256(_canonical_json(intent).encode("utf-8")).hexdigest()


__all__ = ["EXECUTION_ENVELOPE_SCHEMA", "ExecutionEnvelope"]
