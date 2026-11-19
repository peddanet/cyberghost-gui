"""What the outside world and the routing table say about the connection."""
import json
import re
import shutil
import time
from typing import Any

from cghostgui import paths, proc, store, vpn

IPV6_PROBE = "2606:4700:4700::1111"
BYPASS = "vorbei über"


def public_info() -> dict[str, Any] | None:
    """Ask an external service how this computer appears.

    Returns:
        Address data, or None if unavailable.
    """
    result = proc.run(["curl", "-fsS", "--max-time", "12", "https://ipinfo.io/json"], 15)
    try:
        data = json.loads(result.out) if result.code == 0 else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def ipv6_path(tunnel: str | None) -> str:
    """Describe the way IPv6 traffic to the internet would take.

    Args:
        tunnel: Tunnel device.

    Returns:
        Text for the user.
    """
    result = proc.run(["ip", "-6", "route", "get", IPV6_PROBE], 3)
    match = re.search(r"\bdev (\S+)", result.out) if result.code == 0 else None
    if not match or result.out.startswith(("unreachable", "blackhole", "prohibit")):
        return "gesperrt, kein Weg am Tunnel vorbei"
    return "im Tunnel" if match.group(1) == tunnel else f"am Tunnel {BYPASS} {match.group(1)}"


def wait_ipv6_block(seconds: float = 4) -> None:
    """Wait for the block that NetworkManager sets shortly after connecting.

    Args:
        seconds: Maximum waiting time.
    """
    end = time.time() + seconds
    while time.time() < end and BYPASS in ipv6_path(vpn.tunnel_device()):
        time.sleep(0.25)


def _code_of_host(remote: str | None) -> str:
    """Extract the country code of a group address.

    Args:
        remote: Host name.

    Returns:
        Lower-case code, or an empty text.
    """
    match = re.search(r"-([a-z]{2})\." + re.escape(paths.DOMAIN) + "$", remote or "")
    return match.group(1) if match else ""


def country_name(code: str) -> str:
    """Translate a country code with the cached country list.

    Args:
        code: Upper-case code.

    Returns:
        Country name, or the code if it is unknown.
    """
    try:
        rows = json.loads((paths.cache_dir() / "countries.json").read_text(encoding="utf-8"))
        return dict(rows).get(code, code)
    except (OSError, ValueError, TypeError):
        return code


def target_label(remote: str | None) -> str:
    """Return a readable name of the connected target.

    Args:
        remote: Host name.

    Returns:
        Label such as a country name.
    """
    settings = store.read_settings()
    if remote and settings.get("target_host") == remote and settings.get("target_label"):
        return str(settings["target_label"])
    code = _code_of_host(remote)
    return country_name(code.upper()) if code else remote or "?"


def expected_country(remote: str | None) -> str:
    """Return the country the user chose.

    Args:
        remote: Host name.

    Returns:
        Upper-case code, or an empty text if unknown.
    """
    settings = store.read_settings()
    if remote and settings.get("target_host") == remote and settings.get("target_cc"):
        return str(settings["target_cc"]).upper()
    return _code_of_host(remote).upper()


def location_warning(info: dict[str, Any] | None, remote: str | None) -> str:
    """Compare the chosen country with the reported one.

    Args:
        info: Result of :func:`public_info`.
        remote: Host name.

    Returns:
        Warning text, empty if they agree or a value is unknown.
    """
    wanted = expected_country(remote)
    seen = str((info or {}).get("country", "")).upper()
    if not wanted or not seen or wanted == seen:
        return ""

    def show(code: str) -> str:
        """Format a country for the warning.

        Args:
            code: Country code.

        Returns:
            Name and code, or the code alone.
        """
        name = country_name(code)
        return f"{name} ({code})" if name != code else code

    return f"Gewählt: {show(wanted)} · gemeldet: {show(seen)} · virtueller Standort möglich"


def check(lan_target: str = "") -> list[str]:
    """Collect the outside view of the connection.

    Args:
        lan_target: Address in the home network to ping, may be empty.

    Returns:
        Lines for the user.
    """
    info = public_info()
    lines = [(f"Öffentlich: {info.get('ip')} · {info.get('country')} · {info.get('city')} · "
              f"{info.get('org', '')}") if info else "Öffentliche IP: nicht ermittelbar"]
    if vpn.state() == "activated":
        warning = location_warning(info, vpn.current_remote())
        if warning:
            lines.append(f"WARNUNG {warning}")
    result = proc.run(["curl", "-6", "-fsS", "--max-time", "6", "https://api6.ipify.org"], 9)
    lines.append(f"WARNUNG IPv6 sichtbar: {result.out.strip()} (am Tunnel vorbei?)"
                 if result.code == 0 and result.out.strip()
                 else "IPv6: von außen keine Adresse sichtbar")
    if lan_target:
        reached = proc.run(["ping", "-c", "1", "-W", "2", lan_target], 5).code == 0
        lines.append(f"Heimnetz {lan_target}: {'erreichbar' if reached else 'NICHT erreichbar'}")
    return lines


def missing_tools() -> list[str]:
    """List required programs that are not installed.

    Returns:
        Program names.
    """
    return [tool for tool in ("nmcli", "openvpn", "curl", "secret-tool")
            if not shutil.which(tool)]
