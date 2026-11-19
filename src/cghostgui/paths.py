"""Names and locations used by the application."""
import getpass
import os
from pathlib import Path

CONNECTION = "CyberGhost-GUI"
DOMAIN = "cg-dialup.net"
APP_ID = "local.cghostgui.Switcher"
APP_PATH = "/local/cghostgui/Switcher"


def app_dir() -> Path:
    """Return the data folder of the application.

    Returns:
        ``$CGHOST_GUI_HOME`` or ``~/scripts/cyberghost-gui``.
    """
    return Path(os.environ.get("CGHOST_GUI_HOME") or Path.home() / "scripts" / "cyberghost-gui")


def vendor_binary() -> Path:
    """Return the location of the official command-line program.

    Returns:
        Path below the data folder.
    """
    return app_dir() / "vendor" / "cyberghostvpn"


def vendor_home() -> Path:
    """Return the folder the official program uses; it cannot be changed.

    Returns:
        ``/home/<user>/.cyberghost``.
    """
    return Path("/home") / getpass.getuser() / ".cyberghost"


def profile_dir() -> Path:
    """Return the folder of the imported OpenVPN configuration.

    Returns:
        Path below the data folder.
    """
    return app_dir() / "profile"


def cache_dir() -> Path:
    """Return the folder of the cached server lists.

    Returns:
        Path below the data folder.
    """
    return app_dir() / "cache"


def settings_file() -> Path:
    """Return the settings file.

    Returns:
        Path below the data folder.
    """
    return app_dir() / "settings.json"
