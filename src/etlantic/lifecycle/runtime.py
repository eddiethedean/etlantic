"""PipelineRuntime — registries, lifespan, middleware, resources."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from etlantic.diagnostics import Diagnostic
from etlantic.lifecycle.callbacks import CallbackRegistry
from etlantic.lifecycle.middleware import MiddlewareStack
from etlantic.lifecycle.resources import ResourceManager
from etlantic.plugins.coordinator import PluginDiscoveryCoordinator, profile_plugin_key
from etlantic.profile import Profile
from etlantic.registry import RegistryBundle, builtin_stub_registry
from etlantic.reports.store import ReportStore
from etlantic.runtime.events import EventBus
from etlantic.secrets.cache import SecretCache
from etlantic.secrets.env import EnvSecretProvider
from etlantic.secrets.provider import SecretProvider
from etlantic.storage.callable_binding import CallableStorage
from etlantic.storage.csv_binding import CsvStorage
from etlantic.storage.json_binding import JsonStorage
from etlantic.storage.memory import MemoryStorage
from etlantic.storage.null import NullStorage
from etlantic.storage.protocol import StorageBinding

Lifespan = Callable[["PipelineRuntime"], AbstractAsyncContextManager[Any]]


@dataclass
class PipelineRuntime:
    """Process-scoped runtime coordinating local execution.

    Owns in-memory and file-backed storage bindings, plugin registries,
    middleware stacks, secret providers, and run reports. Application code
    creates one runtime per process (or per test) and passes it to
    :meth:`~etlantic.pipeline.Pipeline.run`.

    Call :meth:`ensure_plugins_for_profile` before the first run when using
    optional engine plugins so entry points are authorized and loaded for the
    active :class:`~etlantic.profile.Profile`.

    Built-in storage ids include ``memory``, ``local``, ``callable``, ``json``,
    ``csv``, and ``null``. Seed in-memory assets with
    :attr:`memory` (:class:`~etlantic.storage.memory.MemoryStorage`).
    """

    lifespan: Lifespan | None = None
    registry: RegistryBundle = field(default_factory=builtin_stub_registry)
    resources: ResourceManager = field(default_factory=ResourceManager)
    callbacks: CallbackRegistry = field(default_factory=CallbackRegistry)
    reports: ReportStore = field(default_factory=ReportStore)
    events: EventBus = field(default_factory=EventBus)
    secret_cache: SecretCache = field(default_factory=SecretCache)
    run_middleware: MiddlewareStack = field(default_factory=MiddlewareStack)
    step_middleware: MiddlewareStack = field(default_factory=MiddlewareStack)
    provider_middleware: MiddlewareStack = field(default_factory=MiddlewareStack)
    secret_providers: dict[str, SecretProvider] = field(default_factory=dict)
    storage: dict[str, StorageBinding] = field(default_factory=dict)
    dataframe_plugins: dict[str, Any] = field(default_factory=dict)
    sql_plugins: dict[str, Any] = field(default_factory=dict)
    spark_plugins: dict[str, Any] = field(default_factory=dict)
    spark_providers: dict[str, Any] = field(default_factory=dict)
    orchestrator_plugins: dict[str, Any] = field(default_factory=dict)
    scheduler_plugins: dict[str, Any] = field(default_factory=dict)
    memory: MemoryStorage = field(default_factory=MemoryStorage)
    callables: CallableStorage = field(default_factory=CallableStorage)
    _entered: bool = False
    _configured_profile_key: str | None = field(default=None, repr=False)
    _plugin_diagnostics: list[Diagnostic] = field(default_factory=list, repr=False)
    _manual_dataframe_plugins: dict[str, Any] = field(default_factory=dict, repr=False)
    _manual_sql_plugins: dict[str, Any] = field(default_factory=dict, repr=False)
    _manual_spark_plugins: dict[str, Any] = field(default_factory=dict, repr=False)
    _manual_spark_providers: dict[str, Any] = field(default_factory=dict, repr=False)
    _manual_orchestrator_plugins: dict[str, Any] = field(
        default_factory=dict, repr=False
    )
    _manual_scheduler_plugins: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if (
            "env" not in self.secret_providers
            and "env-secrets" not in self.secret_providers
        ):
            env = EnvSecretProvider()
            self.secret_providers["env"] = env
            self.secret_providers["env-secrets"] = env
        if not self.storage:
            self.storage = {
                "memory": self.memory,
                "local": self.memory,
                "python": self.memory,
                "callable": self.callables,
                "json": JsonStorage(),
                "csv": CsvStorage(),
                "null": NullStorage(),
            }
        else:
            self.storage.setdefault("memory", self.memory)
            self.storage.setdefault("local", self.memory)
            self.storage.setdefault("python", self.memory)

    def ensure_plugins_for_profile(self, profile: Profile) -> list[Diagnostic]:
        """Discover and load plugins authorized for ``profile`` (0.20).

        Idempotent per profile key. No entry points are imported until this
        method runs (or manual ``register_*_plugin`` calls).

        When the profile key changes, previously *discovered* plugin maps are
        replaced (not merged) so a switch to a tighter allowlist cannot leave
        unauthorized entry-point plugins resident. Plugins registered via
        ``register_*_plugin`` are preserved and re-applied after discovery.
        """
        key = profile_plugin_key(profile)
        if self._configured_profile_key == key:
            return list(self._plugin_diagnostics)

        # Drop previously discovered (non-builtin) registry descriptors before
        # re-registering the authorized set for the new profile. Manual plugins
        # are re-registered below after discovery.
        _BUILTIN_PLUGIN_NAMES = frozenset({"local", "null", "env", "env-secrets"})
        for name in list(self.registry.plugins):
            if name not in _BUILTIN_PLUGIN_NAMES:
                descriptor = self.registry.plugins.pop(name)
                if descriptor.engine and descriptor.engine in self.registry.engines:
                    # Only drop engine caps when no remaining plugin claims them.
                    still = any(
                        d.engine == descriptor.engine
                        for d in self.registry.plugins.values()
                    )
                    if not still:
                        self.registry.engines.pop(descriptor.engine, None)
                if name in self.registry.secret_providers:
                    self.registry.secret_providers.pop(name, None)

        coordinator = PluginDiscoveryCoordinator()
        result = coordinator.discover_for_profile(
            profile,
            registry=self.registry,
            register_to_registry=True,
            include_runtime_groups=True,
            include_transform_compilers=True,
        )
        # Replace discovered maps, then restore explicit manual registrations
        # (tests / app wiring inject configured plugin instances).
        self.dataframe_plugins = {
            **dict(result.dataframe_plugins),
            **self._manual_dataframe_plugins,
        }
        self.sql_plugins = {**dict(result.sql_plugins), **self._manual_sql_plugins}
        self.spark_plugins = {
            **dict(result.spark_plugins),
            **self._manual_spark_plugins,
        }
        self.spark_providers = {
            **dict(result.spark_providers),
            **self._manual_spark_providers,
        }
        self.orchestrator_plugins = {
            **dict(result.orchestrator_plugins),
            **self._manual_orchestrator_plugins,
        }
        self.scheduler_plugins = {
            **dict(result.scheduler_plugins),
            **self._manual_scheduler_plugins,
        }
        if self._manual_dataframe_plugins:
            from etlantic.dataframe.discovery import (
                register_discovered_plugins as register_df,
            )

            register_df(
                self.registry, plugins=self._manual_dataframe_plugins, profile=profile
            )
        if self._manual_sql_plugins:
            from etlantic.sql.discovery import (
                register_discovered_plugins as register_sql,
            )

            register_sql(
                self.registry, plugins=self._manual_sql_plugins, profile=profile
            )
        if self._manual_spark_plugins:
            from etlantic.spark.discovery import (
                register_discovered_plugins as register_spark,
            )

            register_spark(
                self.registry, plugins=self._manual_spark_plugins, profile=profile
            )
        if self._manual_orchestrator_plugins:
            from etlantic.orchestration.discovery import (
                register_discovered_plugins as register_orch,
            )

            register_orch(
                self.registry,
                plugins=self._manual_orchestrator_plugins,
                profile=profile,
            )
        self._configured_profile_key = key
        self._plugin_diagnostics = list(result.diagnostics)
        return list(result.diagnostics)

    def add_run_middleware(self, middleware: Any, *, name: str | None = None) -> None:
        """Register middleware invoked around entire pipeline runs.

        Args:
            middleware: Callable or async callable conforming to the run
                middleware protocol.
            name: Optional stable name for ordering and diagnostics.
        """
        self.run_middleware.add(middleware, name=name)

    def add_step_middleware(self, middleware: Any, *, name: str | None = None) -> None:
        """Register middleware invoked around individual step execution.

        Args:
            middleware: Callable or async callable conforming to the step
                middleware protocol.
            name: Optional stable name for ordering and diagnostics.
        """
        self.step_middleware.add(middleware, name=name)

    def override_resource(self, name: str, provider: Callable[..., Any]) -> None:
        """Replace a named injectable resource provider for this runtime.

        Args:
            name: Resource key referenced by :class:`~etlantic.lifecycle.Inject`.
            provider: Factory callable resolved at execution time.
        """
        self.resources.override(name, provider)

    def register_secret_provider(self, name: str, provider: SecretProvider) -> None:
        """Register a secret provider under ``name``.

        Args:
            name: Provider id referenced by profile ``secret_providers``.
            provider: Implementation of :class:`~etlantic.secrets.provider.SecretProvider`.
        """
        self.secret_providers[name] = provider

    def register_storage(self, name: str, binding: StorageBinding) -> None:
        """Register a storage binding under ``name``.

        Args:
            name: Provider id referenced by profile ``assets`` / bindings.
            binding: Storage implementation (JSON, CSV, SQL-backed, …).
        """
        self.storage[name] = binding

    def register_dataframe_plugin(self, engine: str, plugin: Any) -> None:
        """Register a live dataframe plugin and its planning descriptor."""
        from etlantic.dataframe.discovery import register_discovered_plugins

        self.dataframe_plugins[engine] = plugin
        self._manual_dataframe_plugins[engine] = plugin
        register_discovered_plugins(self.registry, plugins={engine: plugin})

    def register_sql_plugin(self, engine: str, plugin: Any) -> None:
        """Register a live SQL plugin and its planning descriptor."""
        from etlantic.sql.discovery import register_discovered_plugins

        self.sql_plugins[engine] = plugin
        self._manual_sql_plugins[engine] = plugin
        register_discovered_plugins(self.registry, plugins={engine: plugin})

    def register_spark_plugin(self, engine: str, plugin: Any) -> None:
        """Register a live Spark plugin and its planning descriptor."""
        from etlantic.spark.discovery import register_discovered_plugins

        self.spark_plugins[engine] = plugin
        self._manual_spark_plugins[engine] = plugin
        register_discovered_plugins(self.registry, plugins={engine: plugin})

    def register_spark_provider(self, name: str, provider: Any) -> None:
        """Register a live Spark session provider."""
        self.spark_providers[name] = provider
        self._manual_spark_providers[name] = provider

    def register_orchestrator_plugin(self, engine: str, plugin: Any) -> None:
        """Register a live orchestrator plugin and its planning descriptor."""
        from etlantic.orchestration.discovery import register_discovered_plugins

        self.orchestrator_plugins[engine] = plugin
        self._manual_orchestrator_plugins[engine] = plugin
        register_discovered_plugins(self.registry, plugins={engine: plugin})

    def register_scheduler_plugin(self, name: str, plugin: Any) -> None:
        """Register a live ExecutionScheduler plugin and its planning descriptor."""
        from etlantic.runtime.scheduler_discovery import register_discovered_plugins

        self.scheduler_plugins[name] = plugin
        self._manual_scheduler_plugins[name] = plugin
        register_discovered_plugins(self.registry, plugins={name: plugin})

    def apply_plugin_allowlist(self, profile: Any) -> list[Any]:
        """Filter discovered plugins using ``profile.plugin_allowlist``.

        Deprecated: prefer :meth:`ensure_plugins_for_profile` which authorizes
        before import. This method re-runs profile-aware discovery.
        """
        from etlantic.profile import Profile as ProfileType

        if isinstance(profile, ProfileType):
            return self.ensure_plugins_for_profile(profile)
        from etlantic.profile import resolve_profile

        return self.ensure_plugins_for_profile(resolve_profile(profile))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[PipelineRuntime]:
        """Enter runtime lifespan (if any)."""
        if self.lifespan is None:
            self._entered = True
            try:
                yield self
            finally:
                self._entered = False
                await self.resources.cleanup_scope("runtime")
            return

        async with self.lifespan(self):
            self._entered = True
            try:
                yield self
            finally:
                self._entered = False
                await self.resources.cleanup_scope("runtime")
