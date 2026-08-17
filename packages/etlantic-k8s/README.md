# etlantic-k8s (Experimental / Preview)

Version **0.47.0** (lockstep with ETLantic core).
Fake-first Kubernetes resource provider for [ETLantic](https://github.com/eddiethedean/etlantic).
Live Kind clusters are opt-in via `ETLANTIC_K8S_CONTEXT` and are skipped in CI (`047-K-01`).

**Maturity:** Experimental (Alpha classifier). Pin with core.

## Install

```bash
pip install 'etlantic-k8s==0.47.0'
```

Core dependency: `etlantic>=0.47.0,<0.48`. No Kubernetes Python SDK in the default extra.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.resource_providers` | `kubernetes` | `etlantic_k8s:create_provider` |
