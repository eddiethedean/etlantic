# Secret Provider

> **Status: Available in ETLantic 0.5+** (protocol in `etlantic.secrets`).
> Built-in providers: environment variables and mounted files. Optional OS
> keyring via `etlantic-keyring`. AWS Secrets Manager, Azure Key Vault, Google
> Cloud Secret Manager, and HashiCorp Vault are planned as optional 0.59
> provider packs; they are not shipped in 0.37.

A Secret Provider resolves logical `SecretRef` objects into short-lived,
redacted values for authorized runtime consumers.

## Responsibilities

A provider:

- declares supported reference forms via `SecretProviderDescriptor`
- retrieves a secret only during execution (never during planning)
- returns a protected `SecretValue`
- applies bounded in-memory cache policy where appropriate
- closes clients where supported

A provider must not add values to plans, log request or response bodies, or
define pipeline semantics.

## Managed current-version references

In a managed worker, `SecretRef.version="current"` is a late-bound request.
The worker requires an injected `SecretAliasAuthorizer` and calls it for each
resolution with the secret reference and the server-derived
`SecretResolutionContext`. The decision runs before cache lookup, so a changed
policy cannot be bypassed by a cached value. The provider receives
`context.late_binding_authorized=True` only after approval.

Configure the policy on the worker, rather than accepting authorization in a
pipeline or HTTP payload:

```python
from etlantic.runtime.execution_host import ExecutionHost

host = ExecutionHost(
    durable_store,
    secret_alias_authorizer=deployment_secret_policy,
)
```

The policy must use the trusted principal, tenant, workspace, environment,
security domain, resource owner, and reference purpose. Denials and policy
errors fail closed before provider access. Versioned providers must advertise
`aliases=True` before they may resolve `current`; providers must return the
actual resolved version for auditing. Managed aliases are not cached because
their target can rotate between lookups. Values from providers advertising
leases, renewal, or revocation are also not cached until the worker owns those
lifecycle operations. Exact version references continue to require
`versions=True` and an exact returned-version match.

## Shipped Protocol

```python
from collections.abc import AsyncIterator
from typing import Protocol

from etlantic.secrets import (
    ProviderContext,
    SecretProvider,
    SecretProviderDescriptor,
    SecretRef,
    SecretResolutionContext,
    SecretValue,
)


class SecretProvider(Protocol):
    @property
    def descriptor(self) -> SecretProviderDescriptor: ...

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue: ...

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]: ...
```

Built-ins:

```python
from etlantic.secrets import EnvSecretProvider, MountedFileSecretProvider

env = EnvSecretProvider(prefix="ETLANTIC_SECRET_")
files = MountedFileSecretProvider(root="/run/secrets")
```

## Conformance

Third-party providers should pass
`etlantic.testing.run_secret_conformance_suite(provider)`.

## Production profiles

Use `Profile.plugin_allowlist` for engine plugins. Secret providers are
attached to the runtime / profile configuration—never embed resolved values in
plans or reports. See
[Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md) and
[Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md).

## Not shipped

- AWS Secrets Manager / HashiCorp Vault providers
- TOML-based secret backend selection (`etlantic.toml`)

## Next Step

Continue with [Testing Plugins](TESTING_PLUGINS.md) for conformance suites, or
[Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md) for operator guidance.
