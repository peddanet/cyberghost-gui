"""Private folders and the settings file."""
import json
from pathlib import Path
from typing import Any

from cghostgui import paths


def private_dir(path: Path) -> Path:
    """Create a folder only the user can enter.

    Args:
        path: Folder.

    Returns:
        The same path.
    """
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def read_settings() -> dict[str, Any]:
    """Read the settings.

    Returns:
        Settings, empty if the file is missing or damaged.
    """
    try:
        data = json.loads(paths.settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_settings(data: dict[str, Any]) -> None:
    """Write the settings, readable by the user only.

    Args:
        data: Settings.
    """
    private_dir(paths.app_dir())
    target = paths.settings_file()
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    target.chmod(0o600)
