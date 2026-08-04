"""Constrained trusted-workspace host for import-based analysis (0.44)."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any

from etlantic.ide.protocol import IdeCommand, IdeResult
from etlantic.ide.trust import TrustAuditRecord, TrustedWorkspacePolicy, deny_untrusted


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

    def load_target(self, target: str) -> Any:
        """Load a target with path/allowlist checks and timeout."""
        record = self._audit(operation="load_target", target=target)
        if not record.allowed:
            raise PermissionError(record.reason)
        module_part = target.rsplit(":", 1)[0] if ":" in target else target
        path = Path(module_part)
        if path.suffix == ".py" and not self.policy.permits_path(path):
            raise PermissionError(f"path outside allow_roots: {path}")
        # Analysis hosts never resolve secrets or query live production schemas.
        if self.policy.allow_secret_resolution or self.policy.allow_live_schema_query:
            raise PermissionError(
                "analysis hosts fail closed on secret resolution and live schema queries"
            )

        def _load() -> Any:
            from etlantic.cli.target import load_target

            return load_target(target)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_load)
            try:
                return future.result(timeout=self.policy.timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
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
            path = Path(target)
            is_json = path.suffix.lower() == ".json" and path.exists()
            if not is_json:
                record = self._audit(operation=command.name, target=target)
                if not record.allowed:
                    return IdeResult(
                        name=command.name,
                        ok=False,
                        error=record.reason,
                    )
        return execute_command(command, policy=self.policy)
