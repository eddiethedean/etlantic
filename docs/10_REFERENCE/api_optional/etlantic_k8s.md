---
status: available
since: "0.48.0"
current_minor: "0.48"
audience: developer
---

# etlantic-k8s API

> **Status: Experimental in ETLantic 0.48.0.** Fake-first Kubernetes resource
> provider. Live Kind is opt-in. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-k8s==0.48.0'
```

```python
import etlantic_k8s
print(etlantic_k8s.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Not required; `FakeKubernetes` remains available for conformance tests |
| Live cluster | Skipped unless `ETLANTIC_K8S_CONTEXT` is set (`047-K-01`) |
| Production allowlist | Empty `resource_provider_allowlist` rejects with `PMRES140` when selected |

## Public API

::: etlantic_k8s
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
