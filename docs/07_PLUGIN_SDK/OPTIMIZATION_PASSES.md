# Optimization Passes (0.45)

> **Status: Available in ETLantic 0.46.0.**

ETLantic's optimization SDK lets built-in and third-party **passes** propose
deterministic physical-plan changes with evidence, cost estimates, and semantic
proof obligations. Optimization is **advisory**: default `plan` / `run` emit
the baseline plan.

See [ADR-021](../11_DEVELOPMENT/adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md).

## Concepts

| Concept | Role |
|---|---|
| `OptimizationPass` | Propose candidates; no data/secret/registry authority |
| `EvidenceStore` | Plan-time statistics (cardinality, locality, reuse, …) |
| `CostProvider` | Rule-based or statistical scores (no universal currency) |
| `OptimizationExplanation` | Shared CLI / API / IDE explanation schema |
| `compare_shadow` | Baseline vs candidate plan comparison |

Wire schema: `etlantic.optimization/1`. Protocol: `etlantic.optimization-pass/1`.

## Authoring a pass

```python
from etlantic.optimization.protocol import (
    OptimizationCandidate,
    OptimizationContext,
    PassMetadata,
    ProofObligation,
)

class MyPass:
    metadata = PassMetadata(
        pass_id="acme.pass.example",
        version="1.0.0",
        rewrite_kinds=("fusion",),
        priority=90,
    )

    def propose(self, context: OptimizationContext):
        return (
            OptimizationCandidate(
                candidate_id="acme:1",
                pass_id=self.metadata.pass_id,
                rewrite_kind="fusion",
                decision="chosen",
                expected_benefit={"relative": 0.2},
                proofs=(ProofObligation(kind="schema", status="proven"),),
                evidence_refs=(),
                policy_result="accepted",
                capability_result="supported",
                reason="example",
                hints={"annotate": {"note": "acme"}},
            ),
        )
```

Register via entry point group `etlantic.optimization_passes`.

## Profile trust

```python
from etlantic import Profile

profile = Profile(
    name="production",
    security_mode="production",
    plugin_allowlist={"local": None},
    optimization_pass_allowlist={"acme.pass.example": "1.0.0"},
    optimization_policy="shadow",  # off | shadow | apply_accepted
)
```

Production fails closed on undeclared passes (`PMOPT140`).

## Conformance

```python
from etlantic.testing import run_optimizer_conformance_suite

run_optimizer_conformance_suite(MyPass())
```

## CLI

```bash
etlantic plan optimize TARGET --profile development
etlantic plan explain TARGET --optimization
etlantic plan diff baseline.json optimized.json
```
