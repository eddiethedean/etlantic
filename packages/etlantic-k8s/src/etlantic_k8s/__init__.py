"""Experimental Kubernetes resource provider for ETLantic (fake by default)."""

from __future__ import annotations

__version__ = "0.47.0"

from etlantic_k8s.provider import FakeKubernetes, create_provider, live_configured

__all__ = [
    "FakeKubernetes",
    "__version__",
    "create_provider",
    "live_configured",
]
