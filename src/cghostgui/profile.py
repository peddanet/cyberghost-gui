"""The imported OpenVPN configuration and its NetworkManager profile."""
import os
import re
import zipfile
from pathlib import Path

from cghostgui import paths, store, vpn
from cghostgui.errors import CgError
from cghostgui.models import Template

REQUIRED = {"openvpn.ovpn", "ca.crt", "client.crt", "client.key"}
MAX_SIZE = 1 << 20


def read_template() -> Template | None:
    """Read the connection values of the imported configuration.

    Returns:
        The values, or None if nothing usable was imported.
    """
    source = paths.profile_dir() / "openvpn.ovpn"
    if not source.exists():
        return None
    host, port, proto = None, 443, "udp"
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        words = line.split()
        if len(words) >= 2 and words[0] == "remote":
            host = words[1].lower()
            if len(words) >= 3 and words[2].isdigit():
                port = int(words[2])
            if len(words) >= 4:
                proto = words[3][:3].lower()
        elif len(words) >= 2 and words[0] == "proto":
            proto = words[1][:3].lower()
    return Template(host, port, proto) if host else None


def _read_archive(archive: str) -> dict[str, bytes]:
    """Read the needed files of a configuration archive.

    Paths inside the archive are ignored, only the base name counts.

    Args:
        archive: ZIP file.

    Returns:
        Contents by file name.

    Raises:
        CgError: The archive is unreadable or incomplete.
    """
    wanted: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                name = Path(info.filename).name
                if name in REQUIRED and info.file_size < MAX_SIZE:
                    wanted[name] = bundle.read(info)
    except (OSError, zipfile.BadZipFile) as error:
        raise CgError(f"ZIP nicht lesbar: {error}") from error
    missing = REQUIRED - set(wanted)
    if missing:
        raise CgError("Im ZIP fehlt: " + ", ".join(sorted(missing)))
    return wanted


def import_zip(archive: str, username: str) -> Template:
    """Install a configuration archive as NetworkManager profile.

    Args:
        archive: ZIP file from the manual device setup of the account.
        username: OpenVPN user name of that configuration.

    Returns:
        Values of the imported configuration.

    Raises:
        CgError: The archive or the import failed.
    """
    contents = _read_archive(archive)
    folder = store.private_dir(paths.profile_dir())
    for name, data in contents.items():
        target = folder / name
        target.unlink(missing_ok=True)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    vpn.disconnect()
    if vpn.profile_exists():
        vpn.nm("connection", "delete", paths.CONNECTION)
    output = vpn.nm("connection", "import", "type", "openvpn", "file",
                    str(folder / "openvpn.ovpn"))
    match = re.search(r"\(([0-9a-f-]{36})\)", output)
    if not match:
        raise CgError("Import lieferte keine Verbindungs-ID")
    vpn.nm("connection", "modify", match.group(1), "connection.id", paths.CONNECTION,
           "connection.autoconnect", "no", "+vpn.data", f"username={username.strip()}",
           "+vpn.data", "password-flags=2", "+vpn.data", "cert-pass-flags=4",
           "+vpn.data", "connection-type=password-tls")
    template = read_template()
    if template is None:
        raise CgError("Die Konfiguration enthält keinen Server")
    return template
