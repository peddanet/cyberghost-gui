# cyberghost-gui

A small GTK desktop application for Linux that switches the country, city,
server and streaming target of a CyberGhost OpenVPN connection without creating
a new device configuration for every target.

**Unofficial project.** It is not affiliated with or endorsed by CyberGhost.
You need your own subscription. The repository contains no CyberGhost program,
certificate, key or configuration.

## What it does

* Selects country, city, server, streaming service and UDP or TCP.
* Runs the tunnel through NetworkManager, so the desktop shows it as a normal VPN.
* Shows a panel indicator with target, public address, traffic and IPv6 state.
* Blocks public IPv6 while connected, because the service tunnels IPv4 only.
* Warns when the chosen country differs from the country reported for the exit
  address, which can happen with virtual server locations.
* Keeps passwords in the desktop key ring.

There is no kill switch: while switching targets or after a connection loss,
traffic leaves directly.

## Requirements

* Ubuntu 24.04 or newer, or a derivative, with NetworkManager
* Python 3.12 or newer
* The official Linux application archive `cyberghostvpn-ubuntu-*.zip`; only its
  read-only list functions are used, its installer is not run
* A manual device configuration (ZIP) from your CyberGhost account
* For the indicator on GNOME: the extension `ubuntu-appindicators@ubuntu.com`

## Install

~~~bash
git clone https://github.com/OWNER/cyberghost-gui.git
cd cyberghost-gui
./install.sh ~/Downloads/cyberghostvpn-ubuntu-22.04-1.5.0.zip
~~~

Run it as a normal user. See [docs/user-guide.md](docs/user-guide.md) for the
first start and [docs/developer.md](docs/developer.md) for the architecture.

## License

MIT, see [LICENSE](LICENSE).
