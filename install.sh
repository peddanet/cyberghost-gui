#!/usr/bin/env bash
# install.sh - install a pushed release tag for the current user and switch a running
# application to it. The VPN connection stays up.
#
#   ~/.local/share/cyberghost-gui/venv     installed release (virtual environment)
#   ~/.local/share/cyberghost-gui/vendor   official program, list functions only
#   ~/.local/bin/cyberghost-gui            command (link into the venv)
#   ~/.config/cyberghost-gui               settings, imported configuration, privacy lists
#   ~/.cache/cyberghost-gui                server lists
#
# Usage: ./install.sh vX.Y.Z [--no-apt] [--no-start] [PATH-TO-OFFICIAL-APP.zip]
#
# Only a release tag that is also on origin is installed, never the working tree.
# Files of the old layout (~/scripts/cyberghost-gui, up to 0.5.1) are moved once;
# an application still running from the old folder is ended and started again.
#
# Run as a normal user. sudo is used only for system packages and for the
# NetworkManager rule that blocks public IPv6 while the VPN is connected.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME=cyberghost-gui
DATA="${XDG_DATA_HOME:-}"
[[ "$DATA" == /* ]] || DATA="$HOME/.local/share"
DATA="$DATA/$NAME"
VENV="$DATA/venv"
BIN="$HOME/.local/bin"
LEGACY="${CGHOST_GUI_HOME:-$HOME/scripts/cyberghost-gui}"
RULE=/etc/NetworkManager/dispatcher.d/90-cyberghost-gui-ipv6
GDBUS=(gdbus call --session --dest local.cghostgui.Switcher --object-path /local/cghostgui/Switcher
       --method org.gtk.Actions.Activate)

die() { echo "install.sh: $*" >&2; exit 1; }

TAG=""; APT=1; START=1; ZIP=""
for arg in "$@"; do
    case "$arg" in
        v[0-9]*) TAG="$arg" ;;
        --no-apt) APT=0 ;;
        --no-start) START=0 ;;
        *) ZIP="$arg" ;;
    esac
done
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "usage: ./install.sh vX.Y.Z [--no-apt] [--no-start] [ZIP] (release tag required)"
[ "$(id -u)" -ne 0 ] || die "run as a normal user, not as root"
VERSION="${TAG#v}"

COMMIT="$(git -C "$SRC" rev-parse --verify --quiet "refs/tags/$TAG^{commit}")" \
    || die "tag $TAG is unknown here - fetch it first: git fetch --tags origin"
REMOTE="$(git -C "$SRC" ls-remote --tags origin "refs/tags/$TAG^{}" | cut -f1)"
[[ -n "$REMOTE" ]] || REMOTE="$(git -C "$SRC" ls-remote --tags origin "refs/tags/$TAG" | cut -f1)"
[[ "$REMOTE" == "$COMMIT" ]] || die "tag $TAG is not on origin or differs from it - push it first"

if (( APT )); then
    echo "[1/7] system packages (sudo)"
    sudo apt-get install -y network-manager-openvpn openvpn python3-venv python3-gi \
        gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
        libsecret-tools libglib2.0-bin unzip curl
fi

echo "[2/7] release $TAG"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$SRC" archive "$TAG" | tar -x -C "$WORK"

echo "[3/7] virtual environment: $VENV"
install -d -m 700 "$DATA"
if [ -d "$VENV" ] && ! "$VENV/bin/python" -c '' 2>/dev/null; then
    echo "      its Python is gone - building it again"
    rm -rf "$VENV"
fi
[ -d "$VENV" ] || python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install --quiet --force-reinstall --no-deps "$WORK"
"$VENV/bin/python" -c 'import gi; gi.require_version("Gtk", "4.0")'
REPORTED="$("$VENV/bin/cyberghost-gui" --version)"
[[ "$REPORTED" == "$NAME $VERSION" ]] || die "installed program reports '$REPORTED', not $VERSION"
install -d "$BIN"
ln -sfn "$VENV/bin/cyberghost-gui" "$BIN/cyberghost-gui"
echo "      $BIN/cyberghost-gui -> $REPORTED"

echo "[4/7] application of the old layout"
STOPPED=0
if pgrep -f "^$LEGACY/venv/bin/python" >/dev/null; then
    "${GDBUS[@]}" quit '[]' '{}' >/dev/null 2>&1 || true
    # wait for the window process; the indicator process is ended right after
    APP_RE="^$LEGACY/venv/bin/python[0-9.]* ($LEGACY/venv/bin/cghost-gui|-m cghostgui( |\$))"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -f "$APP_RE" >/dev/null || break
        sleep 1
    done
    pkill -f "^$LEGACY/venv/bin/python" || true
    STOPPED=1
    echo "      ended; it is started again from the new location below"
else
    echo "      none running"
fi

echo "[5/7] move files of the old layout"
"$VENV/bin/python" -m cghostgui.migrate

echo "[6/7] official program (list functions only; its installer is not run)"
VENDOR="$DATA/vendor/cyberghostvpn"
if [ ! -x "$VENDOR" ]; then
    if [ -z "$ZIP" ]; then
        ZIP="$(find "$HOME/Downloads" -maxdepth 1 -name 'cyberghostvpn-ubuntu-*.zip' \
               -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2-)"
    fi
    [ -f "$ZIP" ] || die "official app ZIP not found; pass its path"
    install -d -m 700 "$DATA/vendor"
    unzip -q -o -j "$ZIP" '*/cyberghost/cyberghostvpn' -d "$DATA/vendor"
    chmod 700 "$VENDOR"
fi

echo "[7/7] menu entry, autostart and IPv6 rule (sudo)"
install -d "$HOME/.local/share/applications" "$HOME/.config/autostart"
cat > "$HOME/.local/share/applications/$NAME.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=CyberGhost VPN (GUI)
Exec=$BIN/cyberghost-gui
Icon=network-vpn
Terminal=false
Categories=Network;
DESK
# Autostart after login: hidden window, icon only. The delay lets the panel get ready
# to show indicator icons first.
cat > "$HOME/.config/autostart/$NAME.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=CyberGhost VPN (GUI)
Exec=$BIN/cyberghost-gui --hidden
Icon=network-vpn
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
DESK
if (( APT )); then
    sudo install -o root -g root -m 755 "$WORK/data/90-cyberghost-gui-ipv6" "$RULE"
    if [ "$(nmcli -g GENERAL.STATE connection show CyberGhost-GUI 2>/dev/null)" = activated ]; then
        sudo ip -6 route replace unreachable 2000::/3 metric 1
    fi
fi

# The old venv was created by an earlier install.sh; it goes once nothing runs from it.
if [ -d "$LEGACY/venv" ] && ! pgrep -f "^$LEGACY/venv/bin/python" >/dev/null; then
    rm -rf "$LEGACY/venv"
    echo "removed the old virtual environment $LEGACY/venv"
fi
if [ -d "$LEGACY" ]; then
    if rmdir "$LEGACY" 2>/dev/null; then
        echo "removed the empty old folder $LEGACY"
    else
        echo "left in the old folder $LEGACY (delete it yourself once checked):"
        ls -A "$LEGACY"
    fi
fi

echo
if pgrep -f "^$VENV/bin/python" >/dev/null && "$VENV/bin/cghost-gui-reload"; then
    echo "the running application switches to $VERSION"
elif (( STOPPED )); then
    setsid -f "$BIN/cyberghost-gui" --hidden >/dev/null 2>&1
    echo "application started again (icon in the panel)"
elif (( START )); then
    setsid -f "$BIN/cyberghost-gui" >/dev/null 2>&1
    echo "application started"
fi
