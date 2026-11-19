"""Tests of the privacy gate."""
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent


def scanner() -> Any:
    """Import the scan script.

    Returns:
        Module.
    """
    spec = importlib.util.spec_from_file_location("privacy_scan", ROOT / "tools/privacy_scan.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repository(path: Path) -> str:
    """Create a small repository.

    Args:
        path: Folder.

    Returns:
        Its path.
    """
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@e",
                        *args], check=True, capture_output=True)
    git("init", "-q")
    (path / "a.txt").write_text("the secretword here\nsea level\n", encoding="utf-8")
    (path / "b.bin").write_bytes(b"\0secretword")
    git("add", ".")
    git("commit", "-qm", "first")
    return str(path)


def test_finds_terms(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Listed terms are reported, binary files skipped.

    Args:
        tmp_path: Temporary folder.
        capsys: Output capture.
    """
    scan = scanner().PrivacyScan(repository(tmp_path), ["secretword", "x"])
    assert scan.run() == 1
    output = capsys.readouterr().out
    assert "a.txt:1: secretword" in output and "b.bin" not in output


def test_allowed_phrase_and_clean(tmp_path: Path) -> None:
    """An allowed phrase hides its term.

    Args:
        tmp_path: Temporary folder.
    """
    assert scanner().PrivacyScan(repository(tmp_path), ["level"], ["sea level"]).run() == 0


def test_lists_are_combined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All local deny lists count; comments are ignored.

    Args:
        tmp_path: Temporary folder.
        monkeypatch: Patch helper.
    """
    module = scanner()
    monkeypatch.setenv("HOME", str(tmp_path))
    for folder in (tmp_path / "app/privacy", tmp_path / ".config/mediatools/privacy"):
        folder.mkdir(parents=True)
    (tmp_path / "app/privacy/denylist.txt").write_text("one # note\n\n", encoding="utf-8")
    (tmp_path / ".config/mediatools/privacy/denylist.txt").write_text("two\n", encoding="utf-8")
    assert module.PrivacyScan.read_list("deny") == ["one", "two"]
    assert module.PrivacyScan.read_list("allow") == []


def test_require_fails_without_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Publishing steps refuse to run without a deny list.

    Args:
        tmp_path: Temporary folder.
        monkeypatch: Patch helper.
    """
    module = scanner()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["scan", "--require"])
    assert module.main() == 2
    monkeypatch.setattr(sys, "argv", ["scan"])
    assert module.main() == 0
