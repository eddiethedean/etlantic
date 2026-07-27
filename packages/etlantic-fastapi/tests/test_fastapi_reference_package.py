"""FastAPI reference adapter OpenAPI + service fixture (no examples import)."""

from __future__ import annotations

import pytest

from etlantic.authoring import (
    definition_from_pipeline,
    pipeline_to_dict,
)
from etlantic.authoring.resolve import callable_registry

fastapi = pytest.importorskip("fastapi")
etlantic_fastapi = pytest.importorskip("etlantic_fastapi")
from examples.memory_customers import (  # noqa: E402
    CustomerPipeline,
    normalize_customers,
)

from etlantic_fastapi import create_reference_app  # noqa: E402


def test_openapi_and_service_fixture() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    callable_registry().register(
        defn.transformations[0].identity, "local", normalize_customers
    )
    app = create_reference_app()
    schema = app.openapi()
    assert "/catalog" in schema["paths"]
    assert "/pipelines/{definition_id}" in schema["paths"]
    assert "/negotiation" in schema["paths"]

    svc = app.state.service
    assert "document_versions" in svc.negotiation()
    assert svc.negotiation().get("run_model") == "synchronous_reference"
    put = svc.put_definition("demo", pipeline_to_dict(defn))
    assert put["fingerprint"]
    assert "entries" in svc.catalog("demo")
    assert "diagnostics" in svc.validate("demo")
    assert "plan" in svc.plan("demo")
