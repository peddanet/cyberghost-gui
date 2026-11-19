"""Panel indicator with live details.

It runs as its own process because the indicator library needs GTK 3 while
the window uses GTK 4.
"""
import subprocess
import sys
import threading
from types import SimpleNamespace
from typing import Any

from cghostgui import diagnostics, paths, traymodel, vpn

WATCHER = "org.kde.StatusNotifierWatcher"


def import_toolkit() -> SimpleNamespace:  # pragma: no cover
    """Import GTK 3 and the indicator library.

    Returns:
        Namespace with ``Gtk``, ``AI``, ``Gio`` and ``GLib``.
    """
    # pylint: disable=import-outside-toplevel
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk
    return SimpleNamespace(Gtk=Gtk, AI=AyatanaAppIndicator3, Gio=Gio, GLib=GLib)


class Tray:
    """The indicator and its menu."""

    def __init__(self, kit: Any) -> None:
        """Create the indicator.

        Args:
            kit: Toolkit namespace from :func:`import_toolkit`.
        """
        self._kit = kit
        self._bus = kit.Gio.bus_get_sync(kit.Gio.BusType.SESSION)
        self._item = kit.AI.Indicator.new("cyberghost-gui", traymodel.ICON_OFF,
                                          kit.AI.IndicatorCategory.COMMUNICATIONS)
        self._item.set_status(kit.AI.IndicatorStatus.ACTIVE)
        self._item.set_title("CyberGhost VPN")
        self._info_for: str | None = None
        self._info: dict[str, Any] | None = None
        self._traffic = traymodel.Traffic()
        self._lines: dict[str, Any] = {}
        self._down = self._build_menu()
        kit.Gio.bus_watch_name_on_connection(self._bus, paths.APP_ID,
                                             kit.Gio.BusNameWatcherFlags.NONE, None,
                                             lambda *_: kit.Gtk.main_quit())
        self.update()
        kit.GLib.timeout_add_seconds(traymodel.INTERVAL, self.update)

    def _entry(self, menu: Any, label: str, handler: Any) -> Any:
        """Append a menu entry.

        Args:
            menu: Menu.
            label: Text.
            handler: Activation handler.

        Returns:
            The entry.
        """
        entry = self._kit.Gtk.MenuItem(label=label)
        entry.connect("activate", handler)
        menu.append(entry)
        return entry

    def _build_menu(self) -> Any:
        """Create the menu; every detail line opens the window.

        Returns:
            The disconnect entry.
        """
        menu = self._kit.Gtk.Menu()
        for key in traymodel.KEYS:
            self._lines[key] = self._entry(menu, "", self.open_window)
        menu.append(self._kit.Gtk.SeparatorMenuItem())
        change = self._entry(menu, "Ziel ändern …", self.open_window)
        down = self._entry(menu, "Trennen", self.disconnect)
        self._entry(menu, "Beenden", self.quit_app)
        menu.show_all()
        self._item.set_menu(menu)
        self._item.set_secondary_activate_target(change)
        return down

    def _fetch_info(self, remote: str) -> None:
        """Ask for the public address in the background.

        Args:
            remote: Host the answer belongs to.
        """
        data = diagnostics.public_info()
        self._kit.GLib.idle_add(self._got_info, remote, data)

    def _got_info(self, remote: str, data: dict[str, Any] | None) -> bool:
        """Take over the public address.

        Args:
            remote: Host the answer belongs to.
            data: Address data.

        Returns:
            False, to run once.
        """
        if remote == self._info_for:
            self._info = data
        return False

    def _view(self) -> traymodel.View:
        """Compute what to show.

        Returns:
            View.
        """
        state = vpn.state()
        remote = vpn.current_remote() if state else None
        if state != "activated":
            self._info_for, self._info = None, None
            self._traffic.last = None
            return traymodel.idle_view(state, remote)
        if remote != self._info_for:
            self._info_for, self._info = remote, None
            self._traffic.reset()
            threading.Thread(target=self._fetch_info, args=(remote,), daemon=True).start()
        return traymodel.connected_view(remote, self._info, self._traffic)

    def update(self) -> bool:
        """Refresh icon, panel text and menu.

        Returns:
            True, to keep the timer running.
        """
        view = self._view()
        self._item.set_icon_full(view.icon, "CyberGhost VPN")
        self._item.set_label(view.label, traymodel.LABEL_GUIDE)
        self._down.set_sensitive(view.connected)
        for key, entry in self._lines.items():
            text = view.lines[key]
            entry.set_visible(bool(text))
            if text:
                entry.set_label(text)
        return True

    def open_window(self, *_: Any) -> None:
        """Show the window; a second start only signals the running instance.

        Args:
            *_: Signal arguments.
        """
        with subprocess.Popen([sys.executable, "-m", "cghostgui"]):
            pass

    def disconnect(self, *_: Any) -> None:
        """Take the connection down.

        Args:
            *_: Signal arguments.
        """
        with subprocess.Popen(["nmcli", "connection", "down", paths.CONNECTION],
                              stdout=subprocess.DEVNULL):
            pass

    def quit_app(self, *_: Any) -> None:
        """Ask the application to end; an established tunnel stays up.

        Args:
            *_: Signal arguments.
        """
        variant = self._kit.GLib.Variant("(sava{sv})", ("quit", [], {}))
        self._bus.call_sync(paths.APP_ID, paths.APP_PATH, "org.gtk.Actions", "Activate", variant,
                            None, self._kit.Gio.DBusCallFlags.NONE, 3000, None)


def has_tray_host(kit: Any) -> bool:
    """Tell whether the desktop shows indicators.

    Args:
        kit: Toolkit namespace.

    Returns:
        True if a host is running.
    """
    bus = kit.Gio.bus_get_sync(kit.Gio.BusType.SESSION)
    reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                          "NameHasOwner", kit.GLib.Variant("(s)", (WATCHER,)), None,
                          kit.Gio.DBusCallFlags.NONE, 2000, None)
    return bool(reply.unpack()[0])


def main(kit: Any = None) -> int:
    """Run the indicator.

    Args:
        kit: Toolkit namespace, loaded if omitted.

    Returns:
        0 after a normal end, 3 without an indicator host.
    """
    toolkit = kit or import_toolkit()
    if not has_tray_host(toolkit):
        return 3
    Tray(toolkit)
    toolkit.Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
