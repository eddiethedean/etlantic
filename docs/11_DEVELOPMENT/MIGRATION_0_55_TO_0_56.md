---
title: Migration from ETLantic 0.55 to 0.56
status: candidate
current_minor: "0.56"
---

# Migration from 0.55 to 0.56

> **Status: 0.56.0 is a qualification candidate and is not published.**

## Candidate package line

Core and first-party distributions are qualified together at `0.56.0`; plugin
metadata requires `etlantic>=0.56.0,<0.57`. Do not mix 0.55 and 0.56
first-party packages in one environment. The published and
supported line remains 0.55.x until the candidate passes final release review
and is published.

## Partition repair and backfill

PostgreSQL partition actions require the provider binding to specify
`partition_column` and the operator profile to allow the required partition
read, replacement, and idempotency capabilities. Selectors are validated
before execution. The provider reads within the selected partitions and
replaces those partitions atomically with the effect record. An empty result
clears the selected partitions.

Existing non-partitioned pipelines need no configuration change. Other providers
remain unavailable for these actions until they advertise and implement the
required capabilities. Repair/backfill uses the normal managed authorization,
command identity, status, attempt and lineage surfaces.

## Input-resource owner migration

Input-resource ownership now defaults to a principal identity qualified by
issuer and principal kind. Deployments that persisted 0.55 resources under the
principal subject alone must preserve access explicitly: configure the trusted
server-side `ControlPlaneContext.resource_owner_id` mapping to the legacy owner
ID for those principals and scopes while old references remain active. Keep
that mapping out of request-controlled fields. Do not apply a subject-only
fallback globally: two principals with the same subject but different issuers
or kinds would otherwise share access to existing resources. New resources
created while the compatibility mapping is active use that mapped owner ID;
remove the mapping after old resources and references have expired or have
been reissued under the new qualified owner identity.

See [What's new in 0.56](../01_GETTING_STARTED/WHATS_NEW_0_56.md) and the
[phase qualification record](evidence/phase_0_56/LOCAL_QUALIFICATION.md).
