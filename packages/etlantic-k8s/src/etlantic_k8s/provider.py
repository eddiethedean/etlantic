"""In-process FakeKubernetes resource provider."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.resources.protocol import (
    ResourceHandle,
    ResourceProviderInfo,
    ResourceRequest,
)

_PKG_VERSION = "0.47.0"


def live_configured() -> bool:
    """True when a live Kind/cluster context is opted in (never required in CI)."""
    return bool(str(os.environ.get("ETLANTIC_K8S_CONTEXT") or "").strip())


@dataclass
class FakeKubernetes:
    """In-memory Kubernetes stand-in. No kubeconfig or live API calls."""

    namespace: str = "default"
    pods: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def info(self) -> ResourceProviderInfo:
        return ResourceProviderInfo(
            name="kubernetes",
            version=_PKG_VERSION,
            package="etlantic-k8s",
            capabilities=self.capabilities(),
            metadata={"fake": True},
        )

    def capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            engine="k8s",
            dataframe=False,
            extras=frozenset({"k8s"}),
        )

    def acquire(self, request: ResourceRequest) -> ResourceHandle:
        if live_configured():
            raise RuntimeError("live Kind path is skipped in 0.47 (047-K-01)")
        self.pods[request.identity] = {
            "kind": request.kind,
            "namespace": self.namespace,
        }
        return ResourceHandle(
            identity=request.identity,
            kind=request.kind or "pod",
            metadata={"namespace": self.namespace, "fake": True},
        )

    def release(self, handle: ResourceHandle) -> None:
        self.pods.pop(handle.identity, None)


def create_provider() -> FakeKubernetes:
    return FakeKubernetes()
