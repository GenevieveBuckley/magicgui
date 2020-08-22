"""magicgui Widget class that wraps all backend widgets."""
import datetime
import inspect
import pathlib
from collections import abc, defaultdict
from enum import EnumMeta
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
)

from typing_extensions import TypedDict

from magicgui import widgets
from magicgui.protocols import WidgetProtocol

if TYPE_CHECKING:
    from magicgui.decorator import FunctionGui
    from magicgui.widget_wrappers import ChoicesType, Widget


class MissingWidget(RuntimeError):
    """Raised when a backend widget cannot be found."""

    pass


WidgetClass = Union[Type["Widget"], Type[WidgetProtocol]]
WidgetClassRef = Union[str, WidgetClass]


ReturnCallback = Callable[["FunctionGui", Any, Type], None]
_RETURN_CALLBACKS: DefaultDict[type, List[ReturnCallback]] = defaultdict(list)


class WidgetOptions(TypedDict, total=False):
    widget_type: WidgetClassRef
    choices: "ChoicesType"
    gui_only: bool
    visible: bool
    enabled: bool
    text: str
    minimum: float
    maximum: float
    step: float
    orientation: str


TypeMatcher = Callable[
    [Any, Optional[Type]], Optional[Tuple[WidgetClassRef, WidgetOptions]]
]

_TYPE_DEFS: Dict[type, Tuple[WidgetClassRef, WidgetOptions]] = {}
_TYPE_MATCHERS: List[TypeMatcher] = list()


def is_subclass(obj, superclass):
    try:
        return issubclass(obj, superclass)
    except Exception:
        return False


def type_matcher(func: TypeMatcher) -> TypeMatcher:
    """Add function to the set of type matchers."""
    _TYPE_MATCHERS.append(func)
    return func


@type_matcher
def sequence_of_paths(
    value, annotation
) -> Optional[Tuple[WidgetClassRef, WidgetOptions]]:
    """Determine if value/annotation is a Sequence[pathlib.Path]."""

    if annotation:
        orig = get_origin(annotation)
        args = get_args(annotation)
        if not (inspect.isclass(orig) and args):
            return None
        if isinstance(orig, abc.Sequence):
            if is_subclass(args[0], pathlib.Path):
                return widgets.FileEdit, {}
    elif value:
        if isinstance(value, abc.Sequence) and all(
            isinstance(v, pathlib.Path) for v in value
        ):
            return widgets.FileEdit, {}
    return None


@type_matcher
def simple_type(value, annotation) -> Optional[Tuple[WidgetClassRef, WidgetOptions]]:
    """Check simple type mappings."""
    dtype = resolve_type(value, annotation)

    simple = {
        bool: widgets.CheckBox,
        int: widgets.SpinBox,
        float: widgets.FloatSpinBox,
        str: widgets.LineEdit,
        pathlib.Path: widgets.FileEdit,
        datetime.datetime: widgets.DateTimeEdit,
        type(None): widgets.LineEdit,
    }
    if dtype in simple:
        return simple[dtype], {}
    else:
        for key in simple.keys():
            if is_subclass(dtype, key):
                return simple[key], {}
    return None


def resolve_type(value: Any, annotation: Any) -> Type:
    return (get_origin(annotation) or annotation) if annotation else type(value)


def pick_widget_type(
    value: Any = None, annotation: Optional[Type] = None, options: WidgetOptions = {},
) -> Tuple[WidgetClassRef, WidgetOptions]:
    """Pick the appropriate widget type for ``value`` with ``annotation``."""
    if "widget_type" in options:
        widget_type = options.pop("widget_type")
        return widget_type, options

    dtype = resolve_type(value, annotation)

    # look for subclasses
    for registered_type in _TYPE_DEFS:
        if dtype == registered_type or is_subclass(dtype, registered_type):
            return _TYPE_DEFS[registered_type]

    choices = options.get("choices") or (isinstance(dtype, EnumMeta) and dtype)
    if choices:
        return widgets.ComboBox, {"choices": choices}

    for matcher in _TYPE_MATCHERS:
        _widget_type = matcher(value, annotation)
        if _widget_type:
            return _widget_type
    raise ValueError("Could not pick widget.")


def get_widget_class(
    value: Any = None, annotation: Optional[Type] = None, options: dict = {}
) -> Tuple[WidgetClass, WidgetOptions]:
    from magicgui.widget_wrappers import Widget

    _options = cast(WidgetOptions, options)
    widget_type, _options = pick_widget_type(value, annotation, _options)
    print("widget_type", widget_type)
    if isinstance(widget_type, str):
        widget_class: WidgetClass = _import_class(widget_type)
    else:
        widget_class = widget_type

    assert isinstance(widget_class, WidgetProtocol) or is_subclass(widget_class, Widget)
    return widget_class, _options


def _import_class(class_name: str) -> WidgetClass:
    import importlib

    mod_name, name = class_name.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, name)


def validate_return_callback(func):
    try:
        sig = inspect.signature(func)
        # the signature must accept three arguments
        sig.bind(1, 2, 3)  # (gui, result, return_type)
    except TypeError as e:
        raise TypeError(f"object {func!r} is not a valid return callback: {e}")


def register_type(
    type_: type,
    *,
    widget_type: WidgetClassRef = None,
    return_callback: Optional[ReturnCallback] = None,
    **options,
):
    """Register a ``widget_type`` to be used for all parameters with type ``type_``.

    Parameters
    ----------
    type_ : type
        The type for which a widget class or return callback will be provided.
    widget_type : Optional[Type[api.WidgetType]], optional
        A widget class from the current backend that should be used whenever ``type_``
        is used as the type annotation for an argument in a decorated function,
        by default None
    return_callback: callable, optional
        If provided, whenever ``type_`` is declared as the return type of a decorated
        function, ``return_callback(widget, value, return_type)`` will be called
        whenever the decorated function is called... where ``widget`` is the MagicGui
        instance, and ``value`` is the return value of the decorated function.

    OPTIONS

    Raises
    ------
    ValueError
        If both ``widget_type`` and ``choices`` are None
    """
    if not (return_callback or options.get("choices") or widget_type):
        raise ValueError(
            "At least one of `widget_type`, `choices`, or "
            "`return_callback` must be provided."
        )

    if return_callback is not None:
        validate_return_callback(return_callback)
        _RETURN_CALLBACKS[type_].append(return_callback)

    _options = cast(WidgetOptions, options)

    if "choices" in _options:
        _TYPE_DEFS[type_] = (widgets.ComboBox, _options)
        if widget_type is not None:
            import warnings

            warnings.warn(
                "Providing `choices` overrides `widget_type`. Categorical widget will "
                f"be used for type {type_}"
            )
    elif widget_type is not None:
        from magicgui.widget_wrappers import Widget

        if not isinstance(widget_type, (str, Widget, WidgetProtocol)):
            raise TypeError(
                '"widget_type" must be either a string, Widget, or WidgetProtocol'
            )
        _TYPE_DEFS[type_] = (widget_type, _options)

    return None


def _type2callback(type_: type) -> List[ReturnCallback]:
    """Check if return callbacks have been registered for ``type_`` and return if so.

    Parameters
    ----------
    type_ : type
        The type_ to look up.

    Returns
    -------
    list of callable
        Where a return callback accepts two arguments (gui, value) and does something.
    """
    # look for direct hits
    if type_ in _RETURN_CALLBACKS:
        return _RETURN_CALLBACKS[type_]
    # look for subclasses
    for registered_type in _RETURN_CALLBACKS:
        if is_subclass(type_, registered_type):
            return _RETURN_CALLBACKS[registered_type]
    return []
