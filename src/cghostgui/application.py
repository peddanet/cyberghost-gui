"""GTK application: single instance, indicator process, live switch to a new release."""
import os
import subprocess
import sys
from typing import Any

import gi
gi.require_version("Gtk", "4.0")
# pylint: disable=wrong-import-position
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from cghostgui import paths  # noqa: E402
from cghostgui.window import Window  # noqa: E402

HIDDEN = "--hidden"


class Application(Gtk.Application):
    """Keeps running while the window is hidden."""

    def __init__(self, hidden: bool = False, start_tray: bool = True) -> None:
        """Create the application.

        Args:
            hidden: Start without showing the window.
            start_tray: Start the indicator process.
        """
        super().__init__(application_id=paths.APP_ID)
        self._hidden = hidden
        self._start_tray = start_tray
        self._reload_wanted = False
        self.tray: subprocess.Popen[bytes] | None = None

    def do_startup(self, *args: Any) -> None:  # pylint: disable=arguments-differ
        """Register actions and start the indicator.

        Args:
            *args: Unused.
        """
        Gtk.Application.do_startup(self, *args)
        for name, handler in (("quit", lambda *_: self.quit()),
                              ("reload", lambda *_: self.request_reload())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
        self.hold()
        if self._start_tray:
            # pylint: disable-next=consider-using-with
            self.tray = subprocess.Popen([sys.executable, "-m", "cghostgui.tray"])

    def do_activate(self) -> None:  # pylint: disable=arguments-differ
        """Show the window, creating it on the first call."""
        windows = self.get_windows()
        window = windows[0] if windows else Window(self)
        if self._hidden:
            self._hidden = False
        else:
            window.present()

    def tray_alive(self) -> bool:
        """Tell whether the indicator runs.

        Returns:
            True if its process is alive.
        """
        return self.tray is not None and self.tray.poll() is None

    def request_reload(self) -> None:
        """Switch to the installed release as soon as no job runs.

        The short delay lets the request be answered before the process is replaced.
        """
        self._reload_wanted = True
        GLib.timeout_add(300, self._reload_timer)

    def _reload_timer(self) -> bool:
        """Try the switch once.

        Returns:
            False, to run once.
        """
        self.idle_now()
        return False

    def idle_now(self) -> None:
        """Carry out a waiting switch when the window is idle.

        The VPN is held by NetworkManager and is not affected.
        """
        windows = self.get_windows()
        if not self._reload_wanted or (windows and windows[0].busy):
            return
        visible = bool(windows and windows[0].get_visible())
        if self.tray_alive():
            self.tray.terminate()  # type: ignore[union-attr]
        self.restart(visible)

    @staticmethod
    def restart(visible: bool) -> None:  # pragma: no cover
        """Replace this process by the installed release.

        Args:
            visible: Whether the window is to be shown again.
        """
        arguments = [sys.executable, "-m", "cghostgui"] + ([] if visible else [HIDDEN])
        os.execv(sys.executable, arguments)  # nosec B606


def main() -> int:
    """Run the application.

    Returns:
        Exit code.
    """
    return int(Application(hidden=HIDDEN in sys.argv[1:]).run([]))
