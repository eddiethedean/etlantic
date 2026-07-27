# etlantic-fastapi

Thin FastAPI reference adapter for the ETLantic 0.25 authoring and service
contract. Not a production control plane (see 1.1 FastAPI Integration Plan).

```bash
pip install etlantic-fastapi
```

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
```
