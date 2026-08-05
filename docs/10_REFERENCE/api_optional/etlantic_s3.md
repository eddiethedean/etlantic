---
status: available
since: "0.43.0"
current_minor: "0.45"
audience: developer
---

# etlantic-s3 API

> **Status: Experimental in ETLantic 0.43.0.** S3-compatible source, sink,
> and storage connectors with fake/CI conformance evidence. Install narrative:
> package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-s3==0.45.0'
```

```python
import etlantic_s3
print(etlantic_s3.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Optional; fake connector remains available for conformance tests |

## Public API

::: etlantic_s3
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
