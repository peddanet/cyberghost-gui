"""Text of the indicator, independent of the toolkit."""
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cghostgui import diagnostics, proc, vpn

BARS = "▁▂▃▄▅▆▇█"
INTERVAL = 2
ICONS = {"activated": "channel-secure-symbolic", "activating": "network-vpn-acquiring-symbolic"}
ICON_OFF = "channel-insecure-symbolic"
KEYS = ("state", "target", "geo", "server", "ip", "org", "since", "down", "up", "ipv6")
LABEL_GUIDE = "CyberGhost VPN Switzerland"


def human_size(amount: float) -> str:
    """Format a number of bytes.

    Args:
        amount: Bytes.

    Returns:
        Text with unit.
    """
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1000:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1000
    return f"{amount:.1f} TB"


def spark(values: Any) -> str:
    """Draw values as a line of bars.

    Args:
        values: Numbers.

    Returns:
        One character per value.
    """
    numbers = list(values)
    peak = max(numbers, default=0)
    return "".join(BARS[int(v / peak * (len(BARS) - 1))] if peak else BARS[0] for v in numbers)


def uptime() -> str:
    """Return how long the OpenVPN process has been running.

    Returns:
        ``HH:MM:SS`` or ``?``.
    """
    result = proc.run(["ps", "-C", "openvpn", "-o", "etimes="], 3)
    ages = [int(word) for word in result.out.split() if word.isdigit()] if result.code == 0 else []
    if not ages:
        return "?"
    seconds = min(ages)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


@dataclass
class Traffic:
    """Byte counters of the tunnel.

    Attributes:
        down: Recent download rates.
        up: Recent upload rates.
        last: Previous counter values.
    """

    down: deque[float] = field(default_factory=lambda: deque(maxlen=16))
    up: deque[float] = field(default_factory=lambda: deque(maxlen=16))
    last: tuple[int, int] | None = None

    def reset(self) -> None:
        """Forget all values."""
        self.down.clear()
        self.up.clear()
        self.last = None

    def sample(self, device: str | None) -> tuple[int, int] | None:
        """Read the counters and update the rates.

        Args:
            device: Tunnel device.

        Returns:
            Received and sent bytes, or None without a device.
        """
        folder = Path("/sys/class/net", device or "-", "statistics")
        try:
            now = (int((folder / "rx_bytes").read_text(encoding="ascii")),
                   int((folder / "tx_bytes").read_text(encoding="ascii")))
        except OSError:
            self.last = None
            return None
        if self.last and now >= self.last:
            self.down.append((now[0] - self.last[0]) / INTERVAL)
            self.up.append((now[1] - self.last[1]) / INTERVAL)
        self.last = now
        return now


@dataclass(frozen=True)
class View:
    """Everything the indicator shows.

    Attributes:
        icon: Icon name.
        label: Text in the panel.
        lines: Menu lines by key; empty lines are hidden.
        connected: True while a tunnel is up or coming up.
    """

    icon: str
    label: str
    lines: dict[str, str]
    connected: bool


def _rate(values: deque[float]) -> str:
    """Format the newest rate.

    Args:
        values: Rates.

    Returns:
        Text.
    """
    return human_size(values[-1] if values else 0) + "/s"


def connected_view(remote: str | None, info: dict[str, Any] | None, traffic: Traffic) -> View:
    """Build the view of an established connection.

    Args:
        remote: Remote host.
        info: Public address data, None until known.
        traffic: Byte counters.

    Returns:
        View.
    """
    label = diagnostics.target_label(remote)
    warning = diagnostics.location_warning(info, remote)
    device = vpn.tunnel_device()
    total = traffic.sample(device)
    data = info or {}
    lines = {
        "state": "CyberGhost VPN: verbunden",
        "target": f"Ziel: {label}",
        "geo": f"⚠ {warning}" if warning else "",
        "server": f"Server: {remote}",
        "ip": f"Öffentliche IP: {data.get('ip', 'wird ermittelt …')}",
        "org": (f"Sichtbar als: {data.get('country', '?')} · {data.get('city', '?')} · "
                f"{data.get('org', '?')}") if data else "",
        "since": f"Verbunden seit: {uptime()}",
        "down": (f"↓ {_rate(traffic.down)}  {spark(traffic.down)}  "
                 f"gesamt {human_size(total[0])}") if total else "",
        "up": (f"↑ {_rate(traffic.up)}  {spark(traffic.up)}  "
               f"gesamt {human_size(total[1])}") if total else "",
        "ipv6": f"IPv6: {diagnostics.ipv6_path(device)}",
    }
    panel = f"CyberGhost VPN {label.split(' · ', maxsplit=1)[0]}{' ⚠' if warning else ''}"
    return View(ICONS["activated"], panel, lines, True)


def idle_view(state: str, remote: str | None) -> View:
    """Build the view without an established connection.

    Args:
        state: Connection state.
        remote: Remote host.

    Returns:
        View.
    """
    lines = dict.fromkeys(KEYS, "")
    if state == "activating":
        lines["state"] = f"Verbindungsaufbau: {remote}"
        return View(ICONS["activating"], "CyberGhost VPN …", lines, True)
    lines["state"] = "Nicht verbunden"
    return View(ICON_OFF, "CyberGhost VPN aus", lines, False)
