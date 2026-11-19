"""Tests of connection control, profile import and server choice."""
import stat
import zipfile
from pathlib import Path

import pytest

from conftest import system
from fakes import VPN_PASSWORD

from cghostgui import connector, paths, profile, store, vpn
from cghostgui.catalog import Catalog
from cghostgui.errors import AuthRejected, CgError
from cghostgui.models import Template

OVPN = "client\nremote 87-1-ch.cg-dialup.net 443\nproto udp\n"
GROUP = Template("87-1-ch.cg-dialup.net", 443, "udp")


def archive(folder: Path, skip: str = "", ovpn: str = OVPN) -> str:
    """Create a configuration archive.

    Args:
        folder: Target folder.
        skip: File to leave out.
        ovpn: Content of the configuration.

    Returns:
        Path of the archive.
    """
    path = folder / "cfg.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        for name in sorted(profile.REQUIRED - {skip}):
            bundle.writestr(f"sub/{name}", ovpn if name.endswith("ovpn") else "x")
        bundle.writestr("../../evil.sh", "x")
    return str(path)


def catalog() -> Catalog:
    """Create a catalogue with a login.

    Returns:
        Catalogue.
    """
    result = Catalog()
    result.password = "acc$pw"
    return result


def target(**values: object) -> connector.Target:
    """Create a selection.

    Args:
        **values: Fields that differ from the default.

    Returns:
        Target.
    """
    base: dict = {"code": "DE", "service": None, "city": "", "server": "", "proto": "udp",
                  "label": "Germany"}
    return connector.Target(**{**base, **values})


def test_import(tmp_path: Path) -> None:
    """An archive becomes a private profile; foreign paths are ignored.

    Args:
        tmp_path: Temporary folder.
    """
    system().state = "activated"
    template = profile.import_zip(archive(tmp_path), " vpnuser ")
    assert (template.host, template.port, template.proto, template.group) == (
        "87-1-ch.cg-dialup.net", 443, "udp", "87-1")
    assert sorted(p.name for p in paths.profile_dir().iterdir()) == sorted(profile.REQUIRED)
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in paths.profile_dir().iterdir())
    assert not (tmp_path / "evil.sh").exists()
    assert system().username == "vpnuser"
    assert system().state == ""


def test_import_errors(tmp_path: Path) -> None:
    """Unusable archives are refused with a reason.

    Args:
        tmp_path: Temporary folder.
    """
    with pytest.raises(CgError, match="client.key"):
        profile.import_zip(archive(tmp_path, "client.key"), "u")
    (tmp_path / "bad.zip").write_text("no zip", encoding="utf-8")
    with pytest.raises(CgError, match="nicht lesbar"):
        profile.import_zip(str(tmp_path / "bad.zip"), "u")
    with pytest.raises(CgError, match="keinen Server"):
        profile.import_zip(archive(tmp_path, ovpn="client\n"), "u")


def test_import_without_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected nmcli answer stops the import.

    Args:
        tmp_path: Temporary folder.
        monkeypatch: Patch helper.
    """
    system().profile = False
    monkeypatch.setattr(vpn, "nm", lambda *a, **k: "nothing useful")
    with pytest.raises(CgError, match="Verbindungs-ID"):
        profile.import_zip(archive(tmp_path), "u")


def test_template_variants() -> None:
    """Port and protocol come from the remote line if present."""
    assert profile.read_template() is None
    store.private_dir(paths.profile_dir())
    (paths.profile_dir() / "openvpn.ovpn").write_text("remote a.example 1194 tcp-client\n",
                                                      encoding="utf-8")
    assert profile.read_template() == Template("a.example", 1194, "tcp")


def test_nm_errors() -> None:
    """nmcli failures become readable errors."""
    system().fail_nmcli = "reload"
    with pytest.raises(CgError, match="refused"):
        vpn.nm("connection", "reload")


def test_state_helpers() -> None:
    """State, remote and device are read from NetworkManager."""
    assert vpn.state() == "" and not vpn.is_active() and vpn.tunnel_device() is None
    system().state = "activated"
    assert vpn.is_active() and vpn.tunnel_device() == "lo"
    assert vpn.current_remote() == "87-1-ch.cg-dialup.net"
    system().profile = False
    assert not vpn.profile_exists()


def test_connect_ok_and_password_file_removed(tmp_path: Path) -> None:
    """A connection comes up and no password file remains.

    Args:
        tmp_path: Temporary folder.
    """
    vpn.connect(f" {VPN_PASSWORD} ")
    assert vpn.state() == "activated"
    assert not list(tmp_path.glob("cghost-*"))
    assert not any(VPN_PASSWORD in " ".join(call) for call in system().calls)


def test_connect_rejected() -> None:
    """A wrong password ends at once with a clear error."""
    with pytest.raises(AuthRejected):
        vpn.connect("wrong")


@pytest.mark.parametrize("mode,text", [("fail", "Keine Verbindung nach"),
                                       ("broken", "something else"), ("silent", "Exit 4")])
def test_connect_failures(mode: str, text: str) -> None:
    """Failures of nmcli are reported.

    Args:
        mode: Behaviour of the fake.
        text: Expected text.
    """
    system().connect_mode = mode
    with pytest.raises(CgError, match=text):
        vpn.connect(VPN_PASSWORD)


def test_connect_hanging_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hanging nmcli is ended at the deadline.

    Args:
        monkeypatch: Patch helper.
    """
    system().connect_mode = "hang"
    monkeypatch.setattr(vpn, "WAIT_SECONDS", -6)
    with pytest.raises(CgError, match="Keine Verbindung"):
        vpn.connect(VPN_PASSWORD)


def test_empty_password() -> None:
    """Empty passwords never reach nmcli."""
    with pytest.raises(CgError, match="Ungültiges"):
        vpn.connect("  ")


def test_log_without_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a cursor the log is read by time.

    Args:
        monkeypatch: Patch helper.
    """
    system().cursor = ""
    monkeypatch.setattr(vpn.re, "search", lambda *a, **k: None)
    mark = vpn.log_mark()
    assert mark.cursor == ""
    system().journal = "a\nb\n"
    assert vpn.vpn_log(mark, 1) == "b"
    assert "--since" in system().calls[-1]


def test_resolves() -> None:
    """Unknown hosts are detected."""
    assert vpn.resolves("ok.example") and not vpn.resolves("nope.example")


def test_pick_host() -> None:
    """Server, group address and least used server are chosen correctly."""
    cat = catalog()
    assert connector.pick_host(cat, target(server="abc"), GROUP) == "abc.cg-dialup.net"
    assert connector.pick_host(cat, target(), GROUP) == "87-1-de.cg-dialup.net"
    assert connector.pick_host(cat, target(proto="tcp"), GROUP).startswith("berlin-s02")
    assert connector.pick_host(cat, target(city="Frankfurt"), GROUP).startswith("frankfurt-s01-i02")
    other = target(code="US", service="Video One")
    assert connector.pick_host(cat, other, GROUP).startswith("atlanta")


def test_pick_host_empty() -> None:
    """Missing cities or servers are errors."""
    with pytest.raises(CgError, match="Keine Stadt"):
        connector.pick_host(catalog(), target(code="XX", proto="tcp"), GROUP)
    with pytest.raises(CgError, match="Kein Server"):
        connector.pick_host(catalog(), target(city="Nowhere"), GROUP)


def test_switch() -> None:
    """A switch stores the target and connects."""
    assert connector.switch(catalog(), target(), GROUP, VPN_PASSWORD) == "87-1-de.cg-dialup.net"
    assert store.read_settings()["target_cc"] == "DE" and vpn.state() == "activated"


def test_switch_keeps_tunnel_for_unknown_host() -> None:
    """A host that does not resolve leaves the tunnel alone."""
    system().state = "activated"
    with pytest.raises(CgError, match="nicht auflösbar"):
        connector.switch(catalog(), target(server="nope"), GROUP, VPN_PASSWORD)
    assert vpn.state() == "activated"


def test_switch_failure_reports_log() -> None:
    """A failed connection adds the OpenVPN log."""
    system().connect_mode = "broken"
    system().journal = ""
    with pytest.raises(CgError, match="VPN ist getrennt"):
        connector.switch(catalog(), target(), GROUP, VPN_PASSWORD)


def test_switch_rejection_passes_through() -> None:
    """A rejected login keeps its type."""
    with pytest.raises(AuthRejected):
        connector.switch(catalog(), target(), GROUP, "wrong")
