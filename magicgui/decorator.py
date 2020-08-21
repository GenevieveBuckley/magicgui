from __future__ import annotations

import inspect
from contextlib import contextmanager
from typing import Any, Callable, List, Optional, Sequence, TypeVar, Union, overload

from magicgui.application import Application, AppRef, use_app
from magicgui.widgets import Container, LineEdit, PushButton

F = TypeVar("F", bound=Callable[..., Any])


@overload
def magicgui(function: F) -> FunctionGui:
    ...


@overload
def magicgui(function=None, **k) -> Callable[[F], FunctionGui]:
    ...


def magicgui(
    function: Optional[F] = None,
    *,
    orientation: str = "horizontal",
    labels: bool = True,
    call_button: Union[bool, str] = False,
    auto_call: bool = False,
    result_widget: bool = False,
    parent: Any = None,
    ignore: Optional[Sequence[str]] = None,
    app: AppRef = None,
    **param_options: dict,
):
    """Create a FunctionGui class for ``function`` and add it as an attribute ``Gui``.

    Parameters
    ----------
    function : Callable, optional
        The function to decorate.  Optional to allow bare decorator with optional
        arguments. by default None
    orientation : str, optional
        The type of layout to use. Must be one of {'horizontal', 'vertical',
        'form', 'grid'}, by default "horizontal"
    labels : bool
        Whether labels are shown in the widget. by default True
    call_button : bool or str, optional
        If True, create an additional button that calls the original function when
        clicked.  If a ``str``, set the button text. by default False
    auto_call : bool, optional
        If True, changing any parameter in either the GUI or the widget attributes
        will call the original function with the current settings. by default False
    parent : api.WidgetType, optional
        An optional parent widget (note: this can be useful for inheriting styles),
        by default None
    ignore : list of str, optional
        Parameters in the function signature that should be ignored when creating
        the widget, by default None

    **param_options : dict of dict
        Any additional keyword arguments will be used as parameter-specific options.
        Keywords MUST match the name of one of the arguments in the function
        signature, and the value MUST be a dict.

    Returns
    -------
    Callable
        The original function is returned with a new attribute ``Gui``.  Gui is a
        subclass of MagicGui that, when instantiated, will create a widget representing
        the signature of the original function.  Furthermore, *calling* that widget will
        call the original function using the state of the Gui arguments.

    Examples
    --------
    >>> @magicgui
    ... def my_function(a: int = 1, b: str = 'hello'):
    ...     pass
    ...
    ... gui = my_function.Gui(show=True)
    """

    def inner_func(func: Callable) -> FunctionGui:
        return FunctionGui(
            function=func,
            call_button=call_button,
            orientation=orientation,
            param_options=param_options,
            auto_call=auto_call,
            result_widget=result_widget,
            app=app,
        )

    if function is None:
        return inner_func
    else:
        return inner_func(function)


class FunctionGui:
    """Wrapper for a container of widgets representing a callable object."""

    widgets: Container
    __magicgui_app__: Application

    def __new__(
        cls,
        function: Callable,
        call_button: Union[bool, str] = True,
        orientation: str = "horizontal",
        app: AppRef = None,
        show: bool = False,
        auto_call: bool = False,
        result_widget: bool = False,
        param_options: Optional[dict] = None,
    ) -> FunctionGui:
        """Create a new FunctionGui instance."""
        if isinstance(function, FunctionGui):
            # don't redecorate already-wrapped function
            return function

        self = super().__new__(cls)
        self.__magicgui_app__ = use_app(app)
        # this must be the first thing set
        self.widgets = Container.from_callable(
            function, orientation=orientation, gui_options=param_options
        )

        self._function = function

        if call_button:
            text = call_button if isinstance(call_button, str) else "Run"
            self._call_button = PushButton(gui_only=True, text=text, name="call_button")
            if not auto_call:  # (otherwise it already get's called)
                # using lambda because the clicked signal returns a value
                self._call_button.changed.connect(lambda x: self.__call__())
            self.widgets.append(self._call_button)

        self._result_widget = None
        if result_widget:
            self._result_widget = LineEdit(gui_only=True, name="result")
            self._result_widget.enabled = False
            self.widgets.append(self._result_widget)

        if auto_call:
            self.widgets.changed.connect(lambda *x: self.__call__())

        if show:
            self.show()
        return self

    def __dir__(self) -> List[str]:
        d = list(super().__dir__())
        d.extend([w.name for w in self.widgets if not w.gui_only])
        return d

    def __getattr__(self, name):
        """If ``name`` is the name of one of the parameters, get the widget."""
        if name != "widgets" and hasattr(self, "widgets"):
            try:
                return getattr(self.widgets, name)
            except AttributeError:
                pass
        raise AttributeError(f"'FunctionGui' object has no attribute {name!r}")

    def __setattr__(self, name, value):
        """If ``name`` is the name of one of the parameters, set the current value."""
        if name != "widgets" and hasattr(self, "widgets"):
            widget = getattr(self.widgets, name, None)
            if widget:
                widget.value = value
                return
        super().__setattr__(name, value)

    def __call__(self, *args: Any, **kwargs: Any):
        """Call the original function with the current parameter values from the Gui.

        It is also possible to override the current parameter values from the GUI by
        providing args/kwargs to the function call.  Only those provided will override
        the ones from the gui.  A `called` signal will also be emitted with the results.

        Returns
        -------
        result : Any
            whatever the return value of the original function would have been.

        Examples
        --------
        gui = FunctionGui(func, show=True)
        # ... change parameters in the gui ... or by setting:  gui.param = something
        """
        sig = self.widgets.to_signature()
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        value = self._function(*bound.args, **bound.kwargs)
        print("returned,", value)
        if self._result_widget is not None:
            self._result_widget.value = value

        # self.called.emit(value)
        # return_type = self.widgets._return_annotation
        # if return_type:
        #     for callback in _type2callback(return_type):
        #         callback(self, value, return_type)
        return value

    def __repr__(self) -> str:
        """Return string representation of instance."""
        fname = f"{self._function.__module__}.{self._function.__name__}"
        return f"<FunctionGui {fname}{self.widgets.to_signature()}>"

    def show(self, run=False):
        """Show the widget."""
        self.widgets.show()
        if run:
            self.__magicgui_app__.run()

    @contextmanager
    def shown(self):
        """Context manager to show the widget."""
        try:
            self.show()
            yield self.__magicgui_app__.__enter__()
        finally:
            self.__magicgui_app__.__exit__()

    def hide(self):
        """Hide the widget."""
        self.widgets.hide()

    @property
    def __signature__(self) -> inspect.Signature:
        """Return signature object, for compatibility with inspect.signature()."""
        return self.widgets.to_signature()
