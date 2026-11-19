"""Server lists from the read-only functions of the official program."""
import configparser
import getpass
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from cghostgui import paths, proc, store
from cghostgui.errors import CgError, LoginRequired
from cghostgui.models import City, Server

TTL_LISTS = 24 * 3600
TTL_USAGE = 15 * 60


def parse_table(text: str) -> list[list[str]]:
    """Return the data rows of a printed table.

    Args:
        text: Program output.

    Returns:
        Rows without the header.
    """
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in text.splitlines() if line.lstrip().startswith("|")]
    return rows[1:]


def _percent(value: str) -> int:
    """Extract a percentage.

    Args:
        value: Text such as ``12%``.

    Returns:
        The number, 999 if there is none.
    """
    match = re.search(r"\d+", value)
    return int(match.group()) if match else 999


class Catalog:
    """Reads and caches countries, streaming services, cities and servers.

    Attributes:
        username: Account name.
        password: Account password, kept in memory only.
    """

    def __init__(self) -> None:
        """Prepare the catalogue for the current user."""
        self.username: str | None = None
        self.password: str | None = None
        self._home = paths.vendor_home()

    def _has_own_config(self) -> bool:
        """Tell whether an installed official client already holds a login.

        Returns:
            True if its configuration contains an account.
        """
        config = configparser.RawConfigParser()
        try:
            config.read(self._home / "config.ini")
        except configparser.Error:
            return False
        return all(config.has_option("account", key) for key in ("username", "password"))

    def _write_config(self, target: Path) -> None:
        """Write the temporary login file the official program insists on.

        Args:
            target: File to create with mode 600.
        """
        store.private_dir(self._home)
        # The program reads the file with extended interpolation: "$" must be doubled.
        user = (self.username or "").replace("$", "$$")
        password = (self.password or "").replace("$", "$$")
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"[account]\nusername = {user}\npassword = {password}\n")

    def _cli(self, args: list[str]) -> str:
        """Run one list query.

        Args:
            args: Program arguments.

        Returns:
            Program output containing a table.

        Raises:
            CgError: The program is missing or printed no table.
            LoginRequired: A login is missing or was refused.
        """
        binary = paths.vendor_binary()
        if not os.access(binary, os.X_OK):
            raise CgError(f"CyberGhost-Programm fehlt: {binary} (install.sh ausführen)")
        config = self._home / "config.ini"
        token = self._home / "token"
        temporary = not self._has_own_config()
        if temporary and not self.password and not (token.is_file() and token.stat().st_size):
            raise LoginRequired("CyberGhost-Login für die Serverliste nötig")
        env = {key: value for key, value in os.environ.items() if key != "SUDO_USER"}
        env["USER"] = getpass.getuser()
        try:
            if temporary:
                self._write_config(config)
            result = proc.run([str(binary), *args], 60, env)
        finally:
            if temporary:
                config.unlink(missing_ok=True)
        text = f"{result.out}\n{result.err}".strip()
        if re.search(r"Wrong login|Authentication error|Bearer", text, re.I):
            token.unlink(missing_ok=True)
            self.password = None
            raise LoginRequired("CyberGhost-Login abgelehnt")
        if "|" not in result.out:
            raise CgError(text.splitlines()[-1] if text
                          else f"CyberGhost-Programm: Exit {result.code}")
        return result.out

    @staticmethod
    def _cached(key: str, ttl: int, fresh: bool, fetch: Callable[[], Any]) -> Any:
        """Return a list from the cache or fetch it.

        Args:
            key: Cache key.
            ttl: Validity in seconds.
            fresh: Ignore a valid cache entry.
            fetch: Function that obtains the list.

        Returns:
            The list; an outdated entry if fetching fails.

        Raises:
            CgError: Fetching failed and no entry exists.
        """
        folder = store.private_dir(paths.cache_dir())
        path = folder / (re.sub(r"[^a-z0-9_.-]+", "_", key.lower()) + ".json")
        if not fresh and path.exists() and time.time() - path.stat().st_mtime < ttl:
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            data = fetch()
        except LoginRequired:
            raise
        except CgError:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            raise
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def countries(self, fresh: bool = False) -> list[tuple[str, str]]:
        """List the countries.

        Args:
            fresh: Ignore the cache.

        Returns:
            Pairs of code and name, sorted by name.
        """
        def fetch() -> list[list[str]]:
            """Query the countries.

            Returns:
                Rows of code and name.
            """
            rows = parse_table(self._cli(["--traffic", "--country-code"]))
            return sorted(([r[2].upper(), r[1]] for r in rows if len(r) >= 3),
                          key=lambda item: item[1])
        return [(row[0], row[1]) for row in self._cached("countries", TTL_LISTS, fresh, fetch)]

    def streaming(self, fresh: bool = False) -> list[tuple[str, str]]:
        """List the streaming services.

        Args:
            fresh: Ignore the cache.

        Returns:
            Pairs of service name and country code, sorted by name.
        """
        def fetch() -> list[list[str]]:
            """Query the services.

            Returns:
                Rows of name and code.
            """
            rows = parse_table(self._cli(["--streaming", "--country-code"]))
            return sorted(([r[1], r[2].upper()] for r in rows if len(r) >= 3),
                          key=lambda item: item[0].lower())
        return [(row[0], row[1]) for row in self._cached("streaming", TTL_LISTS, fresh, fetch)]

    @staticmethod
    def _base(code: str, service: str | None) -> list[str]:
        """Build the arguments selecting a target.

        Args:
            code: Country code.
            service: Streaming service or None.

        Returns:
            Program arguments.
        """
        kind = ["--streaming", service] if service else ["--traffic"]
        return [*kind, "--country-code", code.lower()]

    def cities(self, code: str, service: str | None = None, fresh: bool = False) -> list[City]:
        """List the cities of a target.

        Args:
            code: Country code.
            service: Streaming service or None.
            fresh: Ignore the cache.

        Returns:
            Cities.
        """
        def fetch() -> list[list[Any]]:
            """Query the cities.

            Returns:
                Rows of name, server count and usage.
            """
            rows = parse_table(self._cli(self._base(code, service)))
            return [[r[1], int(r[2]), _percent(r[3])] for r in rows
                    if len(r) >= 4 and r[2].isdigit()]
        data = self._cached(f"cities_{service or 'traffic'}_{code}", TTL_USAGE, fresh, fetch)
        return [City(*item) for item in data]

    def servers(self, code: str, city: str, service: str | None = None,
                fresh: bool = False) -> list[Server]:
        """List the servers of a city, least used first.

        Args:
            code: Country code.
            city: City name.
            service: Streaming service or None.
            fresh: Ignore the cache.

        Returns:
            Servers.
        """
        def fetch() -> list[list[Any]]:
            """Query the servers.

            Returns:
                Rows of name and usage.
            """
            args = [*self._base(code, service), "--city", city.lower()]
            found = [[r[2].lower(), _percent(r[3])] for r in parse_table(self._cli(args))
                     if len(r) >= 4 and not r[2].isdigit()
                     and re.fullmatch(r"[a-z0-9][a-z0-9-]*", r[2].lower())]
            return sorted(found, key=lambda item: item[1])
        key = f"servers_{service or 'traffic'}_{code}_{city}"
        return [Server(*item) for item in self._cached(key, TTL_USAGE, fresh, fetch)]
