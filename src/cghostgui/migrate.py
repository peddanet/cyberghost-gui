"""One-time move from the single folder of release 0.5.1 to the XDG layout.

Up to release 0.5.1 everything lived in ``~/scripts/cyberghost-gui``. Since then

* settings, imported configuration and privacy lists live in ``~/.config/cyberghost-gui``,
* the official program lives in ``~/.local/share/cyberghost-gui/vendor``,
* the server lists live in ``~/.cache/cyberghost-gui``.

The move never overwrites: an existing target keeps its content and the old file
stays where it is. Every move is reported. The files of the imported configuration
are referenced by the NetworkManager profile; they are copied first, the profile is
pointed at the copies, and the old files are removed only while the VPN is down
(otherwise on a later run). Emptied folders are removed; what remains is reported.

Run as a normal user: ``python -m cghostgui.migrate``.
"""
import filecmp
import re
import shutil
import sys
from pathlib import Path

from cghostgui import paths, proc, store, vpn
from cghostgui.errors import CgError

PLAIN = (("settings.json", paths.settings_file),
         ("privacy", lambda: paths.config_dir() / "privacy"),
         ("vendor", lambda: paths.data_dir() / "vendor"),
         ("cache", paths.cache_dir))


def _move(source: Path, target: Path, report: list[str]) -> None:
    """Move a file, or the files of a folder, without overwriting anything.

    Args:
        source: Old file or folder.
        target: New file or folder.
        report: Collects one line per action.
    """
    if source.is_dir() and not source.is_symlink():
        for child in sorted(source.iterdir()):
            _move(child, target / child.name, report)
        _remove_if_empty(source)
        return
    if target.exists() or target.is_symlink():
        report.append(f"bleibt (Ziel existiert schon): {source}")
        return
    store.private_dir(target.parent)
    shutil.move(str(source), str(target))
    report.append(f"verschoben: {source} -> {target}")


def _remove_if_empty(folder: Path) -> None:
    """Remove a folder if it is empty.

    Args:
        folder: Folder.
    """
    try:
        folder.rmdir()
    except OSError:
        pass


def _profile_references(old: Path) -> dict[str, str]:
    """Find the entries of the NetworkManager profile that point into a folder.

    Args:
        old: Folder of the old configuration.

    Returns:
        Entry name (for example ``ca``) and file path, for every entry below ``old``.
    """
    result = proc.run(["nmcli", "-g", "vpn.data", "connection", "show", paths.CONNECTION], 10)
    if result.code:
        return {}
    prefix = re.escape(str(old) + "/")
    return dict(re.findall(r"(?:^|[ ,])([\w-]+) = (" + prefix + r"[^,\s]+)", result.out))


def _move_profile(old: Path, report: list[str]) -> None:
    """Copy the imported configuration and point the profile at the copies.

    Args:
        old: Folder of the old configuration.
        report: Collects one line per action.
    """
    new = store.private_dir(paths.profile_dir())
    for source in sorted(p for p in old.iterdir() if p.is_file()):
        target = new / source.name
        if not target.exists():
            shutil.copy2(source, target)
            target.chmod(0o600)
            report.append(f"kopiert: {source} -> {target}")
        elif not filecmp.cmp(source, target, shallow=False):
            report.append(f"bleibt (Ziel ist verschieden): {source}")
    changes: list[str] = []
    for name, value in _profile_references(old).items():
        target = new / Path(value).name
        if target.exists():
            changes += ["+vpn.data", f"{name}={target}"]
    if changes:
        try:
            vpn.nm("connection", "modify", paths.CONNECTION, *changes)
        except CgError as error:
            report.append(f"Profil nicht angepasst ({error}); alte Dateien bleiben")
            return
        report.append(f"NetworkManager-Profil zeigt jetzt auf {new}")
    if _profile_references(old):
        report.append(f"alte Konfiguration bleibt: das Profil verweist noch auf {old}")
        return
    if vpn.is_active():
        report.append(f"alte Konfiguration bleibt bis nach dem Trennen der VPN: {old}")
        return
    for source in sorted(p for p in old.iterdir() if p.is_file()):
        target = new / source.name
        if target.exists() and filecmp.cmp(source, target, shallow=False):
            source.unlink()
    _remove_if_empty(old)
    if not old.exists():
        report.append(f"entfernt (nach {new} kopiert): {old}")


def migrate() -> list[str]:
    """Move the files of the old layout.

    Returns:
        One line per action; empty if there was nothing to do.
    """
    old = paths.legacy_dir()
    report: list[str] = []
    if not old.is_dir():
        return report
    for name, target in PLAIN:
        source = old / name
        if source.exists() or source.is_symlink():
            _move(source, target(), report)
    if (old / "profile").is_dir():
        _move_profile(old / "profile", report)
    _remove_if_empty(old)
    if old.exists():
        rest = ", ".join(sorted(p.name for p in old.iterdir()))
        report.append(f"im alten Ordner {old} verbleibt: {rest}")
    return report


def main() -> int:
    """Run the move and print what was done.

    Returns:
        0.
    """
    for line in migrate():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
