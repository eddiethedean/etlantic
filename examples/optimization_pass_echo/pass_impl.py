"""Example third-party optimization pass for ETLantic 0.45.

Install as an editable example or register via entry points::

    [project.entry-points."etlantic.optimization_passes"]
    echo = "examples.optimization_pass_echo.pass_impl:EchoOptimizationPass"

Pin against ``etlantic>=0.47.0,<0.48``.
"""

from __future__ import annotations

from etlantic.optimization.protocol import (
    OptimizationCandidate,
    OptimizationContext,
    PassMetadata,
    ProofObligation,
)


class EchoOptimizationPass:
    """No-op pass that proposes a rejected echo candidate (conformance fixture)."""

    metadata = PassMetadata(
        pass_id="example.pass.echo",
        version="1.0.0",
        rewrite_kinds=("pruning",),
        priority=200,
        description="External example optimization pass",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        _ = context
        return (
            OptimizationCandidate(
                candidate_id="echo:noop",
                pass_id=self.metadata.pass_id,
                rewrite_kind="pruning",
                decision="rejected",
                expected_benefit={},
                proofs=(
                    ProofObligation(
                        kind="dependency",
                        status="proven",
                        detail="echo pass never rewrites",
                    ),
                ),
                evidence_refs=(),
                policy_result="accepted",
                capability_result="supported",
                reason="echo example does not rewrite",
            ),
        )


def create_echo_pass() -> EchoOptimizationPass:
    """Entry-point factory."""
    return EchoOptimizationPass()
