# etlantic-fastapi

Thin FastAPI reference adapter for the ETLantic 0.34 authoring and service
contract. It is not the production control plane; that surface is a
[planned first-class program](../../docs/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
with 0.40–0.43 incubation gates and a 0.44 graduation gate.

```bash
pip install 'etlantic==0.34.0' 'etlantic-fastapi==0.34.0'
# or: pip install 'etlantic[fastapi]'
```

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
```
