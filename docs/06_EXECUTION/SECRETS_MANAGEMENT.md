# Secrets Management

> **Available:** `env` and mounted-file secret providers (0.5+).
> Optional OS keyring provider via `etlantic-keyring` (0.9+).
> AWS Secrets Manager, Azure Key Vault, Google Cloud Secret Manager, and Vault
> are **planned 0.52 optional providers**—they are not shipped, so do not
> configure them yet.

ETLantic treats secrets as runtime dependencies that are referenced during
configuration and resolved only inside an authorized execution boundary.

ETLantic is not a secret store. Plans stay secret-free: they may contain a
`SecretRef`, never a resolved value. Values must not appear in contracts,
`PipelinePlan`, logs, diagnostics, events, reports, caches, or tracebacks.

## Shipped in 0.5

### Secret references

```python
from etlantic import SecretRef

warehouse_password = SecretRef(
    provider="ci-secrets",
    name="WAREHOUSE_PASSWORD",
)
```

| Field | Meaning |
|---|---|
| `provider` | Logical provider name configured on the runtime |
| `name` | Provider-specific secret identifier |
| `key` | Optional field within a structured secret (when supported) |
| `version` | Optional version hint (provider-specific) |

### Environment provider

```python
from etlantic.secrets import EnvSecretProvider

# Optional explicit prefix (not ambient):
provider = EnvSecretProvider(prefix="ETLANTIC_SECRET_")
# Resolves SecretRef(name="WAREHOUSE_PASSWORD") from
# ETLANTIC_SECRET_WAREHOUSE_PASSWORD
```

Default (no custom prefix): `SecretRef(name="database_password")` resolves from
`DATABASE_PASSWORD`. See the normative
[Secrets decision tree](../10_REFERENCE/SECRETS_DECISION.md).

Use environment variables for CI and local smoke tests. Prefer a real secret
manager in production once provider plugins ship.

### Mounted-file provider

```python
from etlantic.secrets import MountedFileSecretProvider

provider = MountedFileSecretProvider(root="/var/run/secrets")
# Resolves SecretRef(name="warehouse_password") from a file under root
```

Useful for Kubernetes/container secret mounts. Paths are bounded to the
configured root (fail closed on traversal).

### SecretValue

Resolved secrets use `SecretValue`:

- `repr()` / `str()` are redacted
- normal serialization is refused
- equality and hashing do not expose the underlying value

### Resolution rules

- Planning must not resolve secrets
- Missing or unreadable secrets fail closed at runtime
- Redact exception messages before they enter reports or logs

## Planned provider packs (not shipped)

The following belong in later milestones. Configuration examples that mention
them are design sketches only. **OS keyring is available today** via
`etlantic-keyring` (0.9+).

| Target environment | Status |
|---|---|
| Developer workstation (`etlantic-keyring`) | Available (optional package) |
| AWS Secrets Manager | Planned 0.52 optional provider |
| Azure Key Vault | Planned 0.52 optional provider |
| Google Cloud Secret Manager | Planned 0.52 optional provider |
| HashiCorp Vault | Planned 0.52 optional provider |
| 1Password | Unscheduled candidate |

See the [Secret Provider SDK](../07_PLUGIN_SDK/SECRET_PROVIDER.md) (future
design) for the intended plugin shape and the
[Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md#managed-runtime-and-enterprise-provider-packs)
for the assigned production gates.

## See Also

- [Security Model](../02_FOUNDATIONS/SECURITY.md)
- [Security policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
- [Local Python](LOCAL_PYTHON.md)
- [Compatibility](../10_REFERENCE/COMPATIBILITY.md)
