"""Choice of the server and the connection sequence."""
from dataclasses import dataclass

from cghostgui import diagnostics, paths, store, vpn
from cghostgui.catalog import Catalog
from cghostgui.errors import CgError
from cghostgui.models import Template


@dataclass(frozen=True)
class Target:
    """What the user selected.

    Attributes:
        code: Country code.
        service: Streaming service or None.
        city: City, empty for automatic.
        server: Server, empty for automatic.
        proto: ``udp`` or ``tcp``.
        label: Readable name of the target.
    """

    code: str
    service: str | None
    city: str
    server: str
    proto: str
    label: str


def pick_host(catalog: Catalog, target: Target, template: Template) -> str:
    """Determine the host to connect to.

    Args:
        catalog: Server lists.
        target: Selection.
        template: Imported configuration.

    Returns:
        Host name.

    Raises:
        CgError: No server is available.
    """
    if target.server:
        return f"{target.server}.{paths.DOMAIN}"
    city = target.city
    if not city and not target.service and template.group and target.proto == template.proto:
        return f"{template.group}-{target.code.lower()}.{paths.DOMAIN}"
    if not city:
        cities = catalog.cities(target.code, target.service)
        if not cities:
            raise CgError("Keine Stadt verfügbar")
        city = min(cities, key=lambda item: item.usage).name
    servers = catalog.servers(target.code, city, target.service)
    if not servers:
        raise CgError(f"Kein Server in {city}")
    return f"{servers[0].name}.{paths.DOMAIN}"


def switch(catalog: Catalog, target: Target, template: Template, password: str) -> str:
    """Connect to a target; a running tunnel stays up until the host is known to resolve.

    Args:
        catalog: Server lists.
        target: Selection.
        template: Imported configuration.
        password: OpenVPN password.

    Returns:
        The host now connected.

    Raises:
        CgError: The host does not resolve or the connection failed.
    """
    host = pick_host(catalog, target, template)
    if not vpn.resolves(host):
        raise CgError(f"Serveradresse nicht auflösbar: {host}")
    vpn.disconnect()
    vpn.set_target(host, template.port, target.proto)
    settings = store.read_settings()
    settings.update(target_host=host, target_label=target.label, target_cc=target.code)
    store.write_settings(settings)
    mark = vpn.log_mark()
    try:
        vpn.connect(password)
    except CgError as error:
        if type(error) is not CgError:  # pylint: disable=unidiomatic-typecheck
            raise
        detail = vpn.vpn_log(mark)
        raise CgError(f"{error} (VPN ist getrennt)" + (f"\n{detail}" if detail else "")) from error
    diagnostics.wait_ipv6_block()
    return host
