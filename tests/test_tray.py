"""Tests of diagnostics and the indicator."""
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from conftest import system

from cghostgui import diagnostics, paths, store, tray, traymodel
from cghostgui.proc import Result

REMOTE = "87-1-de.cg-dialup.net"


def countries() -> None:
    """Provide a cached country list."""
    store.private_dir(paths.cache_dir())
    (paths.cache_dir() / "countries.json").write_text(
        '[["DE", "Germany"], ["FR", "France"]]', encoding="utf-8")


def toolkit(host: bool = True) -> Any:
    """Create a fake toolkit.

    Args:
        host: Whether an indicator host exists.

    Returns:
        Namespace.
    """
    kit: Any = SimpleNamespace(Gtk=MagicMock(), AI=MagicMock(), Gio=MagicMock(), GLib=MagicMock())
    kit.Gtk.MenuItem.side_effect = lambda label="": MagicMock(label=label)
    bus = kit.Gio.bus_get_sync.return_value
    bus.call_sync.return_value.unpack.return_value = (host,)
    return kit


def test_ipv6_path() -> None:
    """All routing answers are told apart."""
    fake = system()
    assert "gesperrt" in diagnostics.ipv6_path("tun0")
    fake.ipv6_route = Result(0, "unreachable x dev lo metric 1", "")
    assert "gesperrt" in diagnostics.ipv6_path("tun0")
    fake.ipv6_route = Result(0, "x via y dev eth9 proto ra", "")
    assert diagnostics.ipv6_path("tun0") == "am Tunnel vorbei über eth9"
    fake.ipv6_route = Result(0, "x dev tun0", "")
    assert diagnostics.ipv6_path("tun0") == "im Tunnel"


def test_wait_for_block() -> None:
    """Waiting ends at the time limit while IPv6 still bypasses the tunnel."""
    system().ipv6_route = Result(0, "x via y dev eth9", "")
    diagnostics.wait_ipv6_block(0.01)
    assert system().calls[-1][0] in ("ip", "nmcli")


def test_location_warning() -> None:
    """Chosen and reported country are compared."""
    assert diagnostics.location_warning({"country": "DE"}, REMOTE) == ""
    assert diagnostics.location_warning(None, REMOTE) == ""
    assert "gemeldet: FR" in diagnostics.location_warning({"country": "FR"}, REMOTE)
    countries()
    text = diagnostics.location_warning({"country": "FR"}, REMOTE)
    assert "Germany (DE)" in text and "France (FR)" in text


def test_labels_from_settings() -> None:
    """Stored target data win over the host name."""
    assert diagnostics.target_label(None) == "?"
    assert diagnostics.target_label("x.example") == "x.example"
    store.write_settings({"target_host": "h", "target_label": "Video", "target_cc": "us"})
    assert diagnostics.target_label("h") == "Video"
    assert diagnostics.expected_country("h") == "US"


def test_check_lines() -> None:
    """The check reports address, warnings, IPv6 and home network."""
    fake = system()
    fake.state, fake.remote = "activated", "87-1-us.cg-dialup.net"
    fake.ipv6_seen = "2001:db8::1"
    lines = diagnostics.check("192.0.2.1")
    assert lines[0].startswith("Öffentlich: 203.0.113.5")
    assert lines[1].startswith("WARNUNG Gewählt")
    assert "2001:db8::1" in lines[2] and lines[3].endswith(": erreichbar")
    fake.public, fake.ipv6_seen, fake.ping_ok = None, "", False
    lines = diagnostics.check("192.0.2.1")
    assert "nicht ermittelbar" in lines[0] and "NICHT" in lines[-1]
    assert len(diagnostics.check()) == 2


def test_public_info_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unusable answers count as unknown.

    Args:
        monkeypatch: Patch helper.
    """
    answers = [Result(0, "no json", ""), Result(0, "[1]", "")]
    monkeypatch.setattr(diagnostics.proc, "run", lambda *a, **k: answers.pop(0))
    assert diagnostics.public_info() is None
    assert diagnostics.public_info() is None


def test_missing_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing programs are listed.

    Args:
        monkeypatch: Patch helper.
    """
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: None)
    assert "nmcli" in diagnostics.missing_tools()


def test_formatting() -> None:
    """Sizes, bars and durations are formatted."""
    assert traymodel.human_size(5) == "5 B"
    assert traymodel.human_size(1500) == "1.5 KB"
    assert traymodel.human_size(2e12) == "2.0 TB"
    assert traymodel.spark([0, 10]) == "▁█" and traymodel.spark([0]) == "▁"
    assert traymodel.uptime() == "00:01:05"
    system().ages = ""
    assert traymodel.uptime() == "?"


def test_traffic() -> None:
    """Counters give rates; a missing device resets them."""
    meter = traymodel.Traffic()
    assert meter.sample("lo") is not None
    assert meter.sample("lo") is not None
    assert len(meter.down) == 1
    assert meter.sample("no-such-device") is None and meter.last is None
    meter.reset()
    assert not meter.down


def test_views() -> None:
    """Connected and idle views contain the right lines."""
    fake = system()
    fake.state, fake.remote = "activated", REMOTE
    view = traymodel.connected_view(REMOTE, {"ip": "1", "country": "FR"}, traymodel.Traffic())
    assert view.label.endswith("⚠") and view.icon == traymodel.ICONS["activated"]
    assert view.lines["geo"].startswith("⚠") and view.lines["ip"].endswith("1")
    plain = traymodel.connected_view(REMOTE, None, traymodel.Traffic())
    assert plain.lines["org"] == "" and "wird ermittelt" in plain.lines["ip"]
    assert traymodel.idle_view("activating", REMOTE).connected
    assert traymodel.idle_view("", None).label == "CyberGhost VPN aus"


def test_tray_follows_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The indicator changes with the connection and finds the public address.

    Args:
        monkeypatch: Patch helper.
    """
    thread = MagicMock()
    monkeypatch.setattr(tray, "threading", SimpleNamespace(Thread=thread))
    kit = toolkit()
    item = tray.Tray(kit)
    icon = kit.AI.Indicator.new.return_value.set_icon_full
    assert icon.call_args[0][0] == traymodel.ICON_OFF
    fake = system()
    fake.state, fake.remote = "activated", REMOTE
    item.update()
    assert icon.call_args[0][0] == traymodel.ICONS["activated"]
    thread.assert_called_once()
    item.update()
    thread.assert_called_once()
    kit.GLib.idle_add.side_effect = lambda function, *args: function(*args)
    item._fetch_info(REMOTE)  # pylint: disable=protected-access
    item._got_info("other", None)  # pylint: disable=protected-access
    assert item.update()


def test_tray_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Menu actions start the right programs.

    Args:
        monkeypatch: Patch helper.
    """
    popen = MagicMock()
    monkeypatch.setattr(tray, "subprocess", SimpleNamespace(Popen=popen, DEVNULL=-3))
    kit = toolkit()
    item = tray.Tray(kit)
    item.open_window()
    assert popen.call_args[0][0][1:] == ["-m", "cghostgui"]
    item.disconnect()
    assert popen.call_args[0][0][:2] == ["nmcli", "connection"]
    item.quit_app()
    assert kit.Gio.bus_get_sync.return_value.call_sync.call_args[0][3] == "Activate"


def test_tray_main() -> None:
    """The indicator only runs with a host."""
    assert tray.main(toolkit(host=False)) == 3
    kit = toolkit()
    assert tray.main(kit) == 0
    kit.Gtk.main.assert_called_once()
