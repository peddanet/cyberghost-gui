# Changelog

## 0.5.1

* Stored passwords are never discarded automatically. An expired CyberGhost session is
  renewed with the stored account password; a refused password leads to a question
  whether to retry it or to enter a new one.
* Clearer login dialogs: account e-mail address and account password are named as such.
* `install.sh` sets up autostart after login (window hidden, icon only).
* `first-publish.sh`: final hint uses a `gh repo edit` option every version knows.

## 0.5.0

First public version.

* Target selection by country, city, server and streaming service; UDP and TCP.
* Connection through NetworkManager; import of a manual device configuration.
* Passwords in the key ring, asked once; new request only after a rejection.
* Clear handling of `AUTH_FAILED`.
* Panel indicator with live details; closing the window keeps it running.
* IPv6 block while connected; warning for differing reported locations.
* Update with live switch of the running application.
