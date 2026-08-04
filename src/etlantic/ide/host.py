"""Constrained trusted-workspace host for import-based analysis (0.44)."""

from __future__ import annotations

import concurrent.futures
from typing import Any

from etlantic.ide.protocol import IdeCommand, IdeResult
from etlantic.ide.trust import (
    TrustAuditRecord,
    TrustedWorkspacePolicy,
    classify_target,
    deny_analysis_secret_flags,
    deny_untrusted,
)


class TrustedAnalysisHost:
    """Host that may import user modules only under an enabled trust policy."""

    def __init__(self, policy: TrustedWorkspacePolicy) -> None:
        if not policy.enabled:
            raise ValueError("TrustedAnalysisHost requires an enabled policy")
        if not policy.allow_imports:
            raise ValueError("TrustedAnalysisHost requires allow_imports=True")
        self.policy = policy
        self.audit_log: list[TrustAuditRecord] = []

    def _audit(
        self, *, operation: str, target: str, require_imports: bool = True
    ) -> TrustAuditRecord:
        record = deny_untrusted(
            self.policy,
            operation=operation,
            target=target,
            require_imports=require_imports,
        )
        self.audit_log.append(record)
        return record

    def _deny_secret_flags(self, *, operation: str, target: str) -> None:
        blocked = deny_analysis_secret_flags(
            self.policy, operation=operation, target=target
        )
        if blocked is not None:
            self.audit_log.append(blocked)
            raise PermissionError(blocked.reason)

    def load_target(self, target: str) -> Any:
        """Load a target with path/allowlist checks and timeout."""
        record = self._audit(operation="load_target", target=target)
        if not record.allowed:
            raise PermissionError(record.reason)
        self._deny_secret_flags(operation="load_target", target=target)

        def _load() -> Any:
            from etlantic.cli.target import load_target

            return load_target(target)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_load)
            try:
                return future.result(timeout=self.policy.timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
                # Waiting aborts; the worker thread is not killed (documented).
                self.audit_log.append(
                    TrustAuditRecord(
                        operation="load_target",
                        target=target,
                        allowed=False,
                        reason=(
                            f"timed out after {self.policy.timeout_seconds}s "
                            "(waiter aborted; worker not killed)"
                        ),
                        policy=self.policy.to_dict(),
                    )
                )
                raise TimeoutError(
                    f"load_target timed out after {self.policy.timeout_seconds}s"
                ) from exc

    def execute(self, command: IdeCommand | dict[str, Any]) -> IdeResult:
        from etlantic.ide.commands import execute_command

        if isinstance(command, dict):
            command = IdeCommand(
                name=str(command["name"]),
                arguments=dict(command.get("arguments") or {}),
            )
        target = str(command.arguments.get("target", ""))
        if target:
            kind = classify_target(target)
            require_imports = kind in {"py_path", "module"}
            record = self._audit(
                operation=command.name,
                target=target,
                require_imports=require_imports,
            )
            if not record.allowed:
                return IdeResult(
                    name=command.name,
                    ok=False,
                    error=record.reason,
                )
            blocked = deny_analysis_secret_flags(
                self.policy, operation=command.name, target=target
            )
            if blocked is not None:
                self.audit_log.append(blocked)
                return IdeResult(
                    name=command.name,
                    ok=False,
                    error=blocked.reason,
                )
        return execute_command(command, policy=self.policy)
