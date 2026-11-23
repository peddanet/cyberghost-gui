"""Tests of the move from the old single folder to the XDG layout."""
from pathlib import Path

import pytest

from conftest import system

from cghostgui import migrate, paths

FILES = ("openvpn.ovpn", "ca.crt", "client.crt", "client.key")


def old_layout() -> Path:
    """Create the folder of release 0.5.1 with a profile that points into it.

    Returns:
        The old folder.
    """
    old = paths.legacy_dir()
    paths.vendor_binary().unlink()
    for name, text in (("settings.json", "{}"), ("privacy/denylist.txt", "term\n"),
                       ("cache/countries.json", "[]"), ("vendor/cyberghostvpn", "bin"),
                       ("venv/bin/python", "")):
        (old / name).parent.mkdir(parents=True, exist_ok=True)
        (old / name).write_text(text, encoding="utf-8")
    (old / "profile").mkdir()
    for name in FILES:
        (old / "profile" / name).write_text(name, encoding="utf-8")
    system().vpn_files = {"ca": f"{old}/profile/ca.crt", "cert": f"{old}/profile/client.crt",
                          "key": f"{old}/profile/client.key"}
    return old


def test_nothing_to_do() -> None:
    """Without the old folder nothing happens."""
    assert not migrate.migrate()


def test_full_move() -> None:
    """Every file reaches its new place, the profile follows, only the venv stays."""
    old = old_layout()
    report = migrate.migrate()
    assert paths.settings_file().read_text(encoding="utf-8") == "{}"
    assert (paths.config_dir() / "privacy/denylist.txt").exists()
    assert (paths.cache_dir() / "countries.json").exists()
    assert paths.vendor_binary().read_text(encoding="utf-8") == "bin"
    assert sorted(p.name for p in paths.profile_dir().iterdir()) == sorted(FILES)
    assert all((p.stat().st_mode & 0o777) == 0o600 for p in paths.profile_dir().iterdir())
    assert system().vpn_files["ca"] == str(paths.profile_dir() / "ca.crt")
    assert sorted(p.name for p in old.iterdir()) == ["venv"]
    assert any("verschoben" in line for line in report)
    assert report[-1].endswith("verbleibt: venv")


def test_nothing_is_overwritten() -> None:
    """An existing target keeps its content and the old file stays."""
    old = old_layout()
    paths.config_dir().mkdir(parents=True)
    paths.settings_file().write_text("new", encoding="utf-8")
    paths.profile_dir().mkdir()
    (paths.profile_dir() / "ca.crt").write_text("other", encoding="utf-8")
    report = migrate.migrate()
    assert paths.settings_file().read_text(encoding="utf-8") == "new"
    assert (old / "settings.json").exists()
    assert "bleibt (Ziel existiert schon)" in "\n".join(report)
    assert "bleibt (Ziel ist verschieden)" in "\n".join(report)
    assert (old / "profile/ca.crt").exists()


def test_profile_kept_while_connected() -> None:
    """While the VPN is up the old configuration stays; a later run removes it."""
    old = old_layout()
    system().state = "activated"
    report = migrate.migrate()
    assert "bis nach dem Trennen" in "\n".join(report)
    assert (old / "profile/client.key").exists()
    system().state = ""
    report = migrate.migrate()
    assert not (old / "profile").exists()
    assert any(line.startswith("entfernt") for line in report)


def test_profile_change_refused() -> None:
    """If NetworkManager refuses the change, the old files stay."""
    old = old_layout()
    system().fail_nmcli = "modify"
    report = migrate.migrate()
    assert any("Profil nicht angepasst" in line for line in report)
    assert (old / "profile/ca.crt").exists()


def test_profile_still_referenced() -> None:
    """A reference that cannot be redirected keeps the old files."""
    old = old_layout()
    system().vpn_files["tls-crypt"] = f"{old}/profile/ta.key"
    report = migrate.migrate()
    assert any("verweist noch" in line for line in report)


def test_unknown_profile() -> None:
    """Without a NetworkManager profile the copies are kept and the old files go."""
    old = old_layout()
    system().fail_nmcli = "vpn.data"
    migrate.migrate()
    assert not (old / "profile").exists()


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    """The command prints one line per action.

    Args:
        capsys: Output capture.
    """
    old_layout()
    assert migrate.main() == 0
    assert "verschoben" in capsys.readouterr().out
