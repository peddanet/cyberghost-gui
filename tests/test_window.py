"""Tests of the GTK window and the application."""
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest.mock import MagicMock

import pytest

from conftest import system
from fakes import ACCOUNT_PASSWORD, VPN_PASSWORD

import gi
gi.require_version("Gtk", "4.0")
# pylint: disable=wrong-import-position,redefined-outer-name,protected-access
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from cghostgui import application, paths, profile, store  # noqa: E402
from cghostgui.errors import CgError  # noqa: E402
from cghostgui.window import Window  # noqa: E402

APP: list[application.Application] = []


def pump(until: Callable[[], Any], seconds: float = 8) -> None:
    """Run the main loop until a condition holds.

    Args:
        until: Condition.
        seconds: Limit.
    """
    context = GLib.MainContext.default()
    end = time.time() + seconds
    while not until():
        assert time.time() < end, "condition not reached"
        context.iteration(False)
        time.sleep(0.002)


def idle(window: Window) -> None:
    """Wait until all jobs of the window are finished.

    Args:
        window: Window.
    """
    pump(lambda: not window.busy and not window.pending)


def dialog(title: str) -> Any:
    """Find an open dialog.

    Args:
        title: Dialog title.

    Returns:
        The dialog.
    """
    found: list[Any] = []

    def search() -> bool:
        """Look for the dialog.

        Returns:
            True if it is open.
        """
        found[:] = [w for w in Gtk.Window.list_toplevels()
                    if w.get_title() == title and w.get_visible()]
        return bool(found)

    pump(search)
    return found[0]


def answer(title: str, value: str) -> None:
    """Fill in and accept a dialog.

    Args:
        title: Dialog title.
        value: Input.
    """
    window = dialog(title)
    window.entry.set_text(value)
    window.submit()


def app() -> application.Application:
    """Return the application shared by the tests.

    Returns:
        Application.
    """
    if not APP:
        APP.append(application.Application(start_tray=False))
        APP[0].set_flags(Gio.ApplicationFlags.NON_UNIQUE)
        APP[0].register(None)
    return APP[0]


def seed_profile() -> None:
    """Install a configuration."""
    store.private_dir(paths.profile_dir())
    (paths.profile_dir() / "openvpn.ovpn").write_text(
        "remote 87-1-ch.cg-dialup.net 443\nproto udp\n", encoding="utf-8")


@pytest.fixture(name="window")
def window_fixture() -> Iterator[Window]:
    """Create a logged-in window with loaded lists.

    Yields:
        Window.
    """
    system().keyring["account"] = ACCOUNT_PASSWORD
    seed_profile()
    win = Window(app())
    idle(win)
    yield win
    idle(win)
    win.destroy()


def test_lists_shown(window: Window) -> None:
    """Countries and services appear after the start.

    Args:
        window: Window.
    """
    assert window.ui.country.values == ["DE", "US"]
    assert window.ui.service.values == ["Video One\tUS", "Video Two\tDE"]
    assert window.get_title().startswith("CyberGhost VPN ")
    assert window.ui.city.values == ["", "Berlin", "Frankfurt"]


def test_selection_chain(window: Window) -> None:
    """Choosing country and city fills the following lists.

    Args:
        window: Window.
    """
    window.ui.country.select("US")
    idle(window)
    assert "New York" in window.ui.city.values
    window.ui.city.select("New York")
    idle(window)
    assert window.ui.server.values == ["", "newyork-s23-i12"]
    window.ui.city.select("")
    idle(window)
    assert window.ui.server.values == [""]


def test_streaming_mode(window: Window) -> None:
    """The streaming mode swaps the selection rows.

    Args:
        window: Window.
    """
    window.ui.mode.select("streaming")
    idle(window)
    assert window.ui.service.widget.get_visible() and not window.ui.country.widget.get_visible()
    window.ui.service.select("Video One\tUS")
    idle(window)
    assert "Atlanta" in window.ui.city.values


def test_password_asked_once(window: Window) -> None:
    """The password is asked once, stored and reused.

    Args:
        window: Window.
    """
    window.start_connect()
    answer("OpenVPN-Passwort", VPN_PASSWORD)
    idle(window)
    assert window.ui.state.get_text() == "Verbunden: 87-1-de.cg-dialup.net"
    assert window.ui.connect.get_label() == "Ziel wechseln"
    assert system().keyring["openvpn"] == VPN_PASSWORD
    window.vpn_password = None
    window.start_connect()
    idle(window)
    assert "Verbunden mit" in window.ui.log.get_text()
    window.start_disconnect()
    idle(window)
    assert window.ui.state.get_text() == "Nicht verbunden"


def choose(title: str, index: int) -> None:
    """Pick a button of an open choice dialog.

    Args:
        title: Dialog title.
        index: Button position.
    """
    dialog(title).choose(index)


def test_rejected_vpn_login_is_kept_until_replaced(window: Window) -> None:
    """A refused OpenVPN password stays until the user enters a new one.

    Args:
        window: Window.
    """
    system().keyring["openvpn"] = "wrong"
    window.start_connect()
    choose("OpenVPN-Anmeldung abgelehnt", 0)
    choose("OpenVPN-Anmeldung abgelehnt", 2)
    assert system().keyring["openvpn"] == "wrong"
    window.start_connect()
    choose("OpenVPN-Anmeldung abgelehnt", 1)
    answer("OpenVPN-Benutzername", " newuser ")
    assert system().username == "newuser"
    assert system().keyring["openvpn"] == "wrong"
    answer("OpenVPN-Passwort", VPN_PASSWORD)
    idle(window)
    assert system().state == "activated"


def test_username_error_is_shown(window: Window) -> None:
    """A failure while storing the user name is reported.

    Args:
        window: Window.
    """
    window._ask_vpn_login("Abgelehnt")
    system().fail_nmcli = "username="
    answer("OpenVPN-Benutzername", "x")
    assert "Fehler" in window.ui.log.get_text()


def test_keyring_failure_is_reported(window: Window) -> None:
    """A locked key ring does not stop the connection.

    Args:
        window: Window.
    """
    system().keyring_works = False
    window._ask_secret("Titel", "Hinweis", "openvpn", window.say)
    answer("Titel", "abc")
    assert window.ui.log.get_text() == "abc"


def test_connect_preconditions(window: Window) -> None:
    """Missing profile or target are explained.

    Args:
        window: Window.
    """
    system().profile = False
    window.start_connect()
    assert "importieren" in window.ui.log.get_text()
    system().profile = True
    window.ui.country.fill([])
    window.start_connect()
    assert "Ziel" in window.ui.log.get_text()
    window.ui.mode.fill([("Streaming", "streaming")])
    window.ui.service.fill([])
    assert window._target() == (None, None)
    window._target_changed()
    window._city_changed()


def test_connection_error_shown(window: Window) -> None:
    """Errors of a job reach the status area.

    Args:
        window: Window.
    """
    system().keyring["openvpn"] = VPN_PASSWORD
    system().connect_mode = "broken"
    window.start_connect()
    idle(window)
    assert window.ui.log.get_text().startswith("Fehler: Error: something else")


def test_check_button(window: Window) -> None:
    """The check shows its result and remembers the test address.

    Args:
        window: Window.
    """
    window.ui.lan.set_text("192.0.2.1")
    window.ui.check.emit("clicked")
    idle(window)
    assert "Heimnetz 192.0.2.1" in window.ui.log.get_text()
    assert store.read_settings()["lan_target"] == "192.0.2.1"


def test_newest_waiting_job_wins(window: Window) -> None:
    """While busy only the newest request is kept.

    Args:
        window: Window.
    """
    results: list[str] = []
    window.background(lambda: time.sleep(0.05))
    window.background(lambda: "a", results.append)
    window.background(lambda: "b", results.append)
    idle(window)
    assert results == ["b"]


def test_periodic_refresh(window: Window) -> None:
    """The timer follows the connection state, also during activation.

    Args:
        window: Window.
    """
    system().state = "activating"
    assert window._tick()
    assert window.ui.state.get_text().startswith("Verbindungsaufbau")
    window.busy = True
    system().state = ""
    assert window._tick()
    window.busy = False


def test_import_flow(window: Window, tmp_path: Path) -> None:
    """Importing asks for the user name and reports the template.

    Args:
        window: Window.
        tmp_path: Temporary folder.
    """
    archive = tmp_path / "c.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in profile.REQUIRED:
            bundle.writestr(name, "remote 87-1-at.cg-dialup.net 443\n")
    window.ask_import_user(str(archive))
    answer("OpenVPN-Benutzername", "user2")
    idle(window)
    assert "Importiert" in window.ui.log.get_text()
    window._choose_archive()


def test_login_flow() -> None:
    """Without a login the user is asked once and the lists appear."""
    seed_profile()
    win = Window(app())
    answer("CyberGhost-Konto: E-Mail-Adresse", "me")
    answer("CyberGhost-Konto: Passwort", ACCOUNT_PASSWORD)
    pump(lambda: bool(win.ui.country.values))
    idle(win)
    assert system().keyring["account"] == ACCOUNT_PASSWORD
    assert store.read_settings()["account_user"] == "me"
    win.destroy()


def test_rejected_account_password_is_kept() -> None:
    """A refused account password is kept until the user enters a new one."""
    system().keyring["account"] = "wrong"
    store.write_settings({"account_user": "me"})
    win = Window(app())
    choose("CyberGhost-Konto: Anmeldung abgelehnt", 0)
    choose("CyberGhost-Konto: Anmeldung abgelehnt", 2)
    assert system().keyring["account"] == "wrong"
    win.read_lists(True)
    choose("CyberGhost-Konto: Anmeldung abgelehnt", 1)
    answer("CyberGhost-Konto: Passwort", ACCOUNT_PASSWORD)
    pump(lambda: bool(win.ui.country.values))
    idle(win)
    assert system().keyring["account"] == ACCOUNT_PASSWORD
    win.catalog.password = None
    win._ask_login("Login nötig", None)
    answer("CyberGhost-Konto: Passwort", ACCOUNT_PASSWORD)
    win.destroy()


def test_start_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing tools and a missing profile are mentioned.

    Args:
        monkeypatch: Patch helper.
    """
    system().profile = False
    system().keyring["account"] = ACCOUNT_PASSWORD
    monkeypatch.setattr("cghostgui.diagnostics.missing_tools", lambda: ["nmcli"])
    win = Window(app())
    idle(win)
    win.destroy()


def test_close_and_application(window: Window, monkeypatch: pytest.MonkeyPatch) -> None:
    """Closing hides with an indicator and quits without one; reload waits for idle.

    Args:
        window: Window.
        monkeypatch: Patch helper.
    """
    instance = app()
    assert not instance.tray_alive()
    instance.tray = MagicMock()
    instance.tray.poll.return_value = None
    window.present()
    assert window._on_close()
    assert not window.get_visible()
    restarts: list[bool] = []
    monkeypatch.setattr(instance, "restart", restarts.append)
    window.busy = True
    instance.request_reload()
    instance.idle_now()
    assert not restarts
    window.busy = False
    pump(lambda: restarts)
    assert restarts == [False] and instance.tray.terminate.called
    instance._reload_wanted = False
    instance.tray = None
    quits = MagicMock()
    monkeypatch.setattr(instance, "quit", quits)
    window._on_close()
    quits.assert_called_once()


def test_activate_paths(window: Window, monkeypatch: pytest.MonkeyPatch) -> None:
    """Activation shows the existing window unless a hidden start was asked for.

    Args:
        window: Window.
        monkeypatch: Patch helper.
    """
    instance = app()
    shown = MagicMock()
    monkeypatch.setattr(window, "present", shown)
    monkeypatch.setattr(instance, "get_windows", lambda: [window])
    instance._hidden = True
    instance.do_activate()
    shown.assert_not_called()
    instance.do_activate()
    shown.assert_called_once()


def test_startup_starts_indicator(monkeypatch: pytest.MonkeyPatch) -> None:
    """The start-up registers actions and launches the indicator process.

    Args:
        monkeypatch: Patch helper.
    """
    popen = MagicMock()
    monkeypatch.setattr(application.subprocess, "Popen", popen)
    other = application.Application()
    other.set_application_id("local.cghostgui.Test")
    other.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
    other.register(None)
    assert popen.call_args[0][0][1:] == ["-m", "cghostgui.tray"]
    assert other.lookup_action("reload") is not None
    restarts: list[bool] = []
    monkeypatch.setattr(other, "restart", restarts.append)
    other.activate_action("reload", None)
    pump(lambda: restarts)
    assert restarts == [False]
    other.release()


def test_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry point passes the hidden flag on.

    Args:
        monkeypatch: Patch helper.
    """
    created = MagicMock()
    created.return_value.run.return_value = 0
    monkeypatch.setattr(application, "Application", created)
    monkeypatch.setattr(application.sys, "argv", ["x", application.HIDDEN])
    assert application.main() == 0
    created.assert_called_once_with(hidden=True)


def test_errors_are_readable() -> None:
    """Errors keep their text."""
    assert str(CgError("x")) == "x"
