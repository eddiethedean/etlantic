"""Service facade tests."""

from __future__ import annotations

from examples.memory_customers import CustomerPipeline, normalize_customers

from etlantic.authoring import definition_from_pipeline, pipeline_to_dict
from etlantic.authoring.resolve import callable_registry
from etlantic.service import AuthoringService, PolicyContext


def test_authoring_service_validate_plan() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    callable_registry().register(
        defn.transformations[0].identity, "local", normalize_customers
    )
    svc = AuthoringService(policy=PolicyContext(profile="development"))
    put = svc.put_definition("cust", pipeline_to_dict(defn))
    assert put["fingerprint"]
    validated = svc.validate("cust")
    assert "diagnostics" in validated
    planned = svc.plan("cust")
    assert "plan" in planned
