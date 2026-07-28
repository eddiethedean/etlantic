"""Pipeline authoring: Extract, Load, Pipeline, and subpipelines."""

from __future__ import annotations

import inspect
import itertools
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, TypeVar

from etlantic.contracts import is_data_contract_type
from etlantic.identity import contract_id, node_id, pipeline_id
from etlantic.model import (
    Edge,
    LogicalGraph,
    Node,
    NodeKind,
    ParameterSpec,
    PortSpec,
)
from etlantic.refs import OutputRef, as_output_ref
from etlantic.transformation import Step

T = TypeVar("T")

_subpipeline_key_counter = itertools.count(1)
_extract_key_counter = itertools.count(1)
_building_graphs: set[type[Any]] = set()


def _require_asset(asset: str | None, *, kwargs: dict[str, Any]) -> str:
    """Validate ``asset=`` and reject removed ``binding=`` authoring."""
    if "binding" in kwargs:
        raise TypeError(
            "binding= was removed in ETLantic 0.16. Use asset= instead. "
            "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
        )
    if asset is None:
        raise TypeError("Extract/Load require asset= (a non-empty logical name).")
    text = str(asset).strip()
    if not text:
        raise ValueError("asset identifiers must be non-empty logical names")
    return text


def _class_annotations(cls: type[Any]) -> dict[str, Any]:
    """Return evaluated class annotations (supports postponed evaluation)."""
    try:
        return inspect.get_annotations(cls, eval_str=True)
    except Exception:
        return dict(getattr(cls, "__annotations__", {}))


class _TypedFactory:
    """Callable ``Extract[T]`` / ``Load[T]`` factory that also works as an annotation."""

    __slots__ = ("__args__", "__origin__", "contract_type", "origin")

    def __init__(self, origin: type[Any], contract_type: type[Any]) -> None:
        self.origin = origin
        self.contract_type = contract_type
        self.__origin__ = origin
        self.__args__ = (contract_type,)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.origin(*args, contract_type=self.contract_type, **kwargs)

    def __repr__(self) -> str:
        name = getattr(self.contract_type, "__name__", self.contract_type)
        return f"{self.origin.__name__}[{name}]"


class Extract:
    """A typed logical entry boundary that introduces data into a pipeline.

    Constructing an ``Extract`` never reads data. Profiles resolve the logical
    ``asset`` name to an environment-specific provider at plan/runtime time.
    """

    __slots__ = (
        "asset",
        "contract_type",
        "name",
        "pipeline_id",
        "producer_key",
    )

    def __init__(
        self,
        asset: str | None = None,
        *,
        contract_type: type[Any] | None = None,
        name: str | None = None,
        pipeline_id: str | None = None,
        producer_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Create a logical extract boundary.

        Args:
            asset: Logical asset name resolved by the profile at plan/runtime.
            contract_type: Optional typed data contract for the extract output.
            name: Optional node name (set when bound into a ``Pipeline``).
            pipeline_id: Optional owning pipeline identity.
            producer_key: Stable producer key for graph wiring; auto-assigned
                when omitted.
            **kwargs: Rejected if it contains removed ``binding=``.

        Raises:
            TypeError: When ``asset`` is missing/``None``, or ``binding=`` is
                passed (removed in 0.16).
            ValueError: When ``asset`` is empty/whitespace.
        """
        self.asset = _require_asset(asset, kwargs=kwargs)
        self.contract_type = contract_type
        self.name = name
        self.pipeline_id = pipeline_id
        self.producer_key = producer_key or f"source-{next(_extract_key_counter)}"

    def __class_getitem__(cls, item: type[Any]) -> _TypedFactory:
        return _TypedFactory(cls, item)

    def __repr__(self) -> str:
        ctype = getattr(self.contract_type, "__name__", self.contract_type)
        return (
            f"{type(self).__name__}(asset={self.asset!r}, "
            f"contract_type={ctype!r}, name={self.name!r})"
        )

    @property
    def result(self) -> OutputRef[Any]:
        """Default output reference for this extract.

        Returns:
            Same as :meth:`as_output_ref` with port ``"result"``.
        """
        return self.as_output_ref()

    def as_output_ref(self, *, default_port: str = "result") -> OutputRef[Any]:
        """Return an OutputRef for this extract's produced dataset.

        Args:
            default_port: Output port name (default ``"result"``).

        Returns:
            An :class:`~etlantic.refs.OutputRef` pointing at this extract.
        """
        name = self.name or ""
        return OutputRef(
            node_name=name,
            port_name=default_port,
            contract_type=self.contract_type,
            pipeline_id=self.pipeline_id,
            node_kind="source",
            producer_key=self.producer_key,
        )

    def bind(self, name: str, *, pipeline_id: str | None = None) -> Extract:
        """Return an extract bound to a node name within a pipeline.

        Args:
            name: Node name assigned in the parent pipeline class body.
            pipeline_id: Optional owning pipeline identity.

        Returns:
            A new ``Extract`` with the same asset/contract and bound name.
        """
        return type(self)(
            asset=self.asset,
            contract_type=self.contract_type,
            name=name,
            pipeline_id=pipeline_id,
            producer_key=self.producer_key,
        )


class Load:
    """A typed logical publication boundary that receives data from a pipeline.

    Constructing a ``Load`` never writes data. Profiles resolve the logical
    ``asset`` name to an environment-specific provider at plan/runtime time.
    """

    __slots__ = (
        "asset",
        "contract_type",
        "input",
        "name",
        "pipeline_id",
    )

    def __init__(
        self,
        input: Any = None,
        asset: str | None = None,
        *,
        contract_type: type[Any] | None = None,
        name: str | None = None,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Create a logical load boundary.

        Args:
            input: Upstream output reference or step result feeding this load.
            asset: Logical asset name resolved by the profile at plan/runtime.
            contract_type: Optional typed data contract for the published data.
            name: Optional node name (set when bound into a ``Pipeline``).
            pipeline_id: Optional owning pipeline identity.
            **kwargs: Rejected if it contains removed ``binding=``.

        Raises:
            TypeError: When ``asset`` is missing/``None``, or ``binding=`` is
                passed (removed in 0.16).
            ValueError: When ``asset`` is empty/whitespace.
        """
        self.input = input
        self.asset = _require_asset(asset, kwargs=kwargs)
        self.contract_type = contract_type
        self.name = name
        self.pipeline_id = pipeline_id

    def __class_getitem__(cls, item: type[Any]) -> _TypedFactory:
        return _TypedFactory(cls, item)

    def __repr__(self) -> str:
        ctype = getattr(self.contract_type, "__name__", self.contract_type)
        return (
            f"{type(self).__name__}(asset={self.asset!r}, "
            f"contract_type={ctype!r}, name={self.name!r})"
        )

    def bind(self, name: str, *, pipeline_id: str | None = None) -> Load:
        """Return a load bound to a node name within a pipeline.

        Args:
            name: Node name assigned in the parent pipeline class body.
            pipeline_id: Optional owning pipeline identity.

        Returns:
            A new ``Load`` with the same input/asset/contract and bound name.
        """
        return type(self)(
            input=self.input,
            asset=self.asset,
            contract_type=self.contract_type,
            name=name,
            pipeline_id=pipeline_id,
        )


@dataclass
class SubpipelineInstance:
    """An embedded child pipeline with parent-side bindings."""

    pipeline_cls: type[Pipeline]
    bindings: dict[str, Any]
    name: str | None = None
    pipeline_id: str | None = None
    producer_key: str = field(
        default_factory=lambda: f"subpipeline-{next(_subpipeline_key_counter)}"
    )
    _outputs: dict[str, OutputRef[Any]] = field(default_factory=dict, repr=False)

    def bind_name(
        self, name: str, *, pipeline_id: str | None = None
    ) -> SubpipelineInstance:
        """Bind this subpipeline instance to a parent node name.

        Args:
            name: Parent-side node name for this embedded pipeline.
            pipeline_id: Optional owning parent pipeline identity.

        Returns:
            A new instance with sink outputs exposed as attributes.
        """
        child_graph = self.pipeline_cls.build_graph()
        outputs: dict[str, OutputRef[Any]] = {}
        for node in child_graph.nodes:
            if node.kind is NodeKind.SINK:
                outputs[node.name] = OutputRef(
                    node_name=name,
                    port_name=node.name,
                    contract_type=node.contract_type,
                    pipeline_id=pipeline_id,
                    node_kind="subpipeline",
                    producer_key=self.producer_key,
                )
        return SubpipelineInstance(
            pipeline_cls=self.pipeline_cls,
            bindings=dict(self.bindings),
            name=name,
            pipeline_id=pipeline_id,
            producer_key=self.producer_key,
            _outputs=outputs,
        )

    def __getattr__(self, item: str) -> OutputRef[Any]:
        if item.startswith("_"):
            raise AttributeError(item)
        if item in self._outputs:
            return self._outputs[item]
        child = self.pipeline_cls.build_graph()
        for node in child.nodes:
            if node.kind is NodeKind.SINK and node.name == item:
                return OutputRef(
                    node_name=self.name or "",
                    port_name=item,
                    contract_type=node.contract_type,
                    pipeline_id=self.pipeline_id,
                    node_kind="subpipeline",
                    producer_key=self.producer_key,
                )
        available = ", ".join(sorted(self._outputs)) or "(none)"
        msg = f"Subpipeline has no public output {item!r}. Available: {available}"
        raise AttributeError(msg)


class _PipelineNamespace(dict[str, Any]):
    """Class body namespace that records declaration order of pipeline members."""

    def __init__(self) -> None:
        super().__init__()
        self._member_order: list[str] = []

    def __setitem__(self, key: str, value: Any) -> None:
        if (
            not key.startswith("_")
            and key not in self
            and isinstance(value, (Extract, Load, Step, SubpipelineInstance))
        ):
            self._member_order.append(key)
        super().__setitem__(key, value)


class _PipelineMeta(type):
    """Metaclass that preserves pipeline member declaration order."""

    @classmethod
    def __prepare__(
        mcs, name: str, bases: tuple[type, ...], **kwargs: Any
    ) -> _PipelineNamespace:
        return _PipelineNamespace()

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> _PipelineMeta:
        order = list(getattr(namespace, "_member_order", []))
        cls = super().__new__(mcs, name, bases, dict(namespace))
        cls.__member_order__ = order  # type: ignore[attr-defined]
        return cls


class Pipeline(metaclass=_PipelineMeta):
    """Declarative typed pipeline graph.

    Subclasses declare ``Extract``, transformation ``Step``, ``Load``, and
    optional subpipeline members. Importing a pipeline does not execute it.
    """

    __member_order__: ClassVar[list[str]] = []
    __pipeline_members__: ClassVar[dict[str, Any]] = {}
    _cached_graph: ClassVar[LogicalGraph | None] = None
    _graph_build_error: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls is Pipeline:
            return
        members = _collect_pipeline_members(cls)
        cls.__pipeline_members__ = members
        cls._cached_graph = None
        cls._graph_build_error = None

    @classmethod
    def identity(cls) -> str:
        """Return the stable pipeline identity string.

        Returns:
            Deterministic identity derived from the pipeline class.
        """
        return pipeline_id(cls)

    @classmethod
    def build_graph(cls) -> LogicalGraph:
        """Build (and cache) the immutable logical graph for this pipeline.

        Returns:
            A :class:`~etlantic.model.LogicalGraph`. Cyclic subpipeline nesting
            yields an empty graph with ``cyclic_subpipeline`` metadata rather
            than raising.
        """
        if cls._cached_graph is not None:
            return cls._cached_graph
        if cls in _building_graphs:
            cls._graph_build_error = (
                f'Cyclic subpipeline nesting detected while building "{cls.__name__}".'
            )
            return LogicalGraph(
                pipeline_id=pipeline_id(cls),
                pipeline_name=cls.__name__,
                metadata=MappingProxyType({"cyclic_subpipeline": True}),
            )

        # Fresh builds must not inherit a stale cyclic-nesting error flag.
        cls._graph_build_error = None
        _building_graphs.add(cls)
        try:
            graph = _build_logical_graph(cls)
            if cls._graph_build_error:
                graph = LogicalGraph(
                    pipeline_id=pipeline_id(cls),
                    pipeline_name=cls.__name__,
                    metadata=MappingProxyType({"cyclic_subpipeline": True}),
                )
            cls._cached_graph = graph
            return graph
        finally:
            _building_graphs.discard(cls)

    @classmethod
    def inspect(cls) -> LogicalGraph:
        """Return the read-only logical graph for this pipeline.

        Returns:
            The inspected :class:`~etlantic.model.LogicalGraph` (same as
            :meth:`build_graph` via the inspection helper).
        """
        from etlantic.inspection import inspect_pipeline

        return inspect_pipeline(cls)

    @classmethod
    def validate(
        cls, *, profile: str | Any = None, policy: str | Any = None, context: Any = None
    ) -> Any:
        """Validate the complete graph without executing transformation code.

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            policy: Validation policy name or object.
            context: Optional planning context with registries and capabilities.

        Returns:
            A ``ValidationReport`` containing phase results and diagnostics.
            Validation failures are returned in the report; call
            ``report.raise_for_errors()`` to raise ``PipelineValidationError``.

        Raises:
            ValueError: When ``profile`` is an unknown bare name (PMCFG100).
            FileNotFoundError: When ``profile`` is a missing ``.json`` path.

        Examples:
            >>> report = CustomerPipeline.validate(profile="development")
            >>> report.raise_for_errors()
        """
        from etlantic.validation import validate_pipeline

        return validate_pipeline(cls, context=context, profile=profile, policy=policy)

    @classmethod
    def plan(
        cls,
        profile: str | Any = None,
        *,
        context: Any = None,
        selection: dict[str, Any] | None = None,
    ) -> Any:
        """Resolve an immutable, secret-free execution plan.

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            context: Optional planning context with bindings and plugins.
            selection: Optional partial-run selection mapping.

        Returns:
            A deterministic ``PipelinePlan``. Planning does not execute user
            transformation code or resolve secret values.

        Raises:
            PipelineValidationError: When validation reports errors.
            ValueError: When ``profile`` is an unknown bare name (PMCFG100).
            FileNotFoundError: When ``profile`` is a missing ``.json`` path.
        """
        from etlantic.plan.planner import plan_pipeline

        return plan_pipeline(cls, context=context, profile=profile, selection=selection)

    @classmethod
    def explain_plan(
        cls,
        profile: str | Any = None,
        *,
        context: Any = None,
        selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a structured explanation of the planned pipeline.

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            context: Optional planning context with bindings and plugins.
            selection: Optional partial-run selection mapping.

        Returns:
            A JSON-serializable explanation dict (regions, bindings,
            interchange boundaries, fingerprints). Does not execute user code.

        Raises:
            PipelineValidationError: When planning validation fails.
            ValueError: When ``profile`` is an unknown bare name (PMCFG100).
            FileNotFoundError: When ``profile`` is a missing ``.json`` path.

        Examples:
            >>> explanation = CustomerPipeline.explain_plan(profile="development")
            >>> "fingerprint" in explanation or "plan" in explanation
            True
        """
        from etlantic.plan.explain import explain_plan
        from etlantic.plan.planner import plan_pipeline

        plan = plan_pipeline(cls, context=context, profile=profile, selection=selection)
        return explain_plan(plan)

    @classmethod
    def run(
        cls,
        profile: str | Any = "development",
        *,
        request: Any = None,
        runtime: Any = None,
        context: Any = None,
        workspace: str | Any = None,
    ) -> Any:
        """Validate, plan, and execute this pipeline in the current process.

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            request: Optional run selection, intent, and policy request.
            runtime: Application-owned ``PipelineRuntime``. A new runtime is
                created when omitted.
            context: Optional planning context.
            workspace: Optional durable workspace root.

        Returns:
            A structured ``PipelineRunReport``.

        Raises:
            PipelineValidationError: If validation fails before execution.
            PipelineExecutionError: If execution fails, or if called from an
                already-running event loop (use :meth:`arun` instead).
            ETLanticError: If plugin trust checks fail before planning.
            ValueError: When ``profile`` is an unknown bare name (PMCFG100).
            FileNotFoundError: When ``profile`` is a missing ``.json`` path.

        Storage writes and plugin calls follow the resolved plan. Process-local
        memory and report stores do not survive a new CLI or Python process.
        """
        from etlantic.runtime.execute import run_pipeline

        return run_pipeline(
            cls,
            profile=profile,
            request=request,
            runtime=runtime,
            context=context,
            workspace=workspace,
        )

    @classmethod
    async def arun(
        cls,
        profile: str | Any = "development",
        *,
        request: Any = None,
        runtime: Any = None,
        context: Any = None,
        workspace: str | Any = None,
    ) -> Any:
        """Validate, plan, and execute this pipeline locally (async).

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            request: Optional run selection, intent, and policy request.
            runtime: Application-owned ``PipelineRuntime``.
            context: Optional planning context.
            workspace: Optional durable workspace root.

        Returns:
            A structured ``PipelineRunReport``.

        Raises:
            PipelineValidationError: If validation fails before execution.
            PipelineExecutionError: If execution cannot produce a run report.
            ETLanticError: If plugin trust checks fail before planning.
            ValueError: When ``profile`` is an unknown bare name (PMCFG100).
            FileNotFoundError: When ``profile`` is a missing ``.json`` path.

        Examples:
            >>> import anyio
            >>> report = anyio.run(CustomerPipeline.arun, "development")
        """
        from etlantic.runtime.execute import arun_pipeline

        return await arun_pipeline(
            cls,
            profile=profile,
            request=request,
            runtime=runtime,
            context=context,
            workspace=workspace,
        )

    @classmethod
    def debug(
        cls,
        profile: str | Any = "development",
        *,
        runtime: Any = None,
        context: Any = None,
    ) -> Any:
        """Open a stateful local debug session.

        Args:
            profile: Built-in profile name, JSON path, or explicit ``Profile``.
            runtime: Application-owned ``PipelineRuntime`` (created if omitted).
            context: Optional planning context.

        Returns:
            A ``DebugSession`` for stepwise ``run_until`` / ``run_one`` /
            ``rerun`` local execution.
        """
        from etlantic.lifecycle.runtime import PipelineRuntime
        from etlantic.runtime.execute import DebugSession

        return DebugSession(
            pipeline_cls=cls,
            profile=profile,
            runtime=runtime or PipelineRuntime(),
            context=context,
        )

    @classmethod
    def to_mermaid(cls) -> str:
        """Generate a Mermaid flowchart from the logical graph.

        Returns:
            Mermaid flowchart source for the pipeline's logical graph.
        """
        from etlantic.mermaid import graph_to_mermaid

        return graph_to_mermaid(cls.build_graph())

    @classmethod
    def to_dpcs(cls) -> dict[str, Any]:
        """Generate a DPCS document dict for this pipeline.

        Returns:
            A DPCS document mapping suitable for interchange/serialization.

        Raises:
            ModelDefinitionError: When ``cls`` is not a ``Pipeline`` subclass.
            DpcsError: When the pipeline cannot be encoded as valid DPCS.
        """
        from etlantic.interchange.dpcs import pipeline_to_dpcs

        return pipeline_to_dpcs(cls)

    @classmethod
    def from_dpcs(
        cls,
        source: str | Any,
        *,
        registry: dict[str, Any] | None = None,
        root: str | Any = None,
        class_name: str | None = None,
    ) -> type[Pipeline]:
        """Load a Pipeline subclass from a DPCS artifact.

        Args:
            source: DPCS YAML/JSON path or already-parsed document dict.
            registry: Optional type registry for resolving ODCS/DTCS refs.
            root: Optional filesystem root for relative artifact loads.
            class_name: Optional generated class name override.

        Returns:
            A dynamically constructed ``Pipeline`` subclass.

        Raises:
            DpcsError: When the document is invalid or cannot be materialized.
            UnsafeLoadError: When a path load violates safe I/O policy.
        """
        from etlantic.interchange.dpcs import pipeline_from_dpcs

        return pipeline_from_dpcs(
            source,
            registry=registry,
            root=root,
            class_name=class_name,
        )

    @classmethod
    def generate_contracts(cls) -> Any:
        """Discover and build an in-memory contract bundle.

        Returns:
            A ``ContractBundle`` with ODCS/DTCS/DPCS documents in memory.

        Raises:
            BundleError: When ``cls`` is invalid or validation fails.
        """
        from etlantic.interchange.bundle import generate_contracts

        return generate_contracts(cls)

    @classmethod
    def write_contracts(cls, directory: str | Any) -> Any:
        """Generate and write ODCS/DTCS/DPCS artifacts under ``directory``.

        Args:
            directory: Output directory for interchange artifacts.

        Returns:
            The written ``ContractBundle`` (including on-disk paths).

        Raises:
            BundleError: When generation or write fails.
        """
        from etlantic.interchange.bundle import write_contracts

        return write_contracts(cls, directory)

    @classmethod
    def subpipeline(cls, **bindings: Any) -> SubpipelineInstance:
        """Embed this pipeline as a reusable subpipeline in a parent.

        Args:
            **bindings: Parent-side input bindings for the child pipeline.

        Returns:
            A :class:`SubpipelineInstance` for declaration in a parent class body.
        """
        return SubpipelineInstance(pipeline_cls=cls, bindings=dict(bindings))


def _step_quality_metadata(transform: type[Any]) -> MappingProxyType:
    """Copy embedded quality expression onto node metadata for planning."""
    from etlantic.quality.gate import (
        QUALITY_METADATA_KEY,
        quality_expression_from_transform,
    )

    expr = quality_expression_from_transform(transform)
    if expr is None:
        return MappingProxyType({})
    return MappingProxyType({QUALITY_METADATA_KEY: expr})


def _annotation_contract(cls: type[Any], name: str) -> type[Any] | None:
    """Extract a contract type from an Extract[T] / Load[T] class annotation."""
    annotations = _class_annotations(cls)
    annotation = annotations.get(name)
    if annotation is None:
        return None
    if isinstance(annotation, _TypedFactory) and is_data_contract_type(
        annotation.contract_type
    ):
        return annotation.contract_type
    contract = getattr(annotation, "contract_type", None)
    if contract is not None and is_data_contract_type(contract):
        return contract
    args = getattr(annotation, "__args__", None)
    if args and is_data_contract_type(args[0]):
        return args[0]
    return None


def _collect_pipeline_members(cls: type[Pipeline]) -> dict[str, Any]:
    """Collect Extract/Step/Load/Subpipeline members across the class MRO."""
    member_types = (Extract, Load, Step, SubpipelineInstance)
    # Bases first (excluding Pipeline/object), then the concrete class last so
    # subclass attributes override inherited ones by name.
    bases = [
        base
        for base in reversed(cls.__mro__)
        if base is not object and base is not Pipeline and issubclass(base, Pipeline)
    ]

    ordered_names: list[str] = []
    raw_values: dict[str, Any] = {}
    for base in bases:
        order = list(getattr(base, "__member_order__", []))
        names = order or [
            k
            for k, v in base.__dict__.items()
            if not k.startswith("_") and isinstance(v, member_types)
        ]
        for name in names:
            if name not in base.__dict__:
                continue
            value = base.__dict__[name]
            if not isinstance(value, member_types):
                continue
            if name not in raw_values:
                ordered_names.append(name)
            else:
                # Keep declaration order from first appearance; value updates.
                pass
            raw_values[name] = value
        for name, value in base.__dict__.items():
            if (
                name not in raw_values
                and not name.startswith("_")
                and isinstance(value, member_types)
            ):
                ordered_names.append(name)
                raw_values[name] = value
            elif name in base.__dict__ and isinstance(value, member_types):
                raw_values[name] = value

    pid = pipeline_id(cls)
    members: dict[str, Any] = {}
    for name in ordered_names:
        value = raw_values[name]
        owner = _member_owner(cls, name)
        if isinstance(value, Extract) and not isinstance(value, Load):
            contract = value.contract_type or _annotation_contract(owner or cls, name)
            members[name] = type(value)(
                asset=value.asset,
                contract_type=contract,
                name=name,
                pipeline_id=pid,
                producer_key=value.producer_key,
            )
        elif isinstance(value, Load):
            contract = value.contract_type or _annotation_contract(owner or cls, name)
            members[name] = type(value)(
                input=value.input,
                asset=value.asset,
                contract_type=contract,
                name=name,
                pipeline_id=pid,
            )
        elif isinstance(value, (Step, SubpipelineInstance)):
            members[name] = value.bind_name(name, pipeline_id=pid)

    cls.__member_order__ = list(members.keys())
    return members


def _member_owner(cls: type[Pipeline], name: str) -> type[Any] | None:
    """Return the class in the MRO that defines ``name``."""
    for base in cls.__mro__:
        if name in getattr(base, "__dict__", {}):
            return base
    return None


def _build_logical_graph(cls: type[Pipeline]) -> LogicalGraph:
    """Construct a deterministic LogicalGraph from a Pipeline class."""
    members = cls.__pipeline_members__
    pid = pipeline_id(cls)
    nodes: list[Node] = []
    edges: list[Edge] = []

    # First pass: create nodes
    for name, member in members.items():
        nid = node_id(pid, name)
        if isinstance(member, Extract) and not isinstance(member, Load):
            ctype = member.contract_type
            cid = contract_id(ctype) if ctype is not None else None
            nodes.append(
                Node(
                    name=name,
                    kind=NodeKind.SOURCE,
                    identity=nid,
                    contract_type=ctype,
                    contract_id=cid,
                    binding=member.asset,
                    outputs=(
                        PortSpec(
                            name="result",
                            direction="output",
                            contract_type=ctype,
                            contract_id=cid,
                        ),
                    ),
                )
            )
        elif isinstance(member, Step):
            transform = member.transformation
            inputs = tuple(
                PortSpec(
                    name=p.name,
                    direction="input",
                    contract_type=p.contract_type,
                    contract_id=contract_id(p.contract_type)
                    if p.contract_type is not None
                    else None,
                )
                for p in transform.inputs()
            )
            outputs = tuple(
                PortSpec(
                    name=p.name,
                    direction="output",
                    contract_type=p.contract_type,
                    contract_id=contract_id(p.contract_type)
                    if p.contract_type is not None
                    else None,
                    role=getattr(p, "role", "valid"),
                )
                for p in transform.outputs()
            )
            params = tuple(
                ParameterSpec(
                    name=p.name,
                    value_type=p.contract_type,
                    default=p.default,
                    has_default=p.has_default,
                    value=member.parameters.get(p.name, ...),
                    has_value=p.name in member.parameters,
                )
                for p in transform.parameters()
            )
            nodes.append(
                Node(
                    name=name,
                    kind=NodeKind.STEP,
                    identity=nid,
                    transformation_id=transform.identity(),
                    transformation_name=transform.__name__,
                    inputs=inputs,
                    outputs=outputs,
                    parameters=params,
                    metadata=_step_quality_metadata(transform),
                )
            )
        elif isinstance(member, Load):
            ctype = member.contract_type
            cid = contract_id(ctype) if ctype is not None else None
            nodes.append(
                Node(
                    name=name,
                    kind=NodeKind.SINK,
                    identity=nid,
                    contract_type=ctype,
                    contract_id=cid,
                    binding=member.asset,
                    inputs=(
                        PortSpec(
                            name="input",
                            direction="input",
                            contract_type=ctype,
                            contract_id=cid,
                        ),
                    ),
                )
            )
        elif isinstance(member, SubpipelineInstance):
            nested = member.pipeline_cls.build_graph()
            # Public inputs = child sources; public outputs = child sinks
            inputs = tuple(
                PortSpec(
                    name=n.name,
                    direction="input",
                    contract_type=n.contract_type,
                    contract_id=n.contract_id,
                )
                for n in nested.nodes
                if n.kind is NodeKind.SOURCE
            )
            outputs = tuple(
                PortSpec(
                    name=n.name,
                    direction="output",
                    contract_type=n.contract_type,
                    contract_id=n.contract_id,
                )
                for n in nested.nodes
                if n.kind is NodeKind.SINK
            )
            nodes.append(
                Node(
                    name=name,
                    kind=NodeKind.SUBPIPELINE,
                    identity=nid,
                    nested_pipeline_id=nested.pipeline_id,
                    nested_graph=nested,
                    inputs=inputs,
                    outputs=outputs,
                )
            )

    node_by_name = {n.name: n for n in nodes}

    # Second pass: edges from step bindings and sinks
    for name, member in members.items():
        if isinstance(member, Step):
            for port_name, raw in member.bindings.items():
                producer = _resolve_binding_ref(
                    raw, members=members, pipeline_cls=cls, port_hint=port_name
                )
                if producer is None:
                    continue
                consumer_port = next(
                    (p for p in node_by_name[name].inputs if p.name == port_name),
                    None,
                )
                edges.append(
                    Edge(
                        producer_node=producer.node_name,
                        producer_port=producer.port_name,
                        consumer_node=name,
                        consumer_port=port_name,
                        producer_contract_id=contract_id(producer.contract_type)
                        if producer.contract_type is not None
                        else None,
                        consumer_contract_id=consumer_port.contract_id
                        if consumer_port
                        else None,
                    )
                )
        elif isinstance(member, Load):
            producer = _resolve_binding_ref(
                member.input, members=members, pipeline_cls=cls, port_hint="input"
            )
            if producer is not None:
                edges.append(
                    Edge(
                        producer_node=producer.node_name,
                        producer_port=producer.port_name,
                        consumer_node=name,
                        consumer_port="input",
                        producer_contract_id=contract_id(producer.contract_type)
                        if producer.contract_type is not None
                        else None,
                        consumer_contract_id=node_by_name[name].contract_id,
                    )
                )
        elif isinstance(member, SubpipelineInstance):
            public_inputs = {p.name for p in node_by_name[name].inputs}
            for port_name, raw in member.bindings.items():
                if port_name not in public_inputs:
                    # Unknown kwargs must not create phantom edges.
                    continue
                producer = _resolve_binding_ref(
                    raw, members=members, pipeline_cls=cls, port_hint=port_name
                )
                if producer is None:
                    continue
                edges.append(
                    Edge(
                        producer_node=producer.node_name,
                        producer_port=producer.port_name,
                        consumer_node=name,
                        consumer_port=port_name,
                        producer_contract_id=contract_id(producer.contract_type)
                        if producer.contract_type is not None
                        else None,
                        consumer_contract_id=next(
                            (
                                p.contract_id
                                for p in node_by_name[name].inputs
                                if p.name == port_name
                            ),
                            None,
                        ),
                    )
                )

    return LogicalGraph(
        pipeline_id=pid,
        pipeline_name=cls.__name__,
        nodes=tuple(nodes),
        edges=tuple(edges),
    )


def _resolve_binding_ref(
    value: Any,
    *,
    members: dict[str, Any],
    pipeline_cls: type[Pipeline],
    port_hint: str,
) -> OutputRef[Any] | None:
    """Resolve a step/sink/subpipeline binding to a concrete OutputRef.

    Fail closed: ambiguous or unmatched references return ``None``.
    """
    pid = pipeline_id(pipeline_cls)

    if isinstance(value, OutputRef) and value.node_name:
        return value if value.pipeline_id else value.bind_pipeline(pid)

    if isinstance(value, OutputRef) and value.producer_key:
        for member in members.values():
            if (
                isinstance(member, Step)
                and member.producer_key == value.producer_key
                and value.port_name in member.output_refs
            ):
                return member.output_refs[value.port_name]
            if (
                isinstance(member, Extract)
                and not isinstance(member, Load)
                and member.producer_key == value.producer_key
            ):
                return member.as_output_ref()
            if (
                isinstance(member, SubpipelineInstance)
                and member.producer_key == value.producer_key
            ):
                if value.port_name in member._outputs:
                    return member._outputs[value.port_name]
                for node in member.pipeline_cls.build_graph().nodes:
                    if (
                        node.kind is NodeKind.SINK
                        and node.name == value.port_name
                        and member.name
                    ):
                        return OutputRef(
                            node_name=member.name,
                            port_name=node.name,
                            contract_type=node.contract_type,
                            pipeline_id=member.pipeline_id,
                            node_kind="subpipeline",
                            producer_key=member.producer_key,
                        )
        # Stale producer_key must not fall through to fuzzy matching.
        return None

    if isinstance(value, Extract) and not isinstance(value, Load):
        if value.name:
            for member in members.values():
                if (
                    isinstance(member, Extract)
                    and not isinstance(member, Load)
                    and member.name == value.name
                ):
                    return member.as_output_ref()
        matches = [
            member.as_output_ref()
            for member in members.values()
            if isinstance(member, Extract)
            and not isinstance(member, Load)
            and member.asset == value.asset
            and (
                value.contract_type is None
                or member.contract_type is value.contract_type
            )
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    if isinstance(value, Step):
        for member in members.values():
            if isinstance(member, Step) and member.producer_key == value.producer_key:
                return member.as_output_ref()
        return None

    if isinstance(value, OutputRef):
        matches: list[OutputRef[Any]] = []
        for member in members.values():
            if isinstance(member, Step) and value.port_name in member.output_refs:
                candidate = member.output_refs[value.port_name]
                if (
                    value.contract_type is None
                    or candidate.contract_type is value.contract_type
                ):
                    matches.append(candidate)
            elif (
                isinstance(member, Extract)
                and not isinstance(member, Load)
                and value.port_name in {"result", "output"}
            ):
                if (
                    value.contract_type is None
                    or member.contract_type is value.contract_type
                ):
                    matches.append(member.as_output_ref())
            elif (
                isinstance(member, SubpipelineInstance)
                and value.port_name in member._outputs
            ):
                matches.append(member._outputs[value.port_name])
        if len(matches) == 1:
            return matches[0]
        return None

    return as_output_ref(value)
