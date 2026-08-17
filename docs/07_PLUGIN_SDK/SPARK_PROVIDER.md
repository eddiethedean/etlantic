# Spark Provider

**Status: shipped in 0.7.0** for the local provider in `etlantic-pyspark`.
An Experimental Spark Connect extra (`etlantic-spark-connect`) with an
in-process fake is Available in **0.47.0**. Live Databricks, EMR, and Spark
Connect packs remain deferred (`047-S-01` / 0.51). See the
[Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md#managed-runtime-and-enterprise-provider-packs).

A **Spark Provider** implements the ETLantic Resource Provider API for
creating, configuring, supplying, reusing, and disposing Apache Spark sessions
and related runtime resources.

The PySpark Plugin executes Spark-capable regions of a Pipeline Plan. The Spark
Provider supplies the concrete Spark environment in which that execution occurs.

This separation keeps cluster configuration, credentials, session lifecycle,
and environment-specific behavior out of pipeline definitions and
transformation contracts.

## Purpose

A Spark Provider is responsible for:

- Creating or acquiring Spark sessions
- Configuring Spark runtime settings
- Managing session lifecycle
- Supplying cluster and catalog integrations
- Managing authentication and connectivity
- Publishing runtime capabilities
- Reporting structured diagnostics
- Cleaning up provider-owned resources

It is **not** responsible for:

- Defining pipeline semantics
- Defining transformation implementations
- Planning Spark regions
- Executing transformation logic
- Replacing the PySpark Plugin
- Embedding secrets in contracts or plans

## Architecture

```text
Validated Pipeline Plan
          │
          ▼
     PySpark Plugin
          │
          ▼
    Spark Provider API
          │
    ┌─────┴──────────────────────────────┐
    ▼                                    ▼
Spark Session Lifecycle          Environment Integration
    │                                    │
    ├── Create / Acquire                 ├── Databricks
    ├── Configure                        ├── EMR
    ├── Reuse                            ├── Kubernetes
    ├── Health Check                     ├── YARN
    └── Dispose                          └── Spark Connect
          │
          ▼
      Spark Runtime
```

## Provider Interface

Conceptually:

```python
class SparkProvider:
    name: str
    version: str

    def capabilities(self) -> SparkProviderCapabilities:
        ...

    def acquire(
        self,
        request: SparkSessionRequest,
        context: ResourceContext,
    ) -> SparkSessionHandle:
        ...

    def release(
        self,
        handle: SparkSessionHandle,
        context: ResourceContext,
    ) -> None:
        ...
```

Async providers may expose asynchronous acquisition and release through the
standard Resource Provider lifecycle.

## Spark Session Request

The PySpark Plugin should request a logical Spark environment rather than build
one directly.

Conceptually:

```python
SparkSessionRequest(
    application_name="customer-pipeline",
    execution_mode="batch",
    required_capabilities={
        "delta_lake",
        "adaptive_query_execution",
    },
    configuration={
        "session_timezone": "UTC",
    },
)
```

The request may include:

- Pipeline identity
- Run identity
- Execution mode
- Required Spark capabilities
- Required catalogs
- Required packages
- Session configuration
- Security requirements
- Resource expectations

It must not contain embedded credentials.

## Spark Session Handle

The provider should return a managed handle.

Conceptually:

```python
SparkSessionHandle(
    session=spark,
    provider="local-spark",
    environment="local",
    owned=True,
    capabilities=...,
)
```

The handle may include:

- Native `SparkSession`
- Environment identity
- Application ID
- Ownership metadata
- Cleanup policy
- Capabilities
- Provider diagnostics
- Remote job metadata
- Spark UI reference where permitted

## Ownership

The provider must declare whether it owns the returned session.

### Provider-owned session

The provider created the session and is responsible for stopping it.

### Shared session

The provider supplies a reusable session and may keep it alive after one run.

### Externally managed session

The session lifecycle is controlled by another platform.

Examples include:

- Databricks notebook session
- Existing Spark application
- Managed worker process
- Spark Connect server

ETLantic must not stop externally managed sessions.

## Lifecycle Models

A provider may support one or more lifecycle models.

### Per-run session

Creates one session for each pipeline execution.

Advantages:

- Strong isolation
- Predictable configuration
- Simple cleanup

Tradeoffs:

- Startup overhead
- Higher resource cost

### Shared worker session

Reuses one session across multiple runs.

Advantages:

- Lower startup cost
- Reused caches and connections

Tradeoffs:

- Configuration isolation
- Cleanup complexity
- Concurrency concerns

### External session

Uses a session supplied by the environment.

Advantages:

- Integrates with managed platforms
- No startup responsibility

Tradeoffs:

- Limited control
- Environment-dependent capabilities

### Remote session

Uses Spark Connect or another remote session protocol.

Advantages:

- Thin client
- Remote cluster execution
- Separated driver environment

Tradeoffs:

- Protocol limitations
- Version compatibility
- Different artifact distribution behavior

## Provider Capabilities

A provider should publish capabilities such as:

```python
SparkProviderCapabilities(
    local_mode=True,
    remote_mode=False,
    shared_sessions=True,
    isolated_sessions=True,
    spark_connect=False,
    batch=True,
    structured_streaming=True,
    dynamic_packages=True,
    custom_jars=True,
    custom_catalogs=True,
    delta_lake=True,
    iceberg=False,
    external_checkpoint_storage=True,
)
```

Capabilities should distinguish:

- Supported
- Partially supported
- Environment managed
- Version dependent
- Unsupported

## Environment Identity

The provider should expose its environment type.

Examples include:

- Local
- Standalone
- YARN
- Kubernetes
- Databricks
- Amazon EMR
- Google Dataproc
- Azure Synapse
- Spark Connect
- Existing embedded Spark session

Environment identity informs planning and diagnostics but does not change
pipeline semantics.

## Configuration Sources

Spark configuration may come from:

- Execution profiles
- Environment variables
- Cluster policies
- Provider defaults
- Managed-platform configuration
- Organization policy
- Secret providers

Precedence should be deterministic and documented.

## Configuration Categories

The provider may configure:

- Application identity
- Master or remote endpoint
- Session time zone
- Shuffle partitions
- Adaptive Query Execution
- Serialization
- Memory settings
- Catalogs
- Spark extensions
- Packages and JARs
- Checkpoint locations
- Cloud storage connectors
- SQL warehouse settings
- Security and authentication

## Configuration Validation

The provider should validate configuration before session acquisition.

Checks may include:

- Unsupported settings
- Conflicting settings
- Invalid package coordinates
- Missing required catalogs
- Incompatible Spark versions
- Restricted settings under cluster policy
- Invalid checkpoint locations
- Unavailable credentials

Failures should produce structured diagnostics.

## Configuration Precedence

A possible precedence model is:

```text
Organization Policy
        │
        ▼
Provider Requirements
        │
        ▼
Execution Profile
        │
        ▼
Provider Defaults
```

Higher-priority controls should not be silently overridden by lower-priority
configuration.

## Application Naming

The provider should generate stable, useful application names.

A name may include:

- Pipeline identity
- Environment
- Run identity
- Attempt number

Example:

```text
etlantic-customer-pipeline-production
```

Application names should avoid secrets and unsafe user input.

## Spark Version Compatibility

The provider should publish and validate compatibility for:

- Apache Spark
- PySpark
- Python
- Java
- Scala binary version
- Hadoop libraries
- Spark Connect protocol
- Managed runtime version
- Installed extensions

Version mismatches should fail before execution where possible.

## Java Compatibility

Spark environments may require a supported Java runtime.

The provider should report:

- Required Java versions
- Detected Java version
- Unsupported combinations
- Environment-managed Java behavior

Pipeline authors should not configure Java in pipeline definitions.

## Scala Compatibility

JARs and Spark extensions may depend on Scala binary versions.

The provider should verify compatible artifacts before session startup.

## Package and JAR Resolution

The provider may resolve:

- Python wheels
- Python archives
- Maven packages
- JAR files
- Spark packages
- Native dependencies

Dependency resolution should be deterministic and inspectable.

## Dependency Locking

Production environments should support locked dependency sets.

Conceptually:

```python
SparkDependencySet(
    python_packages=[...],
    jars=[...],
    spark_packages=[...],
    digest="...",
)
```

Dependency metadata should be suitable for review and reproducibility.

## Catalog Configuration

Providers may configure catalogs such as:

- Hive metastore
- Unity Catalog
- AWS Glue
- Iceberg catalogs
- Delta catalogs
- JDBC catalogs
- Organization-specific catalogs

Catalog credentials and endpoints should come from Resource Providers or secret
managers.

## Delta Lake

A provider may enable Delta Lake through:

- Spark extensions
- Catalog configuration
- Package dependencies
- Managed-runtime support

Capabilities should identify:

- Read and write
- Merge
- Change Data Feed
- Time travel
- Streaming
- Schema evolution
- Optimize and vacuum where permitted

## Iceberg

A provider may configure Iceberg through:

- Catalogs
- Spark session extensions
- Runtime JARs
- Cloud integrations

Capabilities should identify supported operations and version limits.

## Cloud Storage

Providers may configure access to:

- Amazon S3
- Azure Data Lake Storage
- Google Cloud Storage
- Organization-specific object stores

Credentials must remain external to pipeline contracts and compiled plans.

## Authentication

Authentication may use:

- Environment identity
- Instance profiles
- Managed identities
- Workload identity
- Service principals
- OAuth
- Token providers
- Secret managers
- Kerberos
- Platform-native identity

The provider should expose authentication requirements without exposing
credentials.

## Secret Integration

Spark Providers should acquire secrets through Resource Providers.

Conceptually:

```text
Spark Provider
      │
      ▼
Secret Provider
      │
      ▼
Temporary runtime credentials
```

Secrets should not be stored in:

- Pipeline definitions
- [DPCS](../05_PIPELINES/DPCS.md) artifacts
- Compiled Spark Plans
- Documentation
- Diagnostics
- Logs

## Security Policy

Providers should enforce:

- Least-privilege access
- Allowed packages and JARs
- Approved catalogs
- Restricted Spark configuration
- Secure network endpoints
- Encrypted checkpoint storage
- Safe logging
- Session isolation
- UDF execution policy

## Session Isolation

Isolation may include:

- Separate Spark applications
- Separate sessions
- Separate catalogs
- Separate namespaces
- Separate temporary directories
- Separate checkpoint roots
- Separate job groups
- Separate credentials

The provider should document its isolation guarantees.

## Concurrency

The provider should declare concurrency support.

Questions include:

- Can one session run multiple pipelines concurrently?
- Are configuration changes session-safe?
- Are temporary views isolated?
- Are job groups isolated?
- Can streaming and batch share the session?
- Are local properties thread-local?

The PySpark Plugin should plan accordingly.

## Thread Safety

Native Spark sessions and contexts have specific concurrency behavior.

The provider should expose safe usage guidance and enforce synchronization where
required.

## Session Configuration Mutability

Some Spark settings may be changed after session creation.

Others require a new application or context.

The provider should classify settings as:

- Startup-only
- Session mutable
- Query-local
- Environment managed
- Unsupported

## Health Checks

Providers should support health checks such as:

- Session exists
- Spark context active
- Remote endpoint reachable
- Catalog accessible
- Required extensions loaded
- Checkpoint storage writable
- Required package present

Health checks should avoid expensive jobs unless explicitly requested.

## Warm-Up

Providers may support optional warm-up actions.

Examples include:

- Initialize Spark context
- Resolve packages
- Load catalogs
- Test object storage access
- Run a minimal query

Warm-up should be explicit because it may incur cost.

## Session Reuse

When sessions are reused, providers should manage:

- Configuration compatibility
- Temporary object cleanup
- Cache cleanup
- Job-group cleanup
- Local property cleanup
- Catalog state
- Streaming-query state
- Credential expiration

A shared session should not leak one pipeline's state into another.

## Cache Cleanup

The provider and PySpark Plugin should coordinate cache ownership.

A provider may clear provider-owned caches during release.

It should not indiscriminately clear caches owned by unrelated external
workloads.

## Temporary Views

Temporary views should use collision-safe names.

Global temporary views require additional care because they may be visible
across sessions in one application.

## Checkpoint Roots

The provider may supply a checkpoint root.

Conceptually:

```text
s3://company-checkpoints/etlantic/
```

The PySpark Plugin derives run- and query-specific paths beneath that root.

Checkpoint paths should be:

- Collision safe
- Access controlled
- Durable when required
- Cleaned according to policy
- Free of secrets

## Local Directories

Providers may configure:

- Spark local directories
- Temporary storage
- Shuffle locations
- Download caches
- Python worker storage

Local storage should respect environment security and cleanup policies.

## Job Groups

The provider should support stable Spark job groups where available.

A job group may be derived from:

- Pipeline identity
- Region identity
- Run identity
- Attempt number

Job groups improve:

- Cancellation
- Diagnostics
- Spark UI attribution
- Runtime lineage

## Cancellation

Providers should support cancellation when the environment permits.

Possible targets include:

- Job group
- Streaming query
- Remote job
- Databricks run
- EMR step
- Kubernetes Spark application
- Spark Connect operation

Cancellation should trigger appropriate cleanup.

## Structured Streaming Lifecycle

For streaming workloads, the provider may manage:

- Query start
- Active query registry
- Await termination
- Graceful stop
- Checkpoint recovery
- Query restart
- Progress listeners
- State-store configuration

Streaming query ownership must be explicit.

## Managed-Platform Providers

Managed environments may require specialized providers.

Examples include:

- Databricks Provider
- EMR Provider
- Dataproc Provider
- Synapse Provider

A managed provider may supply:

- Existing runtime sessions
- Job submission APIs
- Cluster configuration
- Platform identity
- Runtime links
- Platform-specific capabilities

## Local Spark Provider

A local provider supports development and CI.

Conceptually:

```python
LocalSparkProvider(
    master="local[*]",
    session_timezone="UTC",
)
```

It should provide deterministic defaults and simple cleanup.

## Standalone Spark Provider

A standalone provider may connect to an existing Spark master or submit a new
application.

It should document:

- Driver placement
- Dependency distribution
- Network requirements
- Cleanup behavior

## YARN Provider

A YARN provider may configure:

- Queue
- Application tags
- Kerberos
- Resource requests
- Deployment mode
- Hadoop configuration

## Kubernetes Provider

A Kubernetes Spark-on-cluster configuration is **not shipped**. Experimental
Kubernetes Job execution (`etlantic-k8s` + `FakeKubernetes`) is the 0.47 freeze;
live isolated clusters are 0.51. Do not implement against this section yet.

A Kubernetes provider may configure:

- Namespace
- Service account
- Driver and executor images
- Resource requests and limits
- Secrets
- Volumes
- Pod templates
- Spark operator integration

## Databricks Provider

A Databricks provider may support:

- Existing cluster
- Job cluster
- Serverless
- Databricks Connect
- Unity Catalog
- Runtime versions
- Job submission
- Run monitoring
- Cluster policies

Credentials should come from approved secret or identity providers.

## EMR Provider

An EMR provider may support:

- Existing clusters
- EMR Steps
- EMR Serverless
- Instance fleets
- IAM roles
- S3 integrations
- Runtime release labels

## Spark Connect Provider

A Spark Connect provider supplies remote sessions.

Capabilities may differ from embedded PySpark.

The provider should declare:

- Protocol version
- Server Spark version
- Unsupported APIs
- Artifact upload support
- UDF support
- Streaming support
- Session lifecycle

## Remote Job Providers

Some environments may not provide a live `SparkSession` to the client.

Instead, the provider may return a remote execution handle.

Conceptually:

```python
RemoteSparkHandle(
    submission_target=...,
    environment=...,
)
```

The PySpark Plugin may compile an executable artifact for remote submission.

## Observability

Providers may expose:

- Application ID
- Environment ID
- Cluster ID
- Spark UI link
- Job or run link
- Session creation duration
- Resource allocation
- Provider health
- Credential expiration metadata
- Runtime version

Observability metadata should be access-controlled and redacted as needed.

## Diagnostics

Provider diagnostics may include:

- Provider identity
- Environment
- Pipeline identity
- Run identity
- Acquisition phase
- Spark version
- Java version
- Missing package
- Invalid configuration
- Authentication failure
- Network failure
- Cluster policy violation
- Session cleanup failure
- Suggested remediation

## Failure Classification

Provider failures may include:

- Configuration error
- Authentication failure
- Authorization failure
- Network failure
- Session startup failure
- Incompatible version
- Missing extension
- Cluster unavailable
- Resource quota exceeded
- Dependency resolution failure
- Cleanup failure
- Cancellation failure

Failure categories should support execution-layer retry decisions.

## Retryability

Potentially retryable provider failures include:

- Transient cluster startup failure
- Temporary network failure
- Rate limiting
- Managed-platform control-plane failure
- Temporary capacity shortage

Non-retryable failures often include:

- Invalid configuration
- Unsupported runtime version
- Missing permission
- Disallowed package
- Incompatible Java or Scala version

The provider should return typed retry guidance.

## Idempotent Acquisition

Session acquisition should be safe to retry when possible.

A provider should avoid creating duplicate clusters or applications without
stable idempotency identifiers.

## Release Semantics

Release behavior depends on ownership.

### Owned local session

Stop the session and context according to policy.

### Shared session

Clean provider-owned state but keep the session alive.

### External session

Do not stop the session.

### Managed job cluster

Allow the platform to terminate it after the run.

### Remote session

Close the client session without terminating unrelated server resources.

## Cleanup

Cleanup may include:

- Unpersist provider-owned data
- Remove temporary views
- Stop owned streaming queries
- Clear job groups
- Remove local temporary files
- Release remote handles
- Revoke temporary credentials
- Delete temporary checkpoints where permitted

Cleanup failures should be reported without hiding the original execution
failure.

## Provider Registration

Applications may register a provider instance explicitly:

```python
from etlantic import PipelineRuntime
from etlantic_pyspark import create_provider

runtime = PipelineRuntime()
runtime.register_spark_provider("local", create_provider())
```

Normal deployments should use the `etlantic.spark_providers` entry point and
profile-aware automatic discovery.

## Profile Binding

A profile may select a provider:

```python
Profile(
    name="spark-local",
    spark_engine="pyspark",
    resources={"spark": "local"},
)
```

The profile describes environment intent. Provider-specific configuration
belongs in the provider or namespaced profile metadata; do not place live
sessions or credentials in the profile.

Secrets remain external.

## Multiple Spark Resources

A pipeline may require multiple Spark environments only when explicitly
supported.

Examples include:

- Separate security domains
- Separate regions
- Separate catalogs
- Migration workflows

Cross-session data movement introduces explicit materialization boundaries.

## Compilation Integration

The Spark Provider should contribute environment metadata during compilation.

This allows the PySpark Plugin to determine:

- Supported Spark features
- Required deployment artifacts
- Package strategy
- Session constraints
- Streaming capabilities
- Catalog access
- Submission mode

## Determinism

Equivalent provider configuration should produce equivalent acquisition
requests and capability declarations.

Runtime-assigned identifiers such as application IDs are not deterministic.

## Caching Provider Metadata

Capability and environment metadata may be cached.

Caches should be invalidated when:

- Runtime version changes
- Cluster policy changes
- Provider version changes
- Installed extensions change
- Authentication context changes
- Managed environment configuration changes

## Testing

Every Spark Provider should pass shared SDK tests.

Required areas include:

- Discovery
- Capability declarations
- Configuration validation
- Session acquisition
- Ownership metadata
- Release behavior
- Health checks
- Error classification
- Retry guidance
- Cleanup
- Secret redaction
- Version compatibility
- Concurrent acquisition
- Streaming lifecycle where supported
- Cancellation where supported

## Local Conformance Tests

The SDK should provide deterministic local tests.

```python
def test_local_spark_provider(
    provider,
) -> None:
    handle = provider.acquire(...)
    assert handle.session is not None
    provider.release(handle, ...)
```

Tests should verify that the provider does not leak sessions or temporary state.

## Managed Integration Tests

Managed providers may offer optional test suites for:

- Cluster startup
- Remote submission
- Catalog access
- Storage access
- Streaming checkpoints
- Cancellation
- Runtime links
- Identity propagation

These tests may require external credentials and should remain separate from
local CI.

## Security Tests

Security testing should verify:

- Secrets do not appear in diagnostics
- Restricted settings cannot be overridden
- Temporary resources are isolated
- Untrusted package coordinates are rejected where policy requires
- External sessions are not stopped
- Credentials are released appropriately

## Best Practices

- Keep Spark sessions behind the provider boundary.
- Declare ownership explicitly.
- Keep secrets external.
- Validate configuration before acquisition.
- Publish precise capabilities.
- Use stable application and job identities.
- Clean only provider-owned resources.
- Make session reuse rules explicit.
- Separate local, remote, and managed providers.
- Expose environment metadata for planning.
- Test lifecycle and cleanup thoroughly.
- Preserve security and isolation policies.

## Anti-Patterns

Avoid:

- Calling `SparkSession.builder` inside transformations.
- Stopping externally managed sessions.
- Embedding credentials in profiles.
- Sharing sessions without state cleanup.
- Mutating startup-only settings on reused sessions.
- Assuming every Spark environment supports the same features.
- Hiding package and JAR dependencies.
- Using one global mutable Spark session without ownership rules.
- Deleting checkpoints owned by another run.
- Logging tokens, connection strings, or secret-backed configuration.
- Treating provider acquisition as transformation execution.

## Key Principle

> A Spark Provider supplies the concrete Spark environment required by the
> PySpark Plugin while keeping sessions, clusters, credentials, catalogs,
> packages, and lifecycle concerns outside portable pipeline definitions.

## Next Step

Continue with [Testing Plugins](TESTING_PLUGINS.md) to apply shared conformance,
lifecycle, isolation, and security tests to Spark providers.
