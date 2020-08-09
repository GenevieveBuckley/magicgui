from __future__ import annotations

from typing import Union, Sequence, overload, MutableSequence, Callable

from magicgui.application import use_app
from magicgui.signature import MagicSignature, magic_signature, MagicParameter
from magicgui.base import BaseContainer
from inspect import Signature
from magicgui.widget import Widget


class Container(MutableSequence[Widget]):
    def __init__(
        self,
        *,
        orientation="horizontal",
        widgets: Sequence[Widget] = [],
        app=None,
        return_annotation=Signature.empty,
    ):
        _app = use_app(app)
        assert _app.native

        self._base: BaseContainer = _app.get_obj("Container")(orientation)
        self._return_annotation = return_annotation
        for w in widgets:
            self.append(w)

    def __getattr__(self, name: str):
        for widget in self:
            if name == widget.name:
                return widget
        raise AttributeError(f"'Container' object has no attribute {name!r}")

    def __delitem__(self, key: Union[int, slice]):
        if isinstance(key, slice):
            for idx in range(*key.indices(len(self))):
                self._base._mg_remove_index(idx)
        else:
            self._base._mg_remove_index(key)

    @overload
    def __getitem__(self, key: int) -> Widget:
        ...

    @overload
    def __getitem__(self, key: slice) -> MutableSequence[Widget]:
        ...

    def __getitem__(self, key):
        if isinstance(key, slice):
            out = []
            for idx in range(*key.indices(len(self))):
                item = self._base._mg_get_index(idx)
                if item:
                    out.append(item)
            return out

        item = self._base._mg_get_index(key)
        if not item:
            raise IndexError("Container index out of range")
        return item

    def __len__(self) -> int:
        return self._base._mg_count()

    def __setitem__(self, key, value):
        raise NotImplementedError("magicgui.Container does not support item setting.")

    def insert(self, key: int, value: Widget):
        self._base._mg_insert_widget(key, value)

    @property
    def native(self):
        return self._base._mg_get_native_layout()

    def __repr__(self) -> str:
        return f"<magicgui.Container at {hex(id(self))} with {len(self)} widgets>"

    @classmethod
    def from_signature(cls, sig: Signature, **kwargs) -> Container:
        return MagicSignature.from_signature(sig).to_container(**kwargs)

    @classmethod
    def from_callable(cls, obj: Callable, **kwargs) -> Container:
        return magic_signature(obj).to_container(**kwargs)

    def to_signature(self) -> MagicSignature:
        params = [
            MagicParameter(
                name=w.name,
                kind=w._kind,
                default=w.value,
                annotation=w.annotation,
                options=w._options,
            )
            for w in self
            if w.name and not w.gui_only
        ]
        return MagicSignature(params, return_annotation=self._return_annotation)

    def show(self):
        self._base._mg_show_widget()

    def hide(self):
        self._base._mg_hide_widget()
