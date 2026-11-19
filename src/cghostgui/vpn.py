"""Control of the OpenVPN connection through NetworkManager."""
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

from cghostgui import proc
from cghostgui.errors import AuthRejected, CgError
from cghostgui.paths import CONNECTION

WAIT_SECONDS = 40


class LogMark(NamedTuple):
    """Position in the system journal."""

    cursor: str
    when: float


def nm(*args: str, timeout: int = 30) -> str:
    """Run nmcli.

    Args:
        *args: Arguments.
        timeout: Limit in seconds.

    Returns:
        Standard output.

    Raises:
        CgError: nmcli failed.
    """
    result = proc.run(["nmcli", *args], timeout)
    if result.code:
        text = (result.err or result.out).strip()
        raise CgError(text.splitlines()[-1] if text else f"nmcli: Exit {result.code}")
    return result.out


def profile_exists() -> bool:
    """Tell whether the profile exists.

    Returns:
        True if NetworkManager knows it.
    """
    result = proc.run(["nmcli", "-t", "-f", "NAME", "connection", "show"], 10)
    return result.code == 0 and CONNECTION in result.out.splitlines()


def state() -> str:
    """Return the state of the connection.

    Returns:
        ``activated``, ``activating``, ``deactivating`` or an empty text.
    """
    result = proc.run(["nmcli", "-g", "GENERAL.STATE", "connection", "show", CONNECTION], 10)
    return result.out.strip() if result.code == 0 else ""


def is_active() -> bool:
    """Tell whether the connection is up or coming up.

    Returns:
        True if so.
    """
    return state() in ("activated", "activating")


def current_remote() -> str | None:
    """Return the configured remote host.

    Returns:
        Host name, or None if unknown.
    """
    result = proc.run(["nmcli", "-g", "vpn.data", "connection", "show", CONNECTION], 10)
    match = re.search(r"(?:^|[ ,])remote = ([^,\s]+)", result.out) if result.code == 0 else None
    return match.group(1) if match else None


def tunnel_device() -> str | None:
    """Return the network device of the tunnel.

    Returns:
        Device name, or None without a tunnel.
    """
    result = proc.run(["nmcli", "-g", "GENERAL.IP-IFACE", "connection", "show", CONNECTION], 5)
    device = result.out.strip() if result.code == 0 else ""
    return device if device and Path("/sys/class/net", device).exists() else None


def set_username(username: str) -> None:
    """Store the OpenVPN user name in the profile.

    Args:
        username: User name.
    """
    nm("connection", "modify", CONNECTION, "+vpn.data", f"username={username.strip()}")


def resolves(host: str) -> bool:
    """Tell whether a host name resolves.

    Args:
        host: Host name.

    Returns:
        True if an address was found.
    """
    try:
        return bool(socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP))
    except OSError:
        return False


def set_target(host: str, port: int, proto: str) -> None:
    """Point the profile at a server.

    Args:
        host: Remote host.
        port: Remote port.
        proto: ``udp`` or ``tcp``.
    """
    nm("connection", "modify", CONNECTION, "+vpn.data", f"remote={host}",
       "+vpn.data", f"port={port}", "+vpn.data", f"proto-tcp={'yes' if proto == 'tcp' else 'no'}")


def log_mark() -> LogMark:
    """Remember the current end of the OpenVPN log.

    Returns:
        Position for :func:`vpn_log`.
    """
    result = proc.run(["journalctl", "-t", "nm-openvpn", "-n", "1", "--show-cursor",
                       "--no-pager", "-o", "cat"], 5)
    match = re.search(r"^-- cursor: (.+)$", result.out, re.M) if result.code == 0 else None
    return LogMark(match.group(1) if match else "", time.time())


def vpn_log(mark: LogMark, lines: int = 25) -> str:
    """Return the OpenVPN log lines after a position.

    Args:
        mark: Position.
        lines: Maximum number of lines.

    Returns:
        Log text.
    """
    where = ["--after-cursor", mark.cursor] if mark.cursor else ["--since", f"@{int(mark.when)}"]
    result = proc.run(["journalctl", "-t", "nm-openvpn", *where, "--no-pager", "-o", "cat"], 5)
    return "\n".join(result.out.splitlines()[-lines:]) if result.code == 0 else ""


def disconnect() -> None:
    """Take the connection down if it is up."""
    if is_active():
        nm("connection", "down", CONNECTION)


def _watch(process: subprocess.Popen[str], mark: LogMark) -> tuple[int, str]:
    """Wait for nmcli and stop as soon as the server rejects the login.

    Args:
        process: Running nmcli.
        mark: Log position before the start.

    Returns:
        Exit code and output of nmcli.

    Raises:
        AuthRejected: The server answered AUTH_FAILED.
    """
    deadline = time.time() + WAIT_SECONDS + 5
    while process.poll() is None and time.time() < deadline:
        time.sleep(0.5)
        if "AUTH_FAILED" in vpn_log(mark):
            # Stopping here prevents the desktop from asking again and again.
            process.terminate()
            process.communicate(timeout=5)
            disconnect()
            raise AuthRejected("Der Server lehnt Benutzername oder Passwort ab (AUTH_FAILED)")
    if process.poll() is None:
        process.terminate()
    output = process.communicate(timeout=5)[0]
    return process.returncode, output


def connect(password: str) -> None:
    """Bring the connection up.

    Args:
        password: OpenVPN password; handed over in a private temporary file.

    Raises:
        CgError: The connection could not be established.
    """
    password = password.strip()
    if not password or "\n" in password:
        raise CgError("Ungültiges Passwort")
    mark = log_mark()
    descriptor, name = tempfile.mkstemp(prefix="cghost-",
                                        dir=os.environ.get("XDG_RUNTIME_DIR") or None)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"vpn.secrets.password:{password}\n")
        with subprocess.Popen(["nmcli", "-w", str(WAIT_SECONDS), "connection", "up", CONNECTION,
                               "passwd-file", name], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True) as process:
            code, output = _watch(process, mark)
    finally:
        os.unlink(name)
    if code:
        disconnect()
        lines = [line for line in output.strip().splitlines() if not line.startswith("Warning")]
        text = lines[-1] if lines else f"Exit {code}"
        if "Timeout" in text or code < 0:
            text = f"Keine Verbindung nach {WAIT_SECONDS} s"
        raise CgError(text)
