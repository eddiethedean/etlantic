"""Shared CLI context and runtime factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.output import render_diagnostic_human
from etlantic.diagnostics import Severity
from etlantic.io_policy import SafeIoPolicy
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.observability.history import FileRunHistoryProvider
from etlantic.profile import Profile
from etlantic.project import resolve_project_profile
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.store import ReportStore
from etlantic.workspace import (
    WorkspacePaths,
    ensure_workspace_layout,
    resolve_workspace,
)


@dataclass
class GlobalCliOptions:
    """Root callback options applied to all commands."""

    verbose: bool = False
    quiet: bool = False
    color: bool = True
    non_interactive: bool = False
    workspace: str | None = None
    ephemeral: bool = False
    default_profile: str | None = None
    accept_legacy_bindings: bool = False


@dataclass
class CliContext:
    """Shared CLI dependencies and workspace state."""

    load_target: Any
    globals: GlobalCliOptions = field(default_factory=GlobalCliOptions)
    workspace_paths: WorkspacePaths | None = None
    _runtime: PipelineRuntime | None = field(default=None, repr=False)
    _report_store: FileReportStore | ReportStore | None = field(
        default=None, repr=False
    )
    _run_history: FileRunHistoryProvider | None = field(default=None, repr=False)

    def workspace(self) -> WorkspacePaths:
        if self.workspace_paths is None:
            self.workspace_paths = resolve_workspace(
                workspace=self.globals.workspace,
            )
        return self.workspace_paths

    def report_store(self) -> FileReportStore | ReportStore:
        if self._report_store is not None:
            return self._report_store
        if self.globals.ephemeral:
            self._report_store = ReportStore()
        else:
            paths = self.workspace()
            ensure_workspace_layout(paths)
            policy = SafeIoPolicy.for_root(paths.reports)
            self._report_store = FileReportStore(paths.reports, policy=policy)
        return self._report_store

    def run_history(self) -> FileRunHistoryProvider | None:
        if self.globals.ephemeral:
            return None
        if self._run_history is not None:
            return self._run_history
        paths = self.workspace()
        ensure_workspace_layout(paths)
        history_root = paths.root / "history"
        policy = SafeIoPolicy.for_root(history_root)
        self._run_history = FileRunHistoryProvider(
            history_root, policy=policy, fail_closed=True
        )
        return self._run_history

    @property
    def runtime(self) -> PipelineRuntime:
        if self._runtime is None:
            store = self.report_store()
            self._runtime = PipelineRuntime(reports=store)
            history = self.run_history()
            if history is not None:
                self._runtime.register_run_history_provider("file", history)
        return self._runtime

    def resolve_profile(
        self,
        profile: str | None,
        *,
        allow_adhoc_profile: bool = False,
    ) -> tuple[Profile, str]:
        name = profile or self.globals.default_profile or "development"
        return resolve_project_profile(
            name,
            start=self.workspace().root,
            allow_adhoc_profile=allow_adhoc_profile,
            accept_legacy_bindings=self.globals.accept_legacy_bindings,
        )

    def ensure_plugins(
        self,
        profile: Profile,
        *,
        fmt: str = "human",
    ) -> None:
        diags = self.runtime.ensure_plugins_for_profile(profile)
        from etlantic.plugin_trust import _NON_BLOCKING_TRUST_CODES

        errors = [
            d
            for d in diags
            if d.severity is Severity.ERROR
            and getattr(d, "code", None) not in _NON_BLOCKING_TRUST_CODES
        ]
        if errors:
            if fmt == "sarif":
                from etlantic.cli.output import emit_payload
                from etlantic.diagnostics.sarif import diagnostics_to_sarif

                emit_payload(diagnostics_to_sarif(errors), fmt="sarif")
            elif fmt == "json":
                from etlantic.cli.output import diagnostic_to_dict, emit_payload

                emit_payload(
                    {
                        "ok": False,
                        "diagnostics": [diagnostic_to_dict(d) for d in errors],
                    },
                    fmt="json",
                )
            elif not self.globals.quiet:
                typer.echo("Plugin authorization failed:", err=True)
                for diagnostic in errors:
                    typer.echo(
                        render_diagnostic_human(
                            diagnostic, verbose=self.globals.verbose
                        ),
                        err=True,
                    )
            raise typer.Exit(ec.TRUST_FAILURE)

    def emit_mutation_preamble(
        self,
        *,
        command: str,
        target: str | None = None,
        profile: Profile | None = None,
        profile_source: str | None = None,
        write_intent: str | None = None,
        preview: bool = False,
        fmt: str = "human",
    ) -> None:
        if fmt == "json":
            payload = {
                "command": command,
                "target": target,
                "profile": profile.name if profile else None,
                "profile_source": profile_source,
                "security_mode": profile.security_mode if profile else None,
                "write_intent": write_intent,
                "ephemeral": self.globals.ephemeral,
                "workspace": str(self.workspace().root),
                "preview": preview,
            }
            from etlantic.cli.output import emit_payload

            emit_payload(payload, fmt="json", quiet=self.globals.quiet)
            return
        if self.globals.quiet:
            return
        typer.echo(f"command: {command}")
        if target:
            typer.echo(f"target: {target}")
        if profile is not None:
            typer.echo(f"profile: {profile.name} ({profile_source or 'unknown'})")
            typer.echo(f"security_mode: {profile.security_mode}")
        if write_intent:
            typer.echo(f"write_intent: {write_intent}")
        if self.globals.ephemeral:
            typer.echo("mode: ephemeral (process-local reports)")
        if preview:
            typer.echo("preview: true (no mutation)")

    def confirm_mutation(self, message: str) -> None:
        if self.globals.non_interactive:
            return
        if not typer.confirm(message, default=False):
            raise typer.Exit(ec.USAGE_ERROR)


def get_cli_context(ctx: typer.Context) -> CliContext:
    """Return CliContext stored on the Typer context object."""
    obj = ctx.obj
    if not isinstance(obj, CliContext):
        raise RuntimeError("CLI context not initialized")
    return obj
