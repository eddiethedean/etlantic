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

See [What's new in 0.56](../01_GETTING_STARTED/WHATS_NEW_0_56.md) and the
[phase qualification record](evidence/phase_0_56/LOCAL_QUALIFICATION.md).
