"""Names and locations used by the application.

Folders follow the XDG base directory layout: ``<base>/cyberghost-gui/``.
"""
import getpass
import os
from pathlib import Path

NAME = "cyberghost-gui"
CONNECTION = "CyberGhost-GUI"
DOMAIN = "cg-dialup.net"
APP_ID = "local.cghostgui.Switcher"
APP_PATH = "/local/cghostgui/Switcher"


def _base(variable: str, default: str) -> Path:
    """Return an XDG base folder.

    Args:
        variable: Name of the environment variable, for example ``XDG_CONFIG_HOME``.
        default: Folder below the home directory used when the variable is unset,
            empty or not an absolute path.

    Returns:
        The base folder.
    """
    value = os.environ.get(variable, "")
    return Path(value) if os.path.isabs(value) else Path.home() / default


def config_dir() -> Path:
    """Return the folder of settings, imported configuration and privacy lists.

    Returns:
        ``$XDG_CONFIG_HOME/cyberghost-gui``, default ``~/.config/cyberghost-gui``.
    """
    return _base("XDG_CONFIG_HOME", ".config") / NAME


def data_dir() -> Path:
    """Return the folder of the installed program and the official program.

    Returns:
        ``$XDG_DATA_HOME/cyberghost-gui``, default ``~/.local/share/cyberghost-gui``.
    """
    return _base("XDG_DATA_HOME", ".local/share") / NAME


def cache_dir() -> Path:
    """Return the folder of the cached server lists; it may be deleted at any time.

    Returns:
        ``$XDG_CACHE_HOME/cyberghost-gui``, default ``~/.cache/cyberghost-gui``.
    """
    return _base("XDG_CACHE_HOME", ".cache") / NAME


def legacy_dir() -> Path:
    """Return the single data folder used up to release 0.5.1.

    Returns:
        ``$CGHOST_GUI_HOME`` or ``~/scripts/cyberghost-gui``.
    """
    return Path(os.environ.get("CGHOST_GUI_HOME") or Path.home() / "scripts" / NAME)


def vendor_binary() -> Path:
    """Return the location of the official command-line program.

    Returns:
        Path below the data folder.
    """
    return data_dir() / "vendor" / "cyberghostvpn"


def vendor_home() -> Path:
    """Return the folder the official program uses; it cannot be changed.

    Returns:
        ``/home/<user>/.cyberghost``.
    """
    return Path("/home") / getpass.getuser() / ".cyberghost"


def profile_dir() -> Path:
    """Return the folder of the imported OpenVPN configuration.

    Returns:
        Path below the configuration folder.
    """
    return config_dir() / "profile"


def settings_file() -> Path:
    """Return the settings file.

    Returns:
        Path below the configuration folder.
    """
    return config_dir() / "settings.json"
