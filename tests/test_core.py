"""Tests of settings, key ring, program runner and path helpers."""
import getpass
import stat
import subprocess
import sys

import pytest

from conftest import system

from cghostgui import keyring, paths, proc, reload, store
from cghostgui.models import Template


def test_settings_round_trip_is_private() -> None:
    """Settings survive a round trip and only the user can read them."""
    assert store.read_settings() == {}
    store.write_settings({"a": 1})
    assert store.read_settings() == {"a": 1}
    assert stat.S_IMODE(paths.settings_file().stat().st_mode) == 0o600


@pytest.mark.parametrize("text", ["not json", "[1]"])
def test_damaged_settings_are_ignored(text: str) -> None:
    """Unusable settings count as empty.

    Args:
        text: File content.
    """
    store.private_dir(paths.app_dir())
    paths.settings_file().write_text(text, encoding="utf-8")
    assert store.read_settings() == {}


def test_keyring() -> None:
    """Secrets are stored, read and removed."""
    assert keyring.Keyring.get("openvpn") is None
    assert keyring.Keyring.put("openvpn", "x")
    assert keyring.Keyring.get("openvpn") == "x"
    keyring.Keyring.clear("openvpn")
    assert keyring.Keyring.get("openvpn") is None
    system().keyring_works = False
    assert not keyring.Keyring.put("openvpn", "x")


def test_secret_never_on_command_line() -> None:
    """A stored secret is not part of any command line."""
    keyring.Keyring.put("account", "very-secret")
    assert not any("very-secret" in " ".join(call) for call in system().calls)


def test_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real runner reports output, missing programs and timeouts.

    Args:
        monkeypatch: Patch helper.
    """
    monkeypatch.undo()
    python = sys.executable
    done = proc.run([python, "-c", "import sys; print(sys.stdin.read())"], 20, stdin="hello")
    assert (done.code, done.out.strip()) == (0, "hello")
    assert proc.run(["no-such-program-here"]).code == 127
    assert proc.run([python, "-c", "import time; time.sleep(9)"], 1).code == 124


def test_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default locations follow the documented layout.

    Args:
        monkeypatch: Patch helper.
    """
    monkeypatch.undo()
    monkeypatch.delenv("CGHOST_GUI_HOME", raising=False)
    assert paths.app_dir().parts[-2:] == ("scripts", "cyberghost-gui")
    assert paths.vendor_home().parts[-2:] == (getpass.getuser(), ".cyberghost")


def test_template_group() -> None:
    """Only group addresses have a group."""
    assert Template("87-1-ch.cg-dialup.net", 443, "udp").group == "87-1"
    assert Template("berlin-s1.cg-dialup.net", 443, "udp").group is None


def test_reload_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reload request reports whether an instance answered.

    Args:
        monkeypatch: Patch helper.
    """
    answers = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)]
    monkeypatch.setattr(reload.subprocess, "run", lambda *a, **k: answers.pop(0))
    assert reload.main() == 0
    assert reload.main() == 1
