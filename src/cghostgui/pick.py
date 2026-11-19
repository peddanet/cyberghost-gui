"""Searchable drop-down list."""
from typing import Any, Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402  pylint: disable=wrong-import-position


class Pick:
    """A drop-down holding pairs of label and value.

    Attributes:
        widget: The GTK widget.
        values: Values in display order.
        labels: Labels in display order.
    """

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        """Create the list.

        Args:
            on_change: Called when the user selects another entry.
        """
        self.values: list[Any] = []
        self.labels: list[str] = []
        self._on_change = on_change
        self._mute = False
        self._model = Gtk.StringList()
        self.widget = Gtk.DropDown(model=self._model, hexpand=True, enable_search=True)
        self.widget.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.widget.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        self.widget.connect("notify::selected", self._changed)

    def _changed(self, *_: Any) -> None:
        """Forward a selection made by the user."""
        if not self._mute and self._on_change:
            self._on_change()

    def fill(self, items: list[tuple[str, Any]], keep: Any = None) -> None:
        """Replace the entries without reporting a change.

        Args:
            items: Pairs of label and value.
            keep: Value to select if present.
        """
        self._mute = True
        self.labels = [label for label, _ in items]
        self.values = [value for _, value in items]
        self._model.splice(0, self._model.get_n_items(), self.labels)
        self.widget.set_selected(self.values.index(keep) if keep in self.values else 0)
        self._mute = False

    def select(self, value: Any) -> None:
        """Select an entry as the user would.

        Args:
            value: Value of the entry.
        """
        self.widget.set_selected(self.values.index(value))

    @property
    def value(self) -> Any:
        """Return the selected value.

        Returns:
            The value, or None for an empty list.
        """
        index = self.widget.get_selected()
        return self.values[index] if index < len(self.values) else None
