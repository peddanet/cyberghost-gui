# Developer guide

## Components

~~~mermaid
flowchart LR
    W[Window, GTK 4] --> C[connector]
    W --> K[Keyring]
    W --> L[Catalog]
    C --> V[vpn]
    C --> D[diagnostics]
    T[Tray process, GTK 3] --> M[traymodel]
    M --> V
    M --> D
    L --> O[official program, list functions]
    V --> N[NetworkManager and OpenVPN]
    N --> R[dispatcher rule: IPv6 block]
~~~

The indicator library needs GTK 3 and the window uses GTK 4. They cannot share a
process, so the indicator is a child process that talks to the application over
the session bus.

## Classes

~~~mermaid
classDiagram
    class Application { tray_alive() request_reload() idle_now() restart() }
    class Window { background() start_connect() start_disconnect() start_check() }
    class Catalog { countries() streaming() cities() servers() }
    class Tray { update() open_window() disconnect() quit_app() }
    class Keyring { get() put() clear() }
    class Pick { fill() select() value }
    class InputDialog { submit() }
    Application --> Window
    Window --> Catalog
    Window --> Pick
    Window --> InputDialog
    Window --> Keyring
~~~

## Switching a target

~~~mermaid
sequenceDiagram
    participant U as User
    participant W as Window
    participant C as connector
    participant N as NetworkManager
    U->>W: Ziel wechseln
    W->>C: switch(target)
    C->>C: choose host, check that it resolves
    C->>N: down, set remote, up with private password file
    N-->>C: activated or AUTH_FAILED in the journal
    N->>N: dispatcher sets the IPv6 block
    C-->>W: host
    W->>W: show outside view
~~~

A host that does not resolve leaves a running tunnel untouched. `AUTH_FAILED`
stops the attempt at once, removes the stored OpenVPN password and asks again.

## Folders

`paths` follows the XDG base directories: `config_dir()` (settings, imported
configuration), `data_dir()` (venv, official program) and `cache_dir()` (server
lists). `legacy_dir()` names the single folder of releases up to 0.5.1;
`migrate` moves its files once, never overwriting. The configuration files are
referenced by the NetworkManager profile, so they are copied, the profile entries
that point into the old folder are changed with `nmcli connection modify
+vpn.data <entry>=<new path>`, and the old files are removed only while the VPN
is down.

## Release, install and live switch

`tools/release.sh` (see CONTRIBUTING.md) merges through pull requests and tags
the release. `install.sh vX.Y.Z` installs only that tag, as it is on origin,
into the venv, links `~/.local/bin/cyberghost-gui` and checks `--version`. Then
`cghost-gui-reload` activates the action `reload` over the session bus. The
application waits until no job runs, ends the indicator and replaces itself with
`os.execv`. NetworkManager holds the VPN, so the connection is not interrupted.
An application still running from the venv of the old layout cannot switch
itself to the new venv; `install.sh` ends it through the action `quit` and starts
the new release with the window hidden.

## Tests

The tests replace every external program by `tests/fakes.py`. The window runs on
real GTK under Xvfb. The indicator gets a fake toolkit because GTK 3 and GTK 4
cannot be imported into one process.
