# Secrets decision tree (0.34)

> **Status: Available in ETLantic 0.36.0.** Normative rules for `SecretRef`
> and environment providers. Plans and reports stay secret-free.

## Rules

1. Put a `SecretRef` in the profile or runtime binding — never a resolved value.
2. Resolve secrets only at execution time inside an authorized provider.
3. Choose **one** environment mapping style for a given runtime (do not mix
   ambient defaults with a custom prefix for the same secret names).

## Decision tree

```text
Need a secret at runtime?
├─ CI / local smoke with the default EnvSecretProvider
│  └─ SecretRef(name="database_password")
│     → env var DATABASE_PASSWORD
│     (key "token" → DATABASE_PASSWORD_TOKEN)
│
├─ Explicit prefix you control
│  └─ Register EnvSecretProvider(prefix="ETLANTIC_SECRET_")
│     → SecretRef(name="WAREHOUSE_PASSWORD")
│     → env var ETLANTIC_SECRET_WAREHOUSE_PASSWORD
│     ETLANTIC_SECRET_* is NOT an ambient core convention
│
├─ Kubernetes / container mounts
│  └─ MountedFileSecretProvider(root=...)
│
└─ OS keyring
   └─ pip install etlantic-keyring (optional package)
```

## What is not shipped

AWS Secrets Manager, Azure Key Vault, Google Cloud Secret Manager, Vault, and
cloud identity providers are planned as optional 0.52 provider packs. They are
not shipped in 0.36; do not configure them yet.

## Related

- [Configuration today](CONFIGURATION_TODAY.md)
- [Runtime configuration](RUNTIME_CONFIGURATION.md)
- [Secrets management](../06_EXECUTION/SECRETS_MANAGEMENT.md)
- [Security howto](../01_GETTING_STARTED/SECURITY_HOWTO.md)
