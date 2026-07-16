"""Transformation contracts, steps, and implementation registration."""

from __future__ import annotations

import inspect
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar

from pipelantic.exceptions import ModelDefinitionError
from pipelantic.identity import implementation_id, transformation_id
from pipelantic.ports import Input, Output, Parameter, unwrap_port_marker
from pipelantic.refs import OutputRef

F = TypeVar("F", bound=Callable[..., Any])

_step_key_counter = itertools.count(1)


def _class_annotations(cls: type[Any]) -> dict[str, Any]:
    """Return evaluated class annotations (supports postponed evaluation)."""
    try:
        return inspect.get_annotations(cls, eval_str=True)
    except Exception:
        return dict(getattr(cls, "__annotations__", {}))


@dataclass(frozen=True, slots=True)
class PortDefinition:
    """Introspected port on a transformation class."""

    name: str
    kind: str  # "input" | "output" | "parameter"
    contract_type: type[Any] | None
    default: Any = ...
    has_default: bool = False


@dataclass(frozen=True, slots=True)
class ImplementationRecord:
    """Registered execution implementation for a transformation."""

    engine: str
    identity: str
    callable: Callable[..., Any]
    is_async: bool
    signature: inspect.Signature


@dataclass
class Step:
    """A concrete use of a transformation inside a pipeline.

    Created via ``Transformation.step(...)``. Attribute access to output port
    names yields :class:`OutputRef` values for downstream wiring.
    """

    transformation: type[Transformation]
    bindings: dict[str, Any]
    parameters: dict[str, Any]
    name: str | None = None
    producer_key: str = field(default_factory=lambda: f"step-{next(_step_key_counter)}")
    _outputs: dict[str, OutputRef[Any]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self._outputs:
            for port in self.transformation.outputs():
                self._outputs[port.name] = OutputRef(
                    node_name="",  # filled when bound into a pipeline
                    port_name=port.name,
                    contract_type=port.contract_type,
                    node_kind="step",
                    producer_key=self.producer_key,
                )

    def bind_name(self, name: str, *, pipeline_id: str | None = None) -> Step:
        """Return a step with its node name and output refs bound."""
        outputs = {
            port_name: OutputRef(
                node_name=name,
                port_name=ref.port_name,
                contract_type=ref.contract_type,
                pipeline_id=pipeline_id,
                node_kind="step",
                producer_key=self.producer_key,
            )
            for port_name, ref in self._outputs.items()
        }
        return Step(
            transformation=self.transformation,
            bindings=dict(self.bindings),
            parameters=dict(self.parameters),
            name=name,
            producer_key=self.producer_key,
            _outputs=outputs,
        )

    def __getattr__(self, item: str) -> OutputRef[Any]:
        if item.startswith("_"):
            raise AttributeError(item)
        if item in self._outputs:
            return self._outputs[item]
        available = ", ".join(sorted(self._outputs)) or "(none)"
        msg = f"Step has no output port {item!r}. Available: {available}"
        raise AttributeError(msg)

    def as_output_ref(self, *, default_port: str = "result") -> OutputRef[Any]:
        """Return the default or named output reference for this step."""
        if default_port in self._outputs:
            return self._outputs[default_port]
        if len(self._outputs) == 1:
            return next(iter(self._outputs.values()))
        msg = (
            f"Step requires an explicit output port; "
            f"available: {', '.join(sorted(self._outputs))}"
        )
        raise AttributeError(msg)

    @property
    def output_refs(self) -> dict[str, OutputRef[Any]]:
        """Return all output references keyed by port name."""
        return dict(self._outputs)


class Transformation:
    """Base class for typed transformation contracts.

    Subclasses declare ``Input``, ``Output``, and ``Parameter`` annotations.
    Implementations are registered separately with :meth:`implementation`.
    """

    __ports__: ClassVar[tuple[PortDefinition, ...]] = ()
    __implementations__: ClassVar[dict[str, ImplementationRecord]] = {}
    _definition_error: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls is Transformation:
            return
        cls.__implementations__ = {}
        try:
            cls.__ports__ = tuple(_collect_ports(cls))
            cls._definition_error = None
        except ModelDefinitionError as exc:
            cls.__ports__ = ()
            cls._definition_error = str(exc)

    @classmethod
    def identity(cls) -> str:
        """Stable transformation identity."""
        return transformation_id(cls)

    @classmethod
    def inputs(cls) -> tuple[PortDefinition, ...]:
        """Return declared input ports in definition order."""
        return tuple(p for p in cls.__ports__ if p.kind == "input")

    @classmethod
    def outputs(cls) -> tuple[PortDefinition, ...]:
        """Return declared output ports in definition order."""
        return tuple(p for p in cls.__ports__ if p.kind == "output")

    @classmethod
    def parameters(cls) -> tuple[PortDefinition, ...]:
        """Return declared parameters in definition order."""
        return tuple(p for p in cls.__ports__ if p.kind == "parameter")

    @classmethod
    def implementations(cls) -> dict[str, ImplementationRecord]:
        """Return registered implementations keyed by engine name."""
        return dict(cls.__implementations__)

    @classmethod
    def validate_definition(cls) -> list[str]:
        """Return definition problems for this transformation class."""
        problems: list[str] = []
        if cls._definition_error:
            problems.append(cls._definition_error)
        if not cls.outputs():
            problems.append(f"{cls.__name__} must declare at least one Output port.")
        return problems

    @classmethod
    def implementation(cls, engine: str) -> Callable[[F], F]:
        """Decorator that registers an execution implementation for ``engine``."""

        def decorator(fn: F) -> F:
            record = ImplementationRecord(
                engine=engine,
                identity=implementation_id(cls.identity(), engine),
                callable=fn,
                is_async=inspect.iscoroutinefunction(fn),
                signature=inspect.signature(fn),
            )
            cls.__implementations__[engine] = record
            return fn

        return decorator

    @classmethod
    def to_dtcs(cls) -> dict[str, Any]:
        """Generate a DTCS document dict for this transformation."""
        from pipelantic.interchange.dtcs import transformation_to_dtcs

        return transformation_to_dtcs(cls)

    @classmethod
    def from_dtcs(
        cls,
        source: str | Any,
        *,
        contracts: dict[str, type[Any]] | None = None,
        root: str | Any = None,
        class_name: str | None = None,
    ) -> type[Transformation]:
        """Load a Transformation subclass from a DTCS artifact."""
        from pipelantic.interchange.dtcs import transformation_from_dtcs

        return transformation_from_dtcs(
            source,
            contracts=contracts,
            root=root,
            class_name=class_name,
        )

    @classmethod
    def step(cls, **kwargs: Any) -> Step:
        """Create a concrete step instance of this transformation."""
        input_names = {p.name for p in cls.inputs()}
        param_defs = {p.name: p for p in cls.parameters()}
        bindings: dict[str, Any] = {}
        parameters: dict[str, Any] = {}

        unknown = set(kwargs) - input_names - set(param_defs)
        if unknown:
            names = ", ".join(sorted(unknown))
            msg = f"Unknown binding(s) for {cls.__name__}: {names}"
            raise ModelDefinitionError(msg)

        for name in input_names:
            if name in kwargs:
                bindings[name] = kwargs[name]

        for name, port in param_defs.items():
            if name in kwargs:
                parameters[name] = kwargs[name]
            elif port.has_default:
                parameters[name] = port.default

        return Step(transformation=cls, bindings=bindings, parameters=parameters)


def _collect_ports(cls: type[Transformation]) -> list[PortDefinition]:
    """Introspect Input/Output/Parameter annotations across the class MRO."""
    ports: list[PortDefinition] = []
    seen: set[str] = set()

    # Base → derived so subclasses can override port definitions by name.
    bases = [
        base
        for base in reversed(cls.__mro__)
        if base is not object
        and base is not Transformation
        and issubclass(base, Transformation)
    ]
    for base in bases:
        annotations = _class_annotations(base)
        for name, annotation in annotations.items():
            if name.startswith("_"):
                continue
            kind_cls, contract = unwrap_port_marker(annotation)
            if kind_cls is None:
                continue

            default = ...
            has_default = False
            if kind_cls is Parameter:
                default, has_default = _parameter_default(base, name, annotation)

            port = PortDefinition(
                name=name,
                kind=(
                    "input"
                    if kind_cls is Input
                    else "output"
                    if kind_cls is Output
                    else "parameter"
                ),
                contract_type=contract,
                default=default,
                has_default=has_default,
            )
            if name in seen:
                # Derived class overrides an inherited port of the same name.
                ports = [p for p in ports if p.name != name]
            else:
                seen.add(name)
            ports.append(port)

    return ports


def _parameter_default(cls: type[Any], name: str, annotation: Any) -> tuple[Any, bool]:
    """Resolve a Parameter default from annotation or class attribute."""
    if isinstance(annotation, Parameter) and annotation.has_default:
        return annotation.default, True
    if name not in cls.__dict__:
        return ..., False
    value = cls.__dict__[name]
    if isinstance(value, Parameter) and value.has_default:
        return value.default, True
    if isinstance(value, Parameter):
        return ..., False
    return value, True
