# etlantic-keyring

Local workstation secret provider for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.40 using the Python
[`keyring`](https://keyring.readthedocs.io/) library and OS credential stores.

## Install

```bash
pip install etlantic-keyring
```

## Wiring

```python
from etlantic import Profile
from etlantic_keyring import create_provider

provider = create_provider(service="etlantic.customer-platform")
runtime.register_secret_provider("keyring", provider)
```

Registration is explicit: create the provider and register it on the runtime
under the same name referenced by the profile. Production profiles must also
allowlist trusted plugins. Secret values remain in the OS credential store and
are resolved only at runtime.

`SecretRef` resolution uses:

- `name` — keyring service name (or falls back to the provider default)
- `key` — keyring username / account name

```toml
[profiles.local.secrets.production-secrets]
provider = "keyring"
service = "etlantic.customer-platform"
```

Fail-closed: missing credentials raise `PipelineExecutionError` at runtime.

## Links

[Secrets documentation](https://etlantic.readthedocs.io/en/v0.40.0/06_EXECUTION/SECRETS_MANAGEMENT/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-keyring) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
