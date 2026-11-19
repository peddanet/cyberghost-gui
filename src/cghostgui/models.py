"""Plain data records."""
import re
from dataclasses import dataclass

from cghostgui.paths import DOMAIN


@dataclass(frozen=True)
class City:
    """A city of the server list.

    Attributes:
        name: City name.
        servers: Number of servers.
        usage: Average utilisation in percent.
    """

    name: str
    servers: int
    usage: int


@dataclass(frozen=True)
class Server:
    """One server of a city.

    Attributes:
        name: Host label below the VPN domain.
        usage: Utilisation in percent.
    """

    name: str
    usage: int


@dataclass(frozen=True)
class Template:
    """Connection values of the imported configuration.

    Attributes:
        host: Remote host.
        port: Remote port.
        proto: ``udp`` or ``tcp``.
    """

    host: str
    port: int
    proto: str

    @property
    def group(self) -> str | None:
        """Return the server group of the host.

        Returns:
            Group such as ``87-1``, or None for another host form.
        """
        match = re.fullmatch(r"(\d+-\d+)-[a-z]{2}\." + re.escape(DOMAIN), self.host)
        return match.group(1) if match else None
