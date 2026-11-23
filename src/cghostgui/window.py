"""Main window."""
import threading
from dataclasses import dataclass
from typing import Any, Callable

import gi
gi.require_version("Gtk", "4.0")
# pylint: disable=wrong-import-position
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from cghostgui import __version__, connector, diagnostics, profile, store, vpn  # noqa: E402
from cghostgui.catalog import Catalog  # noqa: E402
from cghostgui.dialogs import ChoiceDialog, InputDialog, padded  # noqa: E402
from cghostgui.errors import AuthRejected, CgError, LoginRejected, LoginRequired  # noqa: E402
from cghostgui.keyring import Keyring  # noqa: E402
from cghostgui.pick import Pick  # noqa: E402

AUTO = ""
AUTO_SERVER = "Automatisch (geringste Last)"
VPN_HINT = ("Von der CyberGhost-Seite „View Configuration“ dieser Konfiguration. "
            "Nicht das Passwort Ihres CyberGhost-Kontos.")


@dataclass
class Controls:
    """The widgets the window works with."""

    mode: Pick
    country: Pick
    service: Pick
    city: Pick
    server: Pick
    proto: Pick
    connect: Gtk.Button
    down: Gtk.Button
    check: Gtk.Button
    state: Gtk.Label
    log: Gtk.Label
    lan: Gtk.Entry


class Window(Gtk.ApplicationWindow):
    """Selection of the target, connection control and status."""

    def __init__(self, app: Any) -> None:
        """Build the window and start reading the server lists.

        Args:
            app: The application.
        """
        super().__init__(application=app, title=f"CyberGhost VPN {__version__}",
                         default_width=560)
        self.catalog = Catalog()
        self.settings = store.read_settings()
        self.catalog.username = self.settings.get("account_user")
        self.vpn_password: str | None = None
        self.busy = False
        self.pending: Callable[[], None] | None = None
        self._rows: dict[str, tuple[Gtk.Label, Gtk.Widget]] = {}
        self.ui = self._build()
        self.connect("close-request", self._on_close)
        GLib.timeout_add_seconds(3, self._tick)
        self._mode_changed(initial=True)
        self.refresh_state()
        missing = diagnostics.missing_tools()
        if missing:
            self.say("Fehlende Programme: " + ", ".join(missing))
        if not vpn.profile_exists():
            self.say("Zuerst die ZIP-Datei aus „Configure Device“ importieren.")
        self.read_lists(False)

    def _build(self) -> Controls:
        """Create the widgets.

        Returns:
            The controls.
        """
        ui = Controls(
            Pick(self._mode_changed), Pick(self._target_changed), Pick(self._target_changed),
            Pick(self._city_changed), Pick(), Pick(), Gtk.Button(label="Verbinden", hexpand=True),
            Gtk.Button(label="Trennen"), Gtk.Button(label="Prüfen"),
            Gtk.Label(xalign=0, wrap=True, selectable=True),
            Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=True, vexpand=True),
            Gtk.Entry(text=self.settings.get("lan_target", ""), hexpand=True,
                      placeholder_text="z. B. 192.168.1.10"))
        ui.mode.fill([("Standard", "traffic"), ("Streaming", "streaming")],
                     self.settings.get("mode"))
        ui.proto.fill([("UDP", "udp"), ("TCP", "tcp")], self.settings.get("proto"))
        grid = Gtk.Grid(row_spacing=8, column_spacing=12)
        for row, (key, text, pick) in enumerate(
                (("mode", "Art", ui.mode), ("country", "Land", ui.country),
                 ("service", "Dienst", ui.service), ("city", "Stadt", ui.city),
                 ("server", "Server", ui.server), ("proto", "Protokoll", ui.proto))):
            label = Gtk.Label(label=text, xalign=0)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(pick.widget, 1, row, 1, 1)
            self._rows[key] = (label, pick.widget)
        ui.connect.add_css_class("suggested-action")
        ui.connect.connect("clicked", lambda *_: self.start_connect())
        ui.down.connect("clicked", lambda *_: self.start_disconnect())
        ui.check.connect("clicked", lambda *_: self.start_check())
        buttons = Gtk.Box(spacing=8)
        for button in (ui.connect, ui.down, ui.check):
            buttons.append(button)
        ui.state.add_css_class("title-4")
        ui.log.add_css_class("dim-label")
        lan_row = Gtk.Box(spacing=12)
        lan_row.append(Gtk.Label(label="Heimnetz-Testziel"))
        lan_row.append(ui.lan)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for widget in (ui.state, grid, buttons, lan_row, ui.log):
            box.append(widget)
        self.set_child(padded(box))
        self._build_header()
        return ui

    def _build_header(self) -> None:
        """Create the title bar."""
        header = Gtk.HeaderBar()
        importer = Gtk.Button(label="Konfiguration importieren")
        importer.connect("clicked", lambda *_: self._choose_archive())
        refresh = Gtk.Button(label="Listen aktualisieren")
        refresh.connect("clicked", lambda *_: self.read_lists(True))
        header.pack_start(importer)
        header.pack_end(refresh)
        self.set_titlebar(header)

    def _on_close(self, *_: Any) -> bool:
        """Hide the window while an indicator exists, otherwise quit.

        Returns:
            True, the default handling is not wanted.
        """
        app = self.get_application()
        if app.tray_alive():
            self.set_visible(False)
        else:
            app.quit()
        return True

    def _tick(self) -> bool:
        """Refresh the state periodically.

        Returns:
            True, to keep the timer running.
        """
        if not self.busy:
            self.refresh_state()
        return True

    def say(self, text: str) -> None:
        """Show a status text.

        Args:
            text: Text.
        """
        self.ui.log.set_text(text)

    def background(self, work: Callable[[], Any], done: Callable[[Any], Any] | None = None,
                   label: str = "Bitte warten …", retry: Callable[[], None] | None = None) -> None:
        """Run work in a thread, one job at a time; the newest waiting job wins.

        Args:
            work: Job.
            done: Receives the result in the GUI thread.
            label: Status text while running.
            retry: Repeats the action after a login.
        """
        if self.busy:
            self.pending = lambda: self.background(work, done, label, retry)
            return
        self._set_busy(True)
        self.say(label)

        def finish(result: Any, error: Exception | None) -> bool:
            """Show the outcome in the GUI thread.

            Args:
                result: Result of the job.
                error: Failure of the job.

            Returns:
                False, to run once.
            """
            self._set_busy(False)
            self.refresh_state()
            if isinstance(error, LoginRequired):
                self._ask_login(str(error), retry)
            elif isinstance(error, LoginRejected):
                self._keep_or_replace_account(str(error), retry)
            elif isinstance(error, AuthRejected):
                self._keep_or_replace_vpn(str(error))
            elif error:
                self.say(f"Fehler: {error}")
            elif done:
                done(result)
            following, self.pending = self.pending, None
            if following and not self.busy:
                following()
            self.get_application().idle_now()
            return False

        def thread() -> None:
            try:
                result, error = work(), None
            except Exception as problem:  # pylint: disable=broad-exception-caught
                result, error = None, problem  # shown to the user, never fatal
            GLib.idle_add(finish, result, error)

        threading.Thread(target=thread, daemon=True).start()

    def _set_busy(self, value: bool) -> None:
        """Enable or disable the buttons.

        Args:
            value: True while a job runs.
        """
        self.busy = value
        for button in (self.ui.connect, self.ui.down, self.ui.check):
            button.set_sensitive(not value)

    def refresh_state(self) -> None:
        """Show the connection state."""
        state = vpn.state()
        remote = vpn.current_remote() or "?"
        texts = {"activated": f"Verbunden: {remote}", "activating": f"Verbindungsaufbau: {remote}"}
        self.ui.state.set_text(texts.get(state, "Nicht verbunden"))
        self.ui.connect.set_label("Ziel wechseln" if state in texts else "Verbinden")

    def _remember(self) -> None:
        """Store the current selection."""
        self.settings = {**store.read_settings(), **self.settings,
                         "mode": self.ui.mode.value, "proto": self.ui.proto.value,
                         "lan_target": self.ui.lan.get_text().strip(),
                         "country": self.ui.country.value, "service": self.ui.service.value}
        store.write_settings(self.settings)

    def _target(self) -> tuple[str | None, str | None]:
        """Return the selected country and service.

        Returns:
            Country code and streaming service.
        """
        if self.ui.mode.value == "streaming":
            if not self.ui.service.value:
                return None, None
            name, code = self.ui.service.value.rsplit("\t", 1)
            return code, name
        return self.ui.country.value, None

    def read_lists(self, fresh: bool) -> None:
        """Fill countries and services.

        Args:
            fresh: Ignore the cache.
        """
        if not self.catalog.password:
            self.catalog.password = Keyring.get("account")

        def done(result: Any) -> None:
            countries, services = result
            self.ui.country.fill([(f"{name} ({code})", code) for code, name in countries],
                                 self.settings.get("country"))
            self.ui.service.fill([(f"{name} · {code}", f"{name}\t{code}")
                                  for name, code in services], self.settings.get("service"))
            self.say(f"{len(countries)} Länder, {len(services)} Streaming-Dienste geladen.")
            self._target_changed()

        self.background(lambda: (self.catalog.countries(fresh), self.catalog.streaming(fresh)),
                        done, "Lade Serverlisten …", lambda: self.read_lists(fresh))

    def _mode_changed(self, initial: bool = False) -> None:
        """Switch between country and service selection.

        Args:
            initial: True during construction.
        """
        streaming = self.ui.mode.value == "streaming"
        for widget in self._rows["country"]:
            widget.set_visible(not streaming)
        for widget in self._rows["service"]:
            widget.set_visible(streaming)
        if not initial:
            self._target_changed()

    def _target_changed(self) -> None:
        """Read the cities of the selected target."""
        code, service = self._target()
        self.ui.city.fill([("Automatisch", AUTO)])
        self.ui.server.fill([(AUTO_SERVER, AUTO)])
        if not code:
            return

        def done(cities: Any) -> None:
            self.ui.city.fill([("Automatisch", AUTO)] + [
                (f"{c.name} · {c.servers} Server · {c.usage} %", c.name) for c in cities])
            self.say("")

        self.background(lambda: self.catalog.cities(code, service), done, "Lade Städte …",
                        self._target_changed)

    def _city_changed(self) -> None:
        """Read the servers of the selected city."""
        code, service = self._target()
        city = self.ui.city.value
        self.ui.server.fill([(AUTO_SERVER, AUTO)])
        if not (code and city):
            return

        def done(servers: Any) -> None:
            self.ui.server.fill([(AUTO_SERVER, AUTO)] + [
                (f"{s.name} · {s.usage} %", s.name) for s in servers])
            self.say("")

        self.background(lambda: self.catalog.servers(code, city, service), done, "Lade Server …",
                        self._city_changed)

    def _selection(self, code: str, service: str | None) -> connector.Target:
        """Describe the current selection.

        Args:
            code: Country code.
            service: Streaming service.

        Returns:
            Target.
        """
        names = dict(zip(self.ui.country.values, self.ui.country.labels))
        label = service or names.get(code, code).rsplit(" (", 1)[0]
        city = self.ui.city.value or ""
        if city:
            label += f" · {city}"
        return connector.Target(code, service, city, self.ui.server.value or "",
                                self.ui.proto.value, label)

    def start_connect(self) -> None:
        """Connect to the selected target."""
        template = profile.read_template() if vpn.profile_exists() else None
        if template is None:
            self.say("Zuerst die Konfiguration importieren.")
            return
        code, service = self._target()
        if not code:
            self.say("Bitte zuerst ein Ziel wählen (Listen aktualisieren).")
            return
        password = self.vpn_password or Keyring.get("openvpn")
        if not password:
            self._ask_secret("OpenVPN-Passwort", VPN_HINT, "openvpn", self._got_vpn_password)
            return
        self.vpn_password = password
        self._remember()
        target = self._selection(code, service)
        lan = self.ui.lan.get_text().strip()

        def work() -> list[str]:
            """Connect and check the result.

            Returns:
                Lines for the status area.

            Raises:
                AuthRejected: The server refused the login.
            """
            try:
                host = connector.switch(self.catalog, target, template, password)
            except AuthRejected:
                self.vpn_password = None  # read again from the key ring; never discarded here
                raise
            return [f"Verbunden mit {host}", *diagnostics.check(lan)]

        self.background(work, lambda lines: self.say("\n".join(lines)), "Verbinde …",
                        self.start_connect)

    def _got_vpn_password(self, value: str) -> None:
        """Connect with an entered password.

        Args:
            value: Password.
        """
        self.vpn_password = value.strip()
        self.start_connect()

    def start_disconnect(self) -> None:
        """Take the connection down."""
        self.background(vpn.disconnect,
                        lambda _: self.say("Getrennt. Der Verkehr läuft wieder direkt."),
                        "Trenne …")

    def start_check(self) -> None:
        """Show the outside view of the connection."""
        lan = self.ui.lan.get_text().strip()
        self._remember()
        self.background(lambda: diagnostics.check(lan), lambda lines: self.say("\n".join(lines)),
                        "Prüfe …")

    def _keep_or_replace_vpn(self, why: str) -> None:
        """Let the user decide whether the stored OpenVPN login is replaced.

        Args:
            why: Reason.
        """
        self.say(f"{why}. VPN ist getrennt. Das gespeicherte Passwort bleibt erhalten.")
        ChoiceDialog(self, "OpenVPN-Anmeldung abgelehnt",
                     f"{why}.\n\nDas gespeicherte OpenVPN-Passwort bleibt, bis Sie ein neues "
                     "eingeben.",
                     [("Gespeichertes Passwort erneut versuchen", self.start_connect),
                      ("Neuen Benutzernamen und neues Passwort eingeben",
                       lambda: self._ask_vpn_login(why)),
                      ("Abbrechen", lambda: None)])

    def _keep_or_replace_account(self, why: str, retry: Callable[[], None] | None) -> None:
        """Let the user decide whether the stored account password is replaced.

        Args:
            why: Reason.
            retry: Repeats the interrupted action.
        """
        self.say(f"{why} Das gespeicherte Passwort bleibt erhalten.")
        ChoiceDialog(self, "CyberGhost-Konto: Anmeldung abgelehnt",
                     f"{why}\n\nDas gespeicherte Konto-Passwort bleibt, bis Sie ein neues "
                     "eingeben.",
                     [("Gespeichertes Passwort erneut versuchen", retry or (lambda: None)),
                      ("Neues Konto-Passwort eingeben", lambda: self._ask_login(why, retry)),
                      ("Abbrechen", lambda: None)])

    def _ask_vpn_login(self, why: str) -> None:
        """Ask for corrected OpenVPN credentials.

        Args:
            why: Reason.
        """
        self.say(f"{why}. VPN ist getrennt.")

        def got_user(user: str) -> None:
            self.settings["vpn_user"] = user.strip()
            store.write_settings(self.settings)
            try:
                vpn.set_username(user)
            except CgError as error:
                self.say(f"Fehler: {error}")
                return
            self._ask_secret("OpenVPN-Passwort", VPN_HINT, "openvpn", self._got_vpn_password)

        InputDialog(self, "OpenVPN-Benutzername",
                    f"{why}. Benötigt wird der „User name“ von „View Configuration“, "
                    "nicht Ihr Konto-Login.", got_user, self.settings.get("vpn_user", ""))

    def _choose_archive(self) -> None:
        """Let the user pick a configuration archive."""
        dialog = Gtk.FileDialog(title="CyberGhost-Konfiguration (ZIP)")
        file_filter = Gtk.FileFilter(name="ZIP-Dateien")
        file_filter.add_pattern("*.zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        dialog.set_filters(filters)

        def opened(source: Any, result: Any) -> None:
            try:
                path = source.open_finish(result).get_path()
            except GLib.Error:
                return
            self.ask_import_user(path)

        dialog.open(self, None, opened)

    def ask_import_user(self, path: str) -> None:
        """Ask for the OpenVPN user name of an archive.

        Args:
            path: Archive.
        """
        InputDialog(self, "OpenVPN-Benutzername", "Von der CyberGhost-Seite „View Configuration“",
                    lambda user: self._import(path, user.strip()),
                    self.settings.get("vpn_user", ""))

    def _import(self, path: str, user: str) -> None:
        """Import an archive.

        Args:
            path: Archive.
            user: OpenVPN user name.
        """
        self.settings["vpn_user"] = user
        store.write_settings(self.settings)
        self.vpn_password = None
        Keyring.clear("openvpn")
        self.background(lambda: profile.import_zip(path, user),
                        lambda t: self.say(f"Importiert. Vorlage: {t.host}:{t.port}/{t.proto}"),
                        "Importiere …")

    def _ask_login(self, why: str, retry: Callable[[], None] | None) -> None:
        """Ask for the account login.

        Args:
            why: Reason.
            retry: Repeats the interrupted action.
        """
        def got_password(value: str) -> None:
            self.catalog.password = value
            if retry:
                retry()

        def ask_password() -> None:
            self._ask_secret("CyberGhost-Konto: Passwort",
                             f"{why}\n\nGemeint ist das Passwort, mit dem Sie sich auf "
                             "cyberghostvpn.com anmelden. Es wird im Schlüsselbund gespeichert "
                             "und nur ersetzt, wenn Sie es selbst neu eingeben.",
                             "account", got_password)

        def got_user(user: str) -> None:
            self.settings["account_user"] = self.catalog.username = user.strip()
            store.write_settings(self.settings)
            ask_password()

        if self.catalog.username:
            ask_password()
        else:
            InputDialog(self, "CyberGhost-Konto: E-Mail-Adresse",
                        f"{why}\n\nGemeint ist die E-Mail-Adresse bzw. der Benutzername Ihres "
                        "CyberGhost-Kontos.", got_user, "")

    def _ask_secret(self, title: str, hint: str, kind: str,
                    callback: Callable[[str], None]) -> None:
        """Ask for a password once and keep it in the key ring.

        Args:
            title: Dialog title.
            hint: Explanation.
            kind: Key ring entry.
            callback: Receives the password.
        """
        def accepted(value: str) -> None:
            if not Keyring.put(kind, value.strip() if kind == "openvpn" else value):
                self.say("Hinweis: Schlüsselbund nicht erreichbar, "
                         "Passwort gilt nur bis zum Programmende.")
            callback(value)

        InputDialog(self, title, hint, accepted)
