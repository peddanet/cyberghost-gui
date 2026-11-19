"""Common test setup: temporary folders and a fake operating system."""
import os
import socket
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

sys.path.insert(0, os.path.dirname(__file__))
# pylint: disable=wrong-import-position
from fakes import FakeSystem  # noqa: E402

from cghostgui import diagnostics, paths, proc, vpn  # noqa: E402

CURRENT: list[FakeSystem] = []


def system() -> FakeSystem:
    """Return the fake system of the running test.

    Returns:
        Fake system.
    """
    return CURRENT[-1]


@pytest.fixture(autouse=True)
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate every test.

    Args:
        tmp_path: Temporary folder.
        monkeypatch: Patch helper.

    Yields:
        Nothing.
    """
    fake = FakeSystem()
    CURRENT.append(fake)
    monkeypatch.setenv("CGHOST_GUI_HOME", str(tmp_path / "app"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "vendor_home", lambda: tmp_path / "vendor-home")
    binary = paths.vendor_binary()
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="ascii")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host: str, *args: Any, **kwargs: Any) -> Any:
        """Resolve every host except the ones meant to fail.

        Args:
            host: Host name.
            *args: Further arguments.
            **kwargs: Further arguments.

        Returns:
            Address list.

        Raises:
            OSError: The host is meant to fail.
        """
        if "nope" in host:
            raise OSError("no such host")
        return real_getaddrinfo("127.0.0.1", *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(proc, "run", fake.run)
    monkeypatch.setattr(vpn, "subprocess", fake.namespace())
    clock = SimpleNamespace(time=__import__("time").time, sleep=lambda _: None)
    monkeypatch.setattr(vpn, "time", clock)
    monkeypatch.setattr(diagnostics, "time", clock)
    yield
    CURRENT.pop()
