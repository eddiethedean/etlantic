# etlantic-fastapi

Thin FastAPI reference adapter for the ETLantic 0.34 authoring and service
contract. It is not the production control plane; that surface is a
[planned first-class program](https://etlantic.readthedocs.io/en/v0.35.0/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN/)
with 0.40–0.43 incubation gates and a 0.44 graduation gate.

## Install

```bash
pip install etlantic-fastapi
```

## Usage

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
```

Use this adapter for local evaluation and integration examples, not as a
multi-tenant production control plane.

## Links

[Documentation](https://etlantic.readthedocs.io/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-fastapi) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
