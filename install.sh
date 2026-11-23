#!/usr/bin/env bash
# install.sh - install this checkout for the current user and switch a running
# application to it. The VPN connection stays up.
#
#   ${CGHOST_GUI_HOME:-~/scripts/cyberghost-gui}    data, venv and official program
#
# Usage: ./install.sh [--no-apt] [--no-start] [PATH-TO-OFFICIAL-APP.zip]
#
# Run as a normal user. sudo is used only for system packages and for the
# NetworkManager rule that blocks public IPv6 while the VPN is connected.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CGHOST_GUI_HOME:-$HOME/scripts/cyberghost-gui}"
RULE=/etc/NetworkManager/dispatcher.d/90-cyberghost-gui-ipv6
APT=1; START=1; ZIP=""
for arg in "$@"; do
    case "$arg" in
        --no-apt) APT=0 ;;
        --no-start) START=0 ;;
        *) ZIP="$arg" ;;
    esac
done
[ "$(id -u)" -ne 0 ] || { echo "run as a normal user, not as root" >&2; exit 1; }

if (( APT )); then
    echo "[1/6] system packages (sudo)"
    sudo apt-get install -y network-manager-openvpn openvpn python3-venv python3-gi \
        gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
        libsecret-tools libglib2.0-bin unzip curl
fi

echo "[2/6] folders: $DEST"
install -d -m 700 "$DEST" "$DEST/vendor"
for old in cghost_core.py cghost_gui.py cghost_tray.py install.sh 90-cyberghost-gui-ipv6; do
    if [ -f "$DEST/$old" ] && [ "$DEST" != "$SRC" ]; then
        install -d -m 700 "$DEST/geloescht"
        mv -f "$DEST/$old" "$DEST/geloescht/"
    fi
done

echo "[3/6] virtual environment and program"
if [ -d "$DEST/venv" ] && ! "$DEST/venv/bin/python" -c '' 2>/dev/null; then
    mv "$DEST/venv" "$DEST/geloescht-venv-$(date +%s)"
fi
[ -d "$DEST/venv" ] || python3 -m venv --system-site-packages "$DEST/venv"
# shellcheck disable=SC1091
source "$DEST/venv/bin/activate"
pip install --quiet --upgrade "$SRC"
python -c 'import gi; gi.require_version("Gtk", "4.0")'

echo "[4/6] official program (list functions only; its installer is not run)"
if [ ! -x "$DEST/vendor/cyberghostvpn" ]; then
    [ -n "$ZIP" ] || ZIP="$(ls -t "$HOME"/Downloads/cyberghostvpn-ubuntu-*.zip 2>/dev/null \
                            | head -n 1 || true)"
    [ -f "$ZIP" ] || { echo "official app ZIP not found; pass its path" >&2; exit 1; }
    unzip -q -o -j "$ZIP" '*/cyberghost/cyberghostvpn' -d "$DEST/vendor"
    chmod 700 "$DEST/vendor/cyberghostvpn"
fi

echo "[5/6] menu entry, autostart and IPv6 rule (sudo)"
install -d "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/cyberghost-gui.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=CyberGhost VPN (GUI)
Exec=$DEST/venv/bin/cghost-gui
Icon=network-vpn
Terminal=false
Categories=Network;
DESK
# Autostart after login: hidden window, icon only. The delay lets the panel get ready
# to show indicator icons first.
install -d "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/cyberghost-gui.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=CyberGhost VPN (GUI)
Exec=$DEST/venv/bin/cghost-gui --hidden
Icon=network-vpn
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
DESK
if (( APT )); then
    sudo install -o root -g root -m 755 "$SRC/data/90-cyberghost-gui-ipv6" "$RULE"
    if [ "$(nmcli -g GENERAL.STATE connection show CyberGhost-GUI 2>/dev/null)" = activated ]; then
        sudo ip -6 route replace unreachable 2000::/3 metric 1
    fi
fi

echo "[6/6] switch a running application"
if "$DEST/venv/bin/cghost-gui-reload"; then
    echo "running application switches to $(python -c 'import cghostgui as c; print(c.__version__)')"
else
    pkill -f 'cghost_gui\.py' 2>/dev/null || true
    if (( START )); then
        setsid -f "$DEST/venv/bin/cghost-gui" >/dev/null 2>&1
        echo "application started"
    fi
fi
