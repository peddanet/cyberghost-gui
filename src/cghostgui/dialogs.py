"""Small input dialog."""
from typing import Any, Callable, Sequence

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402  pylint: disable=wrong-import-position


def padded(child: Gtk.Widget) -> Gtk.Widget:
    """Surround a widget with free space.

    Args:
        child: Widget.

    Returns:
        Container holding the widget.
    """
    child.set_margin_start(16)
    child.set_margin_end(16)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(Gtk.Box(height_request=16))
    box.append(child)
    box.append(Gtk.Box(height_request=16))
    return box


class InputDialog(Gtk.Window):
    """Asks for one value."""

    def __init__(self, parent: Gtk.Window, title: str, hint: str, on_value: Callable[[str], None],
                 value: str | None = None) -> None:
        """Create and show the dialog.

        Args:
            parent: Parent window.
            title: Window title.
            hint: Explanation.
            on_value: Receives the entered text.
            value: Visible preset; None asks for a hidden secret.
        """
        super().__init__(title=title, transient_for=parent, modal=True, default_width=380)
        self._on_value = on_value
        self.entry = (Gtk.PasswordEntry(show_peek_icon=True) if value is None
                      else Gtk.Entry(text=value))
        self.entry.set_hexpand(True)
        self.accept_button = Gtk.Button(label="OK")
        self.accept_button.add_css_class("suggested-action")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(Gtk.Label(label=hint, xalign=0, wrap=True))
        box.append(self.entry)
        box.append(self.accept_button)
        self.set_child(padded(box))
        self.accept_button.connect("clicked", self._accept)
        self.entry.connect("activate", self._accept)
        self.present()

    def submit(self) -> None:
        """Accept the current input."""
        self._accept()

    def _accept(self, *_: Any) -> None:
        """Hand over a non-empty value and close."""
        text = self.entry.get_text()
        if text.strip():
            self.destroy()
            self._on_value(text)


class ChoiceDialog(Gtk.Window):
    """Offers a few actions as buttons; closing the window chooses nothing."""

    def __init__(self, parent: Gtk.Window, title: str, hint: str,
                 choices: Sequence[tuple[str, Callable[[], None]]]) -> None:
        """Create and show the dialog.

        Args:
            parent: Parent window.
            title: Window title.
            hint: Explanation.
            choices: Pairs of button label and action.
        """
        super().__init__(title=title, transient_for=parent, modal=True, default_width=420)
        self._actions = [action for _, action in choices]
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(Gtk.Label(label=hint, xalign=0, wrap=True))
        for index, (label, _) in enumerate(choices):
            button = Gtk.Button(label=label)
            if index == 0:
                button.add_css_class("suggested-action")
            button.connect("clicked", lambda _b, i=index: self.choose(i))
            box.append(button)
        self.set_child(padded(box))
        self.present()

    def choose(self, index: int) -> None:
        """Close the dialog and run one action.

        Args:
            index: Position of the action.
        """
        self.destroy()
        self._actions[index]()
