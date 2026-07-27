"""CI-collectable FastAPI reference smoke (repo root on sys.path)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")

from examples.memory_customers import CustomerPipeline, normalize_customers

from etlantic.authoring import definition_from_pipeline, pipeline_to_dict
from etlantic.authoring.resolve import callable_registry
from etlantic_fastapi import create_reference_app


def test_reference_app_openapi_paths() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    callable_registry().register(
        defn.transformations[0].identity, "local", normalize_customers
    )
    app = create_reference_app()
    paths = app.openapi()["paths"]
    assert "/catalog" in paths
    assert "/pipelines/{definition_id}/runs" in paths
    put = app.state.service.put_definition("demo", pipeline_to_dict(defn))
    assert put["fingerprint"]
    cancel = app.state.service.cancel_run(
        app.state.service.submit_run("demo")["job_id"]
    )
    assert cancel["cancel_supported"] is False
