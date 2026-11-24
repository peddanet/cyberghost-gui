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


def test_identities_are_scanned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Names and addresses of authors, committers and taggers count as text.

    Args:
        tmp_path: Temporary folder.
        capsys: Output capture.
    """
    repo = repository(tmp_path)
    subprocess.run(["git", "-C", repo, "-c", "user.name=Box Owner",
                    "-c", "user.email=owner@hostbox.example", "tag", "-a", "v1", "-m", "v1"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "-c", "user.name=Box Owner",
                    "-c", "user.email=owner@hostbox.example", "commit", "--amend", "-q",
                    "--no-edit"], check=True, capture_output=True)
    assert scanner().PrivacyScan(repo, ["hostbox"]).run() == 1
    output = capsys.readouterr().out
    assert "committer:1: hostbox" in output and "tag v1 tagger:1: hostbox" in output
    assert "author:1: hostbox" not in output


def test_config_folder_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The list in the configuration folder of the XDG layout counts.

    Args:
        tmp_path: Temporary folder.
        monkeypatch: Patch helper.
    """
    module = scanner()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "conf"))
    folder = tmp_path / "conf/cyberghost-gui/privacy"
    folder.mkdir(parents=True)
    (folder / "denylist.txt").write_text("three\n", encoding="utf-8")
    assert module.PrivacyScan.read_list("deny") == ["three"]
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert module.PrivacyScan.list_folders()[0] == str(tmp_path / ".config/cyberghost-gui/privacy")
