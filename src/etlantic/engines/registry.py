# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Central engine family registry and priority resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from etlantic.engines.family import ExecutionFamily
from etlantic.engines.protocol import EngineFamily
from etlantic.profile import Profile


@dataclass(frozen=True, slots=True)
class _BuiltinFamily:
    name: str
    aliases: frozenset[str]
    entry_point_group: str | None
    capability_defaults: tuple[str, ...] = ()

    def matches(self, engine: str) -> bool:
        return engine in self.aliases

    def default_capabilities(self, profile: Profile) -> list[str]:
        caps = list(self.capability_defaults)
        if self.name == "sql":
            caps.extend(profile.required_sql_capabilities)
        elif self.name == "spark":
            caps.extend(profile.required_spark_capabilities)
            if profile.spark_streaming:
                caps.extend(["streaming", "spark_streaming"])
        return caps


# Known first-party names for profile primary resolution / defaults only.
# Not a privilege allowlist — third-party engines register via discovery and
# are classified through capabilities (see resolve_execution_family).
_LOCAL = _BuiltinFamily("local", frozenset({"local", "null"}), None, ())
_DATAFRAME = _BuiltinFamily(
    "dataframe",
    frozenset({"polars", "pandas"}),
    "etlantic.dataframe_plugins",
    ("dataframe", "eager"),
)
_SQL = _BuiltinFamily(
    "sql",
    frozenset({"sql"}),
    "etlantic.sql_plugins",
    ("sql", "transactions", "sql_catalog_inspect"),
)
_SPARK = _BuiltinFamily(
    "spark",
    frozenset({"pyspark", "spark"}),
    "etlantic.spark_plugins",
    ("spark", "lazy", "schema_inspection"),
)

_BUILTIN_FAMILIES: tuple[_BuiltinFamily, ...] = (
    _LOCAL,
    _DATAFRAME,
    _SQL,
    _SPARK,
)

# spark → sql → dataframe/local (single priority implementation)
_PRIORITY: tuple[_BuiltinFamily, ...] = (_SPARK, _SQL, _DATAFRAME, _LOCAL)

_FAMILY_TO_EXECUTION: dict[str, ExecutionFamily] = {
    "local": ExecutionFamily.LOCAL,
    "dataframe": ExecutionFamily.DATAFRAME,
    "sql": ExecutionFamily.SQL,
    "spark": ExecutionFamily.SPARK,
}


def _capability_flag(capabilities: Any, name: str) -> bool:
    return bool(getattr(capabilities, name, False))


def _plugins_with_kind(engines: Any, engine: str, kind: str) -> bool:
    """Return True when ``engines`` looks like a registry with matching plugins."""
    plugins = getattr(engines, "plugins", None)
    if plugins is None and isinstance(engines, dict):
        return False
    if not isinstance(plugins, dict):
        return False
    return any(
        getattr(descriptor, "engine", None) == engine
        and getattr(descriptor, "kind", None) == kind
        for descriptor in plugins.values()
    )


def _engines_map(engines: dict[str, Any] | Any | None) -> dict[str, Any]:
    if engines is None:
        return {}
    if isinstance(engines, dict):
        return engines
    nested = getattr(engines, "engines", None)
    return nested if isinstance(nested, dict) else {}


class EngineRegistry:
    """Resolve engine families and profile-primary engines."""

    def __init__(self, families: tuple[EngineFamily, ...] | None = None) -> None:
        self._families: tuple[EngineFamily, ...] = (
            families
            if families is not None
            else cast(tuple[EngineFamily, ...], _BUILTIN_FAMILIES)
        )

    def resolve_family(
        self,
        engine: str,
        engines: dict[str, Any] | Any | None = None,
    ) -> EngineFamily | None:
        """Resolve builtin family aliases, or capability-backed family when present."""
        caps_map = _engines_map(engines)
        capabilities = caps_map.get(engine)
        if capabilities is not None:
            if _capability_flag(capabilities, "spark"):
                return cast(EngineFamily, _SPARK)
            if _capability_flag(capabilities, "sql"):
                return cast(EngineFamily, _SQL)
            if _capability_flag(capabilities, "dataframe"):
                return cast(EngineFamily, _DATAFRAME)
        for family in self._families:
            if family.matches(engine):
                return family
        return None

    def resolve_execution_family(
        self,
        engine: str,
        engines: dict[str, Any] | Any | None = None,
    ) -> ExecutionFamily | None:
        """Classify an engine via capabilities / registration, then builtin aliases."""
        from etlantic.capabilities import PluginCapabilities

        caps_map = _engines_map(engines)
        capabilities = caps_map.get(engine)
        if isinstance(capabilities, PluginCapabilities) or capabilities is not None:
            if _capability_flag(capabilities, "spark"):
                return ExecutionFamily.SPARK
            if _capability_flag(capabilities, "sql"):
                return ExecutionFamily.SQL
            if _capability_flag(capabilities, "orchestration"):
                return ExecutionFamily.ORCHESTRATION
            if _capability_flag(capabilities, "secret_provider"):
                return ExecutionFamily.SECRET
            if _capability_flag(capabilities, "dataframe"):
                return ExecutionFamily.DATAFRAME
        if _plugins_with_kind(engines, engine, "spark"):
            return ExecutionFamily.SPARK
        if _plugins_with_kind(engines, engine, "sql"):
            return ExecutionFamily.SQL
        if _plugins_with_kind(engines, engine, "dataframe"):
            return ExecutionFamily.DATAFRAME
        if _plugins_with_kind(engines, engine, "orchestrator"):
            return ExecutionFamily.ORCHESTRATION
        if _plugins_with_kind(engines, engine, "scheduler"):
            return ExecutionFamily.SCHEDULER
        if _plugins_with_kind(engines, engine, "secret"):
            return ExecutionFamily.SECRET
        if _plugins_with_kind(engines, engine, "transform_compiler"):
            return ExecutionFamily.TRANSFORM_COMPILER

        family = self.resolve_family(engine)
        if family is None:
            if engine in {"local", "null", ""}:
                return ExecutionFamily.LOCAL
            return None
        return _FAMILY_TO_EXECUTION.get(family.name)

    def primary_family(self, profile: Profile) -> EngineFamily:
        if profile.spark_engine:
            return cast(EngineFamily, _SPARK)
        if profile.sql_engine:
            return cast(EngineFamily, _SQL)
        return (
            cast(EngineFamily, _DATAFRAME)
            if (profile.dataframe_engine or "local") != "local"
            else cast(EngineFamily, _LOCAL)
        )

    def primary_engine(self, profile: Profile) -> str:
        if profile.spark_engine:
            return profile.spark_engine
        if profile.sql_engine:
            return profile.sql_engine
        return profile.dataframe_engine or "local"

    def primary_engine_field(self, profile: Profile) -> str:
        if profile.spark_engine:
            return "spark_engine"
        if profile.sql_engine:
            return "sql_engine"
        return "dataframe_engine"

    def default_capabilities(self, profile: Profile) -> list[str]:
        return self.primary_family(profile).default_capabilities(profile)

    def is_dataframe_engine(
        self,
        engine: str,
        engines: dict[str, Any] | Any | None = None,
    ) -> bool:
        """Return True when capabilities/registration say dataframe, else builtin fallback.

        ``DATAFRAME_ENGINES`` is a non-privileged compat fallback for known
        first-party names during transition — not an allowlist.
        """
        from etlantic.capabilities import PluginCapabilities
        from etlantic.dataframe.protocol import DATAFRAME_ENGINES

        caps_map = _engines_map(engines)
        capabilities = caps_map.get(engine)
        if isinstance(capabilities, PluginCapabilities) and capabilities.dataframe:
            return True
        if capabilities is not None and _capability_flag(capabilities, "dataframe"):
            return True
        if _plugins_with_kind(engines, engine, "dataframe"):
            return True
        return engine in DATAFRAME_ENGINES

    def is_sql_engine(
        self,
        engine: str,
        engines: dict[str, Any] | Any | None = None,
    ) -> bool:
        """Return True when capabilities/registration say sql, else builtin fallback."""
        from etlantic.capabilities import PluginCapabilities
        from etlantic.sql.protocol import SQL_ENGINES

        caps_map = _engines_map(engines)
        capabilities = caps_map.get(engine)
        if isinstance(capabilities, PluginCapabilities) and capabilities.sql:
            return True
        if capabilities is not None and _capability_flag(capabilities, "sql"):
            return True
        if _plugins_with_kind(engines, engine, "sql"):
            return True
        return engine in SQL_ENGINES

    def is_spark_engine(
        self,
        engine: str,
        engines: dict[str, Any] | Any | None = None,
    ) -> bool:
        """Return True when capabilities say spark; ``SPARK_ENGINES`` aliases as fallback."""
        from etlantic.capabilities import PluginCapabilities
        from etlantic.spark.protocol import SPARK_ENGINES

        caps_map = _engines_map(engines)
        capabilities = caps_map.get(engine)
        if isinstance(capabilities, PluginCapabilities) and capabilities.spark:
            return True
        if capabilities is not None and _capability_flag(capabilities, "spark"):
            return True
        if _plugins_with_kind(engines, engine, "spark"):
            return True
        return engine in SPARK_ENGINES

    def normalize_spark_alias(self, engine: str) -> str:
        if engine == "spark":
            return "pyspark"
        return engine


_DEFAULT_REGISTRY = EngineRegistry()


def get_engine_registry() -> EngineRegistry:
    return _DEFAULT_REGISTRY
