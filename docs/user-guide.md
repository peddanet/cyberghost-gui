# User guide

The user interface is German; the terms below are the labels you will see.

## Install

~~~bash
./install.sh ~/Downloads/cyberghostvpn-ubuntu-22.04-1.5.0.zip
~~~

Run as a normal user. The script uses `sudo` only for system packages and for
the NetworkManager rule that blocks public IPv6.

| Location | Content |
|---|---|
| `~/scripts/cyberghost-gui/venv` | installed program |
| `~/scripts/cyberghost-gui/vendor` | official program, used for server lists |
| `~/scripts/cyberghost-gui/profile` | imported configuration, mode 600 |
| `~/scripts/cyberghost-gui/cache` | server lists |
| `~/scripts/cyberghost-gui/settings.json` | selection, user names |

`CGHOST_GUI_HOME` selects another folder.

## Use case: first connection

1. In your CyberGhost account open **VPN**, then **Configure Device**. Choose
   OpenVPN, a country, a server group and UDP. Save it.
2. Open **View Configuration** and download the ZIP file. Keep the page open.
3. Start **CyberGhost VPN (GUI)** and enter your account login when asked. It
   is used for the server lists.
4. Click **Konfiguration importieren**, choose the ZIP and enter the **User name**
   shown on the page.
5. Choose **Land** and click **Verbinden**. Enter the **Password** from the page.
   It is not your account password.

Each password is asked once and stored in the desktop key ring. A stored password
is never removed automatically: if it is refused, the application asks whether to
try it again or to enter a new one. An expired session of the server lists is
renewed with the stored account password without asking.

After login the application starts by itself with the window hidden; the panel icon
opens it.

## Use case: change the target

Choose another **Land**, **Stadt** or **Server** and click **Ziel wechseln**. For
a streaming service set **Art** to **Streaming** and choose **Dienst**.

## Use case: check the connection

**Prüfen** shows the public address, the reported location, IPv6 visibility and,
if **Heimnetz-Testziel** is filled in, whether that address answers.

## Panel indicator

The indicator shows a lock and the target. Its menu lists server, public
address, duration, traffic and the IPv6 path. A detail line or **Ziel ändern …**
opens the window. **Beenden** ends the application; the VPN stays connected until
you choose **Trennen**.

## Update

~~~bash
source .venv/bin/activate
update/apply-release.sh
~~~

A running application switches to the new release when it is idle.

## Limits

* No kill switch: traffic leaves directly while switching or after a failure.
* IPv6 to the internet is blocked while connected, not tunnelled.
* For a virtual server location the address is registered for the chosen country
  while the server may be elsewhere. Websites decide with their own location
  databases, so results can differ.

## Glossary

**AppIndicator** -- panel icon with menu.
[Ayatana indicators](https://github.com/AyatanaIndicators/libayatana-appindicator)

**Dispatcher script** -- program NetworkManager runs on connection events.
[NetworkManager-dispatcher](https://networkmanager.dev/docs/api/latest/NetworkManager-dispatcher.html)

**Kill switch** -- a rule that blocks all traffic outside the tunnel.

**Virtual server location** -- server whose address is registered for another
country than the one it stands in.
