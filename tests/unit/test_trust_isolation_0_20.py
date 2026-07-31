"""Tests for ETLantic 0.20 trust, isolation, and safe I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.capability_probe import CapabilityProbeResult
from etlantic.dataframe.discovery import discover_dataframe_plugins
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.exceptions import ETLanticError
from etlantic.interchange.security import UnsafeLoadError
from etlantic.io_policy import SafeIoPolicy, read_text_safe, write_text_safe
from etlantic.outbound import (
    OutboundDeniedError,
    OutboundPolicy,
    assert_outbound_allowed,
    evaluate_outbound_url,
)
from etlantic.plan.artifacts import (
    artifact_identity,
    assert_identity_compatible,
    cache_identity,
)
from etlantic.plugin_lifecycle import (
    authorize_plugins,
    discover_entry_points,
    discover_evaluate_authorize_load,
)
from etlantic.plugin_manifest import (
    PLUGIN_MANIFEST_SCHEMA,
    compute_manifest_digest,
    parse_plugin_manifest,
)
from etlantic.profile import Profile, load_profile, production_profile, write_profile
from etlantic.serialization_policy import (
    UnsafeSerializationError,
    assert_safe_load_path,
    is_unsafe_path,
)


def test_manifest_digest_roundtrip() -> None:
    payload = {
        "schema": PLUGIN_MANIFEST_SCHEMA,
        "package": "example-plugin",
        "version": "0.20.0",
        "protocol_range": "*",
        "entries": [],
        "capabilities": [],
        "privileges": [],
        "provenance": {},
    }
    payload["digest"] = compute_manifest_digest(payload)
    manifest, diags = parse_plugin_manifest(json.dumps(payload))
    assert not diags
    assert manifest is not None
    assert manifest.package == "example-plugin"


def test_manifest_missing_digest_fails_when_verify() -> None:
    payload = {
        "schema": PLUGIN_MANIFEST_SCHEMA,
        "package": "example-plugin",
        "version": "0.20.0",
        "protocol_range": "*",
        "entries": [],
        "capabilities": [],
        "privileges": [],
        "provenance": {},
    }
    manifest, diags = parse_plugin_manifest(json.dumps(payload), verify_digest=True)
    assert manifest is None
    assert any(d.code == "PMPLUG411" for d in diags)


def test_manifest_tamper_detected() -> None:
    payload = {
        "schema": PLUGIN_MANIFEST_SCHEMA,
        "package": "example-plugin",
        "version": "0.20.0",
        "protocol_range": "*",
        "entries": [],
        "capabilities": [],
        "privileges": [],
        "provenance": {},
        "digest": "sha256:deadbeef",
    }
    manifest, diags = parse_plugin_manifest(json.dumps(payload))
    assert manifest is None
    assert any(d.code == "PMPLUG411" for d in diags)


def test_disallowed_plugin_rejected_before_load() -> None:
    """Allowlist denial happens in authorize phase (no load of denied plugins)."""
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    profile = production_profile(
        plugin_allowlist={"definitely-not-installed": "==9.9.9"}
    )
    authorized, diags, events = authorize_plugins(discovered, profile)
    assert authorized == []
    assert any(d.code == "PMPLUG402" for d in diags)
    assert all(e.outcome == "denied" for e in events)
    assert all(e.kind == "plugin_authorization" for e in events)


def test_allowlist_rejects_engine_spoofing() -> None:
    """Allowlist matches package identity only — engine short names cannot spoof."""
    from etlantic.plugin_lifecycle import DiscoveredPlugin
    from etlantic.plugin_lifecycle.policies import ProductionPolicy

    fake = DiscoveredPlugin(
        group="etlantic.dataframe_plugins",
        name="polars",
        target="evil:create",
        distribution_name="evil-pkg",
        distribution_version="0.33.0",
        entry_point=type("EP", (), {"name": "polars", "value": "evil:create"})(),
        engine="etlantic-polars",
    )
    profile = production_profile(
        plugin_allowlist={"etlantic-polars": "==0.33.0"},
    )
    authorized, diags, _events = ProductionPolicy().authorize([fake], profile)
    assert authorized == []
    assert any(d.code == "PMPLUG402" for d in diags)


def test_allowlist_package_identity_authorizes() -> None:
    """Allowlist keys must match distribution/package identity."""
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    package = next(
        (item.distribution_name for item in discovered if item.distribution_name),
        None,
    )
    if package is None:
        pytest.skip("no distribution metadata available")
    profile = production_profile(plugin_allowlist={str(package): "==0.37.0"})
    authorized, diags, _events = authorize_plugins(discovered, profile)
    assert authorized, f"expected {package!r} to authorize; diags={diags}"
    assert all(
        item.authorization == "allowed"
        for item in authorized
        if item.distribution_name == package
    )


def test_production_allowlist_requires_version_pin() -> None:
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    package = next(
        (item.distribution_name for item in discovered if item.distribution_name),
        None,
    )
    if package is None:
        pytest.skip("no distribution metadata available")
    profile = production_profile(plugin_allowlist={str(package): None})
    authorized, diags, _events = authorize_plugins(discovered, profile)
    assert not any(
        item.authorization == "allowed"
        for item in authorized
        if item.distribution_name == package
    )
    assert any(d.code == "PMPLUG403" for d in diags)


def test_discover_dataframe_plugins_exposes_last_diagnostics() -> None:
    profile = production_profile(plugin_allowlist={})
    found = discover_dataframe_plugins(profile=profile)
    assert found == {}
    diags = getattr(discover_dataframe_plugins, "last_diagnostics", [])
    assert any(getattr(d, "code", None) == "PMPLUG401" for d in diags)


def test_builtin_local_exempt_from_package_allowlist() -> None:
    from etlantic.plugin_trust import filter_plugins_by_allowlist
    from etlantic.registry import PluginDescriptor

    profile = production_profile(
        plugin_allowlist={"etlantic-polars": "==0.27.0"},
    )
    local = PluginDescriptor(
        name="local", kind="runtime", version="0.27.0", engine="local"
    )
    kept, diags = filter_plugins_by_allowlist({"local": local}, profile)
    assert "local" in kept
    assert not any(d.code == "PMPLUG402" for d in diags)


def test_builtin_exemption_rejects_third_party_engine_spoof() -> None:
    """Third-party packages cannot skip allowlist by declaring engine=local."""
    from etlantic.plugin_lifecycle import DiscoveredPlugin
    from etlantic.plugin_lifecycle.policies import ProductionPolicy
    from etlantic.plugin_trust import filter_plugins_by_allowlist
    from etlantic.registry import PluginDescriptor

    fake = DiscoveredPlugin(
        group="etlantic.dataframe_plugins",
        name="local",
        target="evil:create",
        distribution_name="evil-pkg",
        distribution_version="1.0.0",
        entry_point=type("EP", (), {"name": "local", "value": "evil:create"})(),
        engine="local",
    )
    profile = production_profile(
        plugin_allowlist={"etlantic-polars": "==0.35.0"},
    )
    authorized, diags, _events = ProductionPolicy().authorize([fake], profile)
    assert authorized == []
    assert any(d.code == "PMPLUG402" for d in diags)

    spoofed = PluginDescriptor(
        name="local",
        kind="runtime",
        version="1.0.0",
        engine="local",
        metadata={"distribution_name": "evil-pkg"},
    )
    kept, filter_diags = filter_plugins_by_allowlist({"local": spoofed}, profile)
    assert "local" not in kept
    assert any(d.code == "PMPLUG402" for d in filter_diags)


def test_production_empty_allowlist_rejects_all() -> None:
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    profile = production_profile(plugin_allowlist={})
    authorized, diags, _events = authorize_plugins(discovered, profile)
    assert authorized == []
    assert any(d.code == "PMPLUG401" for d in diags)


def test_lifecycle_loads_when_allowlisted() -> None:
    plugins = discover_dataframe_plugins()
    if "polars" not in plugins and "pandas" not in plugins:
        pytest.skip("dataframe plugins not installed")
    # Non-production open allowlist
    found = discover_dataframe_plugins(
        profile=Profile(name="dev", security_mode="development")
    )
    assert found


def test_safe_io_rejects_root_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    policy = SafeIoPolicy.for_root(root)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(UnsafeLoadError):
        read_text_safe(outside, policy)


def test_safe_io_atomic_write_and_lock(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    policy = SafeIoPolicy.for_root(root)
    target = root / "report.json"
    result = write_text_safe(target, '{"ok": true}\n', policy, run_id="t1")
    assert target.exists()
    assert result.digest and result.digest.startswith("sha256:")
    _path, text, _ = read_text_safe(target, policy)
    assert "ok" in text


def test_safe_io_rejects_overwrite_when_configured(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    policy = SafeIoPolicy.for_root(root, overwrite_policy="reject")
    target = root / "once.json"
    write_text_safe(target, "a", policy)
    with pytest.raises(UnsafeLoadError) as exc:
        write_text_safe(target, "b", policy)
    assert exc.value.report.errors[0].code == "PMSRC113"


def test_safe_io_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    link = root / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not supported")
    policy = SafeIoPolicy.for_root(root, symlink_policy="reject")
    with pytest.raises(UnsafeLoadError):
        read_text_safe(link, policy)


def test_safe_io_reject_denies_in_root_dir_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    target = sub / "file.txt"
    target.write_text("ok", encoding="utf-8")
    linkdir = root / "linkdir"
    try:
        linkdir.symlink_to(sub)
    except OSError:
        pytest.skip("symlinks not supported")
    policy = SafeIoPolicy.for_root(root, symlink_policy="reject")
    with pytest.raises(UnsafeLoadError, match=r"Symlink"):
        read_text_safe(linkdir / "file.txt", policy)


def test_safe_io_empty_approved_roots_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    target.write_text("x", encoding="utf-8")
    policy = SafeIoPolicy(approved_roots=(), max_read_bytes=1024)
    with pytest.raises(UnsafeLoadError, match=r"approved_roots"):
        read_text_safe(target, policy)


def test_artifact_isolation_dimensions() -> None:
    a = artifact_identity(
        pipeline_id="p",
        node_name="n",
        port_name="out",
        security_domain="prod",
        tenant="t1",
        environment="staging",
        authorization="prod-profile",
    )
    b = artifact_identity(
        pipeline_id="p",
        node_name="n",
        port_name="out",
        security_domain="prod",
        tenant="t2",
        environment="staging",
        authorization="prod-profile",
    )
    assert a != b
    assert_identity_compatible(
        a, security_domain="prod", tenant="t1", environment="staging"
    )
    with pytest.raises(ETLanticError):
        assert_identity_compatible(
            a, security_domain="prod", tenant="t2", environment="staging"
        )


def test_cache_identity_includes_compiler_and_tenant() -> None:
    key = cache_identity(
        pipeline_id="p",
        node_name="n",
        port_name="out",
        security_domain="prod",
        plan_fingerprint="abc",
        compiler_fingerprint="polars@0.20.0",
        tenant="acme",
        environment="prod",
    )
    assert "acme" in key
    assert "+cc:polars@0.20.0" in key


def test_outbound_blocks_metadata_and_private() -> None:
    policy = OutboundPolicy(
        allowed_hosts=("api.example.com",), allowed_schemes=("https",)
    )
    denied = evaluate_outbound_url("http://169.254.169.254/latest", policy)
    assert not denied.allowed
    denied2 = evaluate_outbound_url("https://evil.example/", policy)
    assert not denied2.allowed
    assert denied2.event is not None
    assert denied2.event.schema_version.startswith("etlantic.security_event/")


def test_outbound_allows_explicit_host(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = OutboundPolicy(
        allowed_hosts=("api.example.com",),
        allowed_schemes=("https",),
    )

    def fake_getaddrinfo(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return [(None, None, None, None, ("93.184.216.34", port))]

    monkeypatch.setattr("etlantic.outbound.socket.getaddrinfo", fake_getaddrinfo)
    decision = assert_outbound_allowed("https://api.example.com/hooks", policy)
    assert decision.allowed


def test_outbound_blocks_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = OutboundPolicy(allowed_hosts=("localhost",), allow_loopback=False)

    def fake_getaddrinfo(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return [(None, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr("etlantic.outbound.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(OutboundDeniedError):
        assert_outbound_allowed("https://localhost/x", policy)


def test_unsafe_serialization_ban() -> None:
    assert is_unsafe_path("model.pkl")
    with pytest.raises(UnsafeSerializationError):
        assert_safe_load_path(Path("cache/joblib.joblib"))


def test_first_party_polars_manifest_readable() -> None:
    from importlib.metadata import distribution

    try:
        dist = distribution("etlantic-polars")
    except Exception:
        pytest.skip("etlantic-polars not installed")
    from etlantic.plugin_manifest import load_manifest_from_distribution

    manifest, diags = load_manifest_from_distribution(dist)
    # Editable installs should expose the package data file.
    if manifest is None:
        pytest.skip(f"manifest not packaged yet: {[d.message for d in diags]}")
    assert manifest.package == "etlantic-polars"
    assert manifest.schema == PLUGIN_MANIFEST_SCHEMA
    assert any(e.name == "polars" for e in manifest.entries)


def test_load_profile_rejects_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    root.mkdir()
    profile_path = root / "prod.json"
    write_profile(production_profile(name="prod"), profile_path)
    outside = tmp_path / "escape.json"
    try:
        outside.symlink_to(profile_path)
    except OSError:
        pytest.skip("symlinks not supported")
    with pytest.raises(UnsafeLoadError):
        load_profile(outside)


def test_capability_probe_failure_emits_pmplug432(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_probe(**kwargs):  # type: ignore[no-untyped-def]
        name = kwargs.get("name", "unknown")
        return CapabilityProbeResult(
            ok=False,
            summary={"ok": False, "error": "simulated"},
            diagnostics=(
                Diagnostic(
                    code="PMPLUG432",
                    severity=Severity.ERROR,
                    message="Capability probe failed (simulated).",
                    phase="plugin_probe",
                    path=("plugin", name),
                ),
            ),
        )

    monkeypatch.setattr(
        "etlantic.capability_probe.run_capability_probe",
        _fail_probe,
    )
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    item = discovered[0]
    allow_key = item.distribution_name or item.name
    pin = item.distribution_version or "0.36.0"
    profile = production_profile(
        plugin_allowlist={allow_key: f"=={pin}" if pin[0].isdigit() else pin},
        require_plugin_probe=True,
    )
    result = discover_evaluate_authorize_load(
        "etlantic.dataframe_plugins",
        profile=profile,
    )
    assert any(d.code == "PMPLUG432" for d in result.diagnostics)
    assert result.loaded == {}


def test_capability_probe_fail_closed_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_probe(**kwargs):  # type: ignore[no-untyped-def]
        return CapabilityProbeResult(
            ok=False,
            summary={"ok": False, "error": "simulated"},
            diagnostics=(),
        )

    monkeypatch.setattr(
        "etlantic.capability_probe.run_capability_probe",
        _fail_probe,
    )
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    profile = Profile(
        name="dev",
        security_mode="development",
        require_plugin_probe=True,
    )
    result = discover_evaluate_authorize_load(
        "etlantic.dataframe_plugins",
        profile=profile,
    )
    assert any(d.code == "PMPLUG432" for d in result.diagnostics)
    assert result.loaded == {}


def test_capability_probe_disabled_skips_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(subprocess, "run", _boom)
    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")
    profile = Profile(
        name="dev",
        security_mode="development",
        require_plugin_probe=False,
    )
    discover_evaluate_authorize_load(
        "etlantic.dataframe_plugins",
        profile=profile,
    )


def test_descriptor_metadata_preserves_third_party_package_identity() -> None:
    from etlantic.dataframe.discovery import register_discovered_plugins
    from etlantic.plugin_trust import (
        filter_plugins_by_allowlist,
        stamp_plugin_package_identity,
    )
    from etlantic.registry import builtin_stub_registry

    class _Info:
        name = "acme-widgets"
        version = "1.2.3"
        engine = "widgets"
        protocol_version = "1"
        capabilities = None

    class _Plugin:
        info = _Info()

    plugin = _Plugin()
    stamp_plugin_package_identity(
        plugin,
        distribution_name="acme-widgets",
        package="acme-widgets",
        distribution_version="1.2.3",
    )
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"widgets": plugin})
    descriptor = registry.plugins["acme-widgets"]
    assert descriptor.metadata.get("distribution_name") == "acme-widgets"
    profile = production_profile(plugin_allowlist={"acme-widgets": "==1.2.3"})
    kept, diags = filter_plugins_by_allowlist({"widgets": descriptor}, profile)
    assert "widgets" in kept
    assert not any(d.code == "PMPLUG402" for d in diags)


def test_manual_register_denied_under_active_production_profile() -> None:
    from etlantic.exceptions import PipelineExecutionError
    from etlantic.lifecycle.runtime import PipelineRuntime
    from etlantic.plugin_trust import stamp_plugin_package_identity

    class _Info:
        name = "evil-pkg"
        version = "9.9.9"
        engine = "evil"
        protocol_version = "1"
        capabilities = None

    class _Plugin:
        info = _Info()

    runtime = PipelineRuntime()
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.35.0"})
    runtime.ensure_plugins_for_profile(profile)
    plugin = _Plugin()
    stamp_plugin_package_identity(
        plugin, distribution_name="evil-pkg", package="evil-pkg"
    )
    with pytest.raises(PipelineExecutionError) as exc:
        runtime.register_dataframe_plugin("evil", plugin)
    assert exc.value.code in {"PMPLUG402", "PMPLUG401"}
