"""FakeKubernetes resource provider tests (live Kind skipped)."""

from __future__ import annotations

import os

import pytest

from etlantic.resources.protocol import ResourceRequest
from etlantic_k8s import FakeKubernetes, live_configured


def test_fake_acquire_and_release() -> None:
    provider = FakeKubernetes()
    handle = provider.acquire(ResourceRequest(kind="pod", identity="job-1"))
    assert handle.metadata["fake"] is True
    assert handle.identity in provider.pods
    provider.release(handle)
    assert handle.identity not in provider.pods


@pytest.mark.skipif(
    not live_configured() and not os.environ.get("ETLANTIC_K8S_CONTEXT"),
    reason="047-K-01 live Kind skipped",
)
def test_live_kind_skipped() -> None:
    pytest.skip("047-K-01 live Kind remains deferred")
