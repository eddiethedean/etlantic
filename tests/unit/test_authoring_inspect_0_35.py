"""Security and behavior tests for authoring inspect/rewrite/provenance (0.35)."""

from __future__ import annotations

from examples.memory_customers import CustomerPipeline

from etlantic.authoring import (
    FACADE_PROTOCOL_VERSION,
    EditCommand,
    definition_from_pipeline,
    definition_provenance,
    inspect_definition,
    negotiate_facade_protocol,
    pipeline_fingerprint,
    rewrite_definition,
)
from etlantic.authoring.inspect import DEFINITION_PROVENANCE_EXTENSION_KEY


def test_inspect_definition_is_secret_free_and_structural() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    summary = inspect_definition(defn)
    assert summary.schema == defn.schema
    assert summary.pipeline_id == defn.pipeline_id
    assert set(summary.node_names) == {"raw", "normalized", "curated"}
    assert summary.edge_count == 2
    assert summary.contract_fingerprints
    blob = summary.to_dict()
    text = str(blob).lower()
    for forbidden in ("password", "secret", "token", "rows", "records"):
        assert forbidden not in text or forbidden in (
            # allow only if part of unrelated identifiers — none expected
            "contract_fingerprints",
        )


def test_rewrite_definition_applies_edits_and_refreshes_fingerprint() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    before = pipeline_fingerprint(defn)
    result = rewrite_definition(
        defn,
        EditCommand(op="clone"),
        expected_token=before,
    )
    assert result.fingerprint
    assert result.definition.fingerprint == result.fingerprint
    assert result.fingerprint == pipeline_fingerprint(result.definition)


def test_rewrite_definition_fails_closed_on_bad_token() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    try:
        rewrite_definition(
            defn,
            EditCommand(op="clone"),
            expected_token="not-the-token",
        )
    except ValueError as exc:
        assert "concurrency" in str(exc).lower()
    else:
        raise AssertionError("expected concurrency failure")


def test_definition_provenance_attach_and_read() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    stamped = definition_provenance(
        defn,
        generator_id="medallantic.migrate.generate",
        source_fingerprint="abc123",
        facade_identity="medallantic",
        action="attach",
    )
    assert stamped is not None
    assert DEFINITION_PROVENANCE_EXTENSION_KEY in stamped.extensions
    read = definition_provenance(stamped, action="read")
    assert read is not None
    assert read.generator_id == "medallantic.migrate.generate"
    assert read.source_fingerprint == "abc123"
    assert read.facade_protocol_version == FACADE_PROTOCOL_VERSION
    summary = inspect_definition(stamped)
    assert summary.generator_id == "medallantic.migrate.generate"


def test_definition_provenance_rejects_secret_extras() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    try:
        definition_provenance(
            defn,
            generator_id="test",
            extras={"password": "nope"},
            action="attach",
        )
    except ValueError as exc:
        assert "secret" in str(exc).lower() or "password" in str(exc).lower()
    else:
        raise AssertionError("expected secret rejection")


def test_negotiate_facade_protocol() -> None:
    assert negotiate_facade_protocol(None) == FACADE_PROTOCOL_VERSION
    assert negotiate_facade_protocol("1") == "1"
    try:
        negotiate_facade_protocol("99")
    except ValueError:
        pass
    else:
        raise AssertionError("expected unsupported protocol failure")


def test_inspect_does_not_import_untrusted_code(monkeypatch) -> None:
    """Analysis must not trigger import machinery beyond the definition object."""
    import builtins

    defn = definition_from_pipeline(CustomerPipeline)
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        # Allow only stdlib/already-loaded packages if any import slips through.
        if name.startswith("examples.") or name.endswith("_evil"):
            raise AssertionError(f"unexpected import during inspect: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    inspect_definition(defn)
