"""Unit tests for capability vocabulary /1."""

from etlantic.capabilities import (
    CAPABILITY_VOCABULARY_VERSION,
    PluginCapabilities,
    capability_conflicts,
    capability_implications,
    validate_capability_claims,
    vocabulary_major_compatible,
)


def test_vocabulary_version_constant_and_default() -> None:
    assert CAPABILITY_VOCABULARY_VERSION == "etlantic.capabilities/1"
    caps = PluginCapabilities(engine="demo")
    assert caps.vocabulary_version == CAPABILITY_VOCABULARY_VERSION
    restored = PluginCapabilities.from_dict(caps.to_dict())
    assert restored.vocabulary_version == CAPABILITY_VOCABULARY_VERSION


def test_vocabulary_major_compatible() -> None:
    assert vocabulary_major_compatible("etlantic.capabilities/1")
    assert vocabulary_major_compatible("etlantic.capabilities/1.0")
    assert not vocabulary_major_compatible("etlantic.capabilities/2")
    assert not vocabulary_major_compatible("etlantic.dataframe/1")
    assert not vocabulary_major_compatible("other")


def test_validate_capability_claims_missing_implication() -> None:
    caps = PluginCapabilities(engine="broken", sql_merge=True, sql=False)
    findings = validate_capability_claims(caps)
    assert findings
    assert any("sql_merge" in item and "sql" in item for item in findings)

    lazy_only = PluginCapabilities(
        engine="broken-lazy",
        lazy=True,
        eager=False,
        dataframe=False,
    )
    lazy_findings = validate_capability_claims(lazy_only)
    assert any("lazy" in item and "dataframe" in item for item in lazy_findings)

    spark_only = PluginCapabilities(
        engine="broken-spark", spark_merge=True, spark=False
    )
    spark_findings = validate_capability_claims(spark_only)
    assert any("spark_merge" in item and "spark" in item for item in spark_findings)


def test_validate_capability_claims_success() -> None:
    caps = PluginCapabilities(
        engine="ok",
        sql=True,
        sql_merge=True,
        spark=True,
        spark_merge=True,
        dataframe=True,
        lazy=True,
        orchestration=True,
        orch_retries=True,
    )
    assert validate_capability_claims(caps) == []


def test_storage_delta_extra_implications() -> None:
    from etlantic.storage import STORAGE_DELTA_CAPABILITY_EXTRAS

    broken = PluginCapabilities(
        engine="x",
        extras=frozenset({"storage.delta.merge"}),
    )
    findings = validate_capability_claims(broken)
    assert any("storage.delta.merge" in f for f in findings)
    assert STORAGE_DELTA_CAPABILITY_EXTRAS


def test_implications_and_conflicts_shapes() -> None:
    implications = capability_implications()
    assert implications["sql_merge"] == frozenset({"sql"})
    assert implications["spark_merge"] == frozenset({"spark"})
    assert implications["lazy"] == frozenset({"dataframe"})
    assert capability_conflicts() == []
