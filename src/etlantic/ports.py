# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Port annotation markers: Input, Output, and Parameter."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Input(Generic[T]):
    """Declares a typed input port consumed under contract ``T``.

    Use on :class:`~etlantic.transformation.Transformation` subclasses::

        class Normalize(Transformation):
            rows: Input[RawRow]
            result: Output[CuratedRow]

    Args:
        contract_type: :class:`~etlantic.contracts.Data` subclass (via subscript
            ``Input[MyData]`` or constructor argument).
    """

    __slots__ = ("contract_type",)

    def __init__(self, contract_type: type[T] | None = None) -> None:
        self.contract_type = contract_type

    def __class_getitem__(cls, item: type[T] | Any) -> Input[T]:
        return cls(contract_type=item)

    def __repr__(self) -> str:
        name = getattr(self.contract_type, "__name__", self.contract_type)
        return f"Input[{name}]"


class Output(Generic[T]):
    """Declares data produced under contract ``T``.

    ``role`` distinguishes primary valid outputs from invalid/side channels:
    ``"valid"`` (default), ``"invalid"``, or ``"side"``.
    """

    __slots__ = ("contract_type", "role")

    def __init__(
        self,
        contract_type: type[T] | None = None,
        *,
        role: str = "valid",
    ) -> None:
        self.contract_type = contract_type
        self.role = role

    def __class_getitem__(cls, item: type[T] | Any) -> Output[T]:
        return cls(contract_type=item)

    def as_invalid(self) -> Output[T]:
        """Return a copy marked as an invalid-output channel."""
        return Output(contract_type=self.contract_type, role="invalid")

    def as_side(self) -> Output[T]:
        """Return a copy marked as a side-output channel."""
        return Output(contract_type=self.contract_type, role="side")

    def __repr__(self) -> str:
        name = getattr(self.contract_type, "__name__", self.contract_type)
        if self.role != "valid":
            return f"Output[{name}, role={self.role!r}]"
        return f"Output[{name}]"


class Parameter(Generic[T]):
    """Declares typed configuration that is not a graph edge.

    Parameters are bound at :meth:`~etlantic.transformation.Transformation.step`
    time and appear in plans separately from input/output ports.

    Example::

        class ThresholdFilter(Transformation):
            rows: Input[Row]
            min_score: Parameter[int]
            result: Output[Row]
    """

    __slots__ = ("contract_type", "default", "has_default")

    def __init__(
        self,
        contract_type: type[T] | None = None,
        *,
        default: Any = ...,
        has_default: bool = False,
    ) -> None:
        self.contract_type = contract_type
        self.default = default
        self.has_default = has_default

    def __class_getitem__(cls, item: type[T] | Any) -> Parameter[T]:
        return cls(contract_type=item)

    def with_default(self, value: Any) -> Parameter[T]:
        """Return a copy of this parameter marker with a default value."""
        return Parameter(
            contract_type=self.contract_type, default=value, has_default=True
        )

    def __repr__(self) -> str:
        name = getattr(self.contract_type, "__name__", self.contract_type)
        return f"Parameter[{name}]"


def unwrap_port_marker(annotation: Any) -> tuple[type[Any] | None, type[Any] | None]:
    """Classify an annotation as Input/Output/Parameter and return (kind, contract).

    Returns ``(None, None)`` when the annotation is not a port marker.
    The first element is the marker class (Input, Output, or Parameter).
    """
    if isinstance(annotation, Input):
        return Input, annotation.contract_type
    if isinstance(annotation, Output):
        return Output, annotation.contract_type
    if isinstance(annotation, Parameter):
        return Parameter, annotation.contract_type

    origin = getattr(annotation, "__origin__", None)
    if origin is Input or origin is Output or origin is Parameter:
        args = getattr(annotation, "__args__", ())
        contract = args[0] if args else None
        return origin, contract

    return None, None
