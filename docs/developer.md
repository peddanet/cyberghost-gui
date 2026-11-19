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

## Update and live switch

`install.sh` installs into the venv, then `cghost-gui-reload` activates the action
`reload` over the session bus. The application waits until no job runs, ends the
indicator and replaces itself with `os.execv`. NetworkManager holds the VPN, so
the connection is not interrupted.

## Tests

The tests replace every external program by `tests/fakes.py`. The window runs on
real GTK under Xvfb. The indicator gets a fake toolkit because GTK 3 and GTK 4
cannot be imported into one process.
