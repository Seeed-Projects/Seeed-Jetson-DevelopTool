from __future__ import annotations

from dataclasses import dataclass
import weakref
from typing import Any, Callable

from seeed_jetson_develop.gui.i18n import get_language, t


@dataclass
class _WidgetBinding:
    kind: str
    ref: weakref.ReferenceType
    key: str
    fmt: dict[str, Any]


class I18nBinding:
    """Lightweight i18n binder for Qt widgets/callbacks."""

    def __init__(self):
        self._widget_bindings: list[_WidgetBinding] = []
        self._callables: list[Any] = []

    def extend(self, other: "I18nBinding") -> "I18nBinding":
        self._widget_bindings.extend(other._widget_bindings)
        self._callables.extend(other._callables)
        return self

    def bind_text(self, widget: Any, key: str, **fmt) -> "I18nBinding":
        self._widget_bindings.append(_WidgetBinding("text", weakref.ref(widget), key, fmt))
        return self

    def bind_placeholder(self, widget: Any, key: str, **fmt) -> "I18nBinding":
        self._widget_bindings.append(_WidgetBinding("placeholder", weakref.ref(widget), key, fmt))
        return self

    def bind_tooltip(self, widget: Any, key: str, **fmt) -> "I18nBinding":
        self._widget_bindings.append(_WidgetBinding("tooltip", weakref.ref(widget), key, fmt))
        return self

    def bind_callable(self, fn: Callable[[], None]) -> "I18nBinding":
        if getattr(fn, "__self__", None) is not None:
            # Bound method: weak reference to avoid keeping owner alive.
            self._callables.append(weakref.WeakMethod(fn))
        else:
            # Plain function/closure: keep strong reference to preserve callback.
            self._callables.append(fn)
        return self

    def apply(self, lang: str | None = None):
        language = lang or get_language()

        alive_bindings: list[_WidgetBinding] = []
        for b in self._widget_bindings:
            w = b.ref()
            if w is None:
                continue
            kwargs = self._resolve_fmt(b.fmt)
            text = t(b.key, lang=language, **kwargs)
            try:
                if b.kind == "text" and hasattr(w, "setText"):
                    w.setText(text)
                elif b.kind == "placeholder" and hasattr(w, "setPlaceholderText"):
                    w.setPlaceholderText(text)
                elif b.kind == "tooltip" and hasattr(w, "setToolTip"):
                    w.setToolTip(text)
            except Exception:
                pass
            alive_bindings.append(b)
        self._widget_bindings = alive_bindings

        alive_calls: list[Any] = []
        for ref in self._callables:
            if isinstance(ref, weakref.ReferenceType):
                fn = ref()
            else:
                fn = ref
            if fn is None:
                continue
            try:
                fn()
            except Exception:
                pass
            alive_calls.append(ref)
        self._callables = alive_calls

    @staticmethod
    def _resolve_fmt(fmt: dict[str, Any]) -> dict[str, Any]:
        if not fmt:
            return {}
        out: dict[str, Any] = {}
        for k, v in fmt.items():
            if callable(v):
                try:
                    out[k] = v()
                except Exception:
                    out[k] = v
            else:
                out[k] = v
        return out
